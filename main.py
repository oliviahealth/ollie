import os
import ssl
from flask import Flask, Response, make_response, redirect, request, g
from flask_cors import CORS
from flask_admin import Admin
from dotenv import load_dotenv
from flask_jwt_extended import JWTManager, create_access_token, jwt_required, set_access_cookies, verify_jwt_in_request
import boto3
import langchain
from langchain.embeddings import OpenAIEmbeddings
from datetime import timedelta

from retrievers import retriever_store
from retrievers.PGVectorRetriever import build_pg_vector_retriever
from retrievers.TableColumnRetriever import build_table_column_retriever
from socketio_instance import socketio
from database import db, bcrypt, load_models, get_models
from init_database import AdminUser
from flask_admin.contrib.sqla import ModelView
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

s3 = boto3.client(
    "s3",
    region_name=os.getenv("AWS_DEFAULT_REGION", "us-east-1"),
    aws_access_key_id=os.getenv("AWS_S3_ACCESS_KEY_ID"),
    aws_secret_access_key=os.getenv("AWS_S3_SECRET_ACCESS_KEY"),
)

os.environ["TOKENIZERS_PARALLELISM"] = "false"

try:
    _create_unverified_https_context = ssl._create_unverified_context
except AttributeError:
    pass
else:
    ssl._create_default_https_context = _create_unverified_https_context
 

def create_app():
    app = Flask(__name__)

    app.config['SQLALCHEMY_DATABASE_URI'] = os.getenv('POSTGRESQL_CONNECTION_STRING')
    app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
    app.config['JWT_ACCESS_TOKEN_EXPIRES'] = timedelta(hours=1)
    app.config['PERMANENT_SESSION_LIFETIME'] = timedelta(hours=1)
    app.config['JWT_BLACKLIST_ENABLED'] = True
    app.config['JWT_BLACKLIST_TOKEN_CHECKS'] = ['access']
    app.config['SECRET_KEY'] = os.getenv('SECRET_KEY')
    app.config["JWT_SECRET_KEY"] = os.getenv('SECRET_KEY')

    langchain.verbose = False

    CORS(app, supports_credentials=True)
    bcrypt.init_app(app)
    jwt = JWTManager(app)

    def check_basic_auth(username, password):
        admin = (
            db.session.query(AdminUser)
            .filter(AdminUser.username == username, AdminUser.is_active == True)
            .first()
        )

        if not admin:
            return False

        return admin.check_password(password)


    def basic_auth_prompt():
        return Response(
            "Login required",
            401,
            {"WWW-Authenticate": 'Basic realm="Admin Login"'}
        )

    @app.before_request
    def protect_admin():
        if not request.path.startswith("/ollieadmin"):
            return

        try:
            verify_jwt_in_request()
            g.admin_identity = None
            return
        except Exception:
            pass

        auth = request.authorization
        if not auth or not check_basic_auth(auth.username, auth.password):
            return basic_auth_prompt()

        # Basic auth succeeded for this request
        g.admin_identity = auth.username

    @app.after_request
    def set_admin_jwt_cookie(response):
        if getattr(g, "admin_identity", None):
            access_token = create_access_token(identity=g.admin_identity)
            set_access_cookies(response, access_token)
        return response

    return app


def register_blueprints(app):
    app.register_blueprint(search_routes_bp)


def setup_database(app):
    with app.app_context():
        db.init_app(app)
        db.create_all()
        load_models()


def setup_admin(app):
    admin = Admin(app, name='ollie', url="/ollieadmin")
    models = get_models()
    admin.add_view(LocationModelView(
        models.location, db.session, embeddings_model))
    admin.add_view(DocumentModelView(models.local_resources,
                   db.session, embeddings_model, s3))
    admin.add_view(DocumentModelView(models.video_spotlights,
                    db.session, embeddings_model, s3))
    admin.add_view(DocumentModelView(models.quick_tips,
                    db.session, embeddings_model, s3))
    admin.add_view(DocumentModelView(models.infographics,
                    db.session, embeddings_model, s3))
    admin.add_view(ModelView(models.islands, db.session))


app = create_app()
setup_database(app)
setup_admin(app)
register_blueprints(app)
socketio.init_app(app)

if __name__ == "__main__":
    socketio.run(app, host="0.0.0.0", port=5050)
