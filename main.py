import os
import ssl
from flask import Flask
from flask_cors import CORS
from flask_admin import Admin
from dotenv import load_dotenv
from flask_jwt_extended import JWTManager
import boto3
import langchain
from langchain.embeddings import OpenAIEmbeddings
from datetime import timedelta

from retrievers import retriever_store
from retrievers.PGVectorRetriever import build_pg_vector_retriever
from retrievers.TableColumnRetriever import build_table_column_retriever
from socketio_instance import socketio
from database import db, bcrypt, revoked_tokens, load_models, get_models
from admin_panel.LocationModelView import LocationModelView
from admin_panel.DocumentModelView import DocumentModelView
from routes.search_routes import search_routes_bp

openai_api_key = os.getenv("OPENAI_API_KEY")
connection_uri = os.getenv("POSTGRES_DSN")
langchain_pg_collection_name = os.getenv("LANGCHAIN_PG_COLLECTION_NAME")

embeddings_model = OpenAIEmbeddings(openai_api_key=openai_api_key)

load_dotenv()

# Creating a TableColumnRetriever to index all of the columns for the location table when retrieving documents (location based questions)
retriever_store.table_column_retriever = build_table_column_retriever(
    connection_uri=connection_uri,
    table_name="location",
)

retriever_store.pg_vector_retriever = build_pg_vector_retriever(
    langchain_pg_collection_name, embeddings_model, connection_uri)

s3 = boto3.client("s3")

os.environ["TOKENIZERS_PARALLELISM"] = "false"

try:
    _create_unverified_https_context = ssl._create_unverified_context
except AttributeError:
    pass
else:
    ssl._create_default_https_context = _create_unverified_https_context
 

def create_app():
    app = Flask(__name__)

    app.config['SQLALCHEMY_DATABASE_URI'] = os.getenv(
        'POSTGRESQL_CONNECTION_STRING')
    app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
    app.config['JWT_ACCESS_TOKEN_EXPIRES'] = timedelta(hours=1)
    app.config['PERMANENT_SESSION_LIFETIME'] = timedelta(hours=1)
    app.config['JWT_BLACKLIST_ENABLED'] = True
    app.config['JWT_BLACKLIST_TOKEN_CHECKS'] = ['access']
    app.config['SECRET_KEY'] = os.getenv('SECRET_KEY')  # Change this

    langchain.verbose = False

    CORS(app, supports_credentials=True)
    bcrypt.init_app(app)
    jwt = JWTManager(app)

    @jwt.token_in_blocklist_loader
    def check_if_token_in_blocklist(jwt_header, jwt_payload):
        return jwt_payload["jti"] in revoked_tokens

    return app


def register_blueprints(app):
    app.register_blueprint(search_routes_bp)


def setup_database(app):
    with app.app_context():
        db.init_app(app)
        db.create_all()
        load_models()


def setup_admin(app):
    admin = Admin(app, name='ollie')
    models = get_models()
    admin.add_view(LocationModelView(
        models.location, db.session, embeddings_model))
    admin.add_view(DocumentModelView(models.local_resources,
                   db.session, embeddings_model, s3))


app = create_app()
setup_database(app)
setup_admin(app)
register_blueprints(app)
socketio.init_app(app)

if __name__ == "__main__":
    socketio.run(app, host="0.0.0.0", port=5050)
