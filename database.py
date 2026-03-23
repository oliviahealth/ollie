from flask_sqlalchemy import SQLAlchemy
from sqlalchemy.ext.automap import automap_base
from flask_bcrypt import Bcrypt

db = SQLAlchemy()
bcrypt = Bcrypt()
revoked_tokens = set()

Base = automap_base()
models = None

# Dynamically load schemas from database
def load_models():
    global models
    Base.prepare(autoload_with=db.engine)
    models = Base.classes
    return models

# Use this to access models
def get_models():
    if models is None:
        raise RuntimeError("Models have not been loaded yet. Call load_models() first.")
    return models