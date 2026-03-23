from flask_sqlalchemy import SQLAlchemy
from sqlalchemy.types import UserDefinedType
import uuid

init_db = SQLAlchemy()

class Vector(UserDefinedType):
    def get_col_spec(self):
        return "VECTOR(1536)"

    def bind_expression(self, bindvalue):
        return bindvalue

    def column_expression(self, col):
        return col
    
class message_store(init_db.Model):
    id = init_db.Column(init_db.Integer(), primary_key=True)
    session_id = init_db.Column(init_db.String(), nullable=False)
    message = init_db.Column(init_db.String(), nullable=False)

class Location(init_db.Model):
    id = init_db.Column(init_db.String(), primary_key=True, default=lambda: str(uuid.uuid4()))
    name = init_db.Column(init_db.String(), nullable=False, unique=True)
    address = init_db.Column(init_db.String(), nullable=False)
    city = init_db.Column(init_db.String(), nullable=False)
    state = init_db.Column(init_db.String(), nullable=False)
    country = init_db.Column(init_db.String(), nullable=False)
    zip_code = init_db.Column(init_db.String(), nullable=False)
    county = init_db.Column(init_db.String(), nullable=False)
    latitude = init_db.Column(init_db.Float(), nullable=False)
    longitude = init_db.Column(init_db.Float(), nullable=False)
    description = init_db.Column(init_db.String(), nullable=False)
    phone = init_db.Column(init_db.String(), nullable=False)
    sunday_hours = init_db.Column(init_db.String(), nullable=False)
    monday_hours = init_db.Column(init_db.String(), nullable=False)
    tuesday_hours = init_db.Column(init_db.String(), nullable=False)
    wednesday_hours = init_db.Column(init_db.String(), nullable=False)
    thursday_hours = init_db.Column(init_db.String(), nullable=False)
    friday_hours = init_db.Column(init_db.String(), nullable=False)
    saturday_hours = init_db.Column(init_db.String(), nullable=False)
    rating = init_db.Column(init_db.String(), nullable=True)
    address_link = init_db.Column(init_db.String(), nullable=True)
    website = init_db.Column(init_db.String(), nullable=False)
    resource_type = init_db.Column(init_db.String(), nullable=False)
    embedding = init_db.Column(Vector(), nullable=True)