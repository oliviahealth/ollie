import os
import ssl
from flask import Flask
from flask_cors import CORS
from dotenv import load_dotenv
from flask_jwt_extended import JWTManager
import langchain
from datetime import timedelta

from socketio_instance import socketio
from database import db, bcrypt, revoked_tokens
from routes.search_routes import search_routes_bp

load_dotenv()

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
    app.config['SECRET_KEY'] = os.getenv('SECRET_KEY')  # Change this

    langchain.verbose = False
    
    CORS(app, supports_credentials=True)
    bcrypt.init_app(app)
    jwt = JWTManager(app)
    
    register_extensions(app)
    register_blueprints(app)

    @jwt.token_in_blocklist_loader
    def check_if_token_in_blocklist(jwt_header, jwt_payload):
        return jwt_payload["jti"] in revoked_tokens

    return app

def register_extensions(app):
    db.init_app(app)  

def register_blueprints(app):
    app.register_blueprint(search_routes_bp)

def setup_database(app):
    with app.app_context():
        db.create_all()

app = create_app()
setup_database(app)
socketio.init_app(app)

if __name__ == "__main__":
    socketio.run(app, host="0.0.0.0", port=5050)