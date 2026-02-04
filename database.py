from flask_sqlalchemy import SQLAlchemy
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.types import UserDefinedType
from flask_bcrypt import Bcrypt
import uuid

db = SQLAlchemy()
bcrypt = Bcrypt()
revoked_tokens = set()

class Vector(UserDefinedType):
    def get_col_spec(self):
        return "VECTOR(1536)"

    def bind_expression(self, bindvalue):
        return bindvalue

    def column_expression(self, col):
        return col
    
class message_store(db.Model):
    id = db.Column(db.Integer(), primary_key=True)
    session_id = db.Column(db.String(), nullable=False)
    message = db.Column(db.String(), nullable=False)

class Location(db.Model):
    id = db.Column(db.String(), primary_key=True, default=lambda: str(uuid.uuid4()))
    name = db.Column(db.String(), nullable=False, unique=True)
    address = db.Column(db.String(), nullable=False)
    city = db.Column(db.String(), nullable=False)
    state = db.Column(db.String(), nullable=False)
    country = db.Column(db.String(), nullable=False)
    zip_code = db.Column(db.String(), nullable=False)
    county = db.Column(db.String(), nullable=False)
    latitude = db.Column(db.Float(), nullable=False)
    longitude = db.Column(db.Float(), nullable=False)
    description = db.Column(db.String(), nullable=False)
    phone = db.Column(db.String(), nullable=False)
    sunday_hours = db.Column(db.String(), nullable=False)
    monday_hours = db.Column(db.String(), nullable=False)
    tuesday_hours = db.Column(db.String(), nullable=False)
    wednesday_hours = db.Column(db.String(), nullable=False)
    thursday_hours = db.Column(db.String(), nullable=False)
    friday_hours = db.Column(db.String(), nullable=False)
    saturday_hours = db.Column(db.String(), nullable=False)
    rating = db.Column(db.String(), nullable=True)
    address_link = db.Column(db.String(), nullable=True)
    website = db.Column(db.String(), nullable=False)
    resource_type = db.Column(db.String(), nullable=False)
    embedding = db.Column(Vector(), nullable=True)