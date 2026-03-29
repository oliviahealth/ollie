from flask_sqlalchemy import SQLAlchemy
from sqlalchemy.types import UserDefinedType
from sqlalchemy.dialects.postgresql import UUID

init_db = SQLAlchemy()


class Vector(UserDefinedType):
    def get_col_spec(self):
        return "VECTOR(1536)"

    def bind_expression(self, bindvalue):
        return bindvalue

    def column_expression(self, col):
        return col


class message_store(init_db.Model):
    __tablename__ = "message_store"

    id = init_db.Column(init_db.Integer(), primary_key=True)
    session_id = init_db.Column(init_db.String(), nullable=False)
    message = init_db.Column(init_db.String(), nullable=False)


class Location(init_db.Model):
    __tablename__ = "location"

    id = init_db.Column(
        init_db.String(),
        primary_key=True,
        server_default=init_db.text("gen_random_uuid()::text")
    )
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


class LocalResources(init_db.Model):
    __tablename__ = "local_resources"

    id = init_db.Column(
        init_db.String(),
        primary_key=True,
        server_default=init_db.text("gen_random_uuid()::text")
    )
    title = init_db.Column(init_db.String(), nullable=False)
    subtitle = init_db.Column(init_db.String(), nullable=True)
    video_url = init_db.Column(init_db.String(), nullable=True)
    video_id = init_db.Column(init_db.String(), nullable=True)
    transcript = init_db.Column(init_db.String(), nullable=True)
    thumbnail_url = init_db.Column(init_db.String(), nullable=True)
    url = init_db.Column(init_db.String(), nullable=False)
    path = init_db.Column(init_db.String(), nullable=True)

    langchain_pg_embeddings = init_db.relationship(
        "LangchainPGEmbedding",
        back_populates="local_resource",
        passive_deletes=True,
    )


class LangchainPGCollection(init_db.Model):
    __tablename__ = "langchain_pg_collection"

    uuid = init_db.Column(UUID(as_uuid=True), primary_key=True)
    name = init_db.Column(init_db.Text())
    cmetadata = init_db.Column(init_db.JSON())

    embeddings = init_db.relationship(
        "LangchainPGEmbedding",
        back_populates="collection",
        passive_deletes=True,
    )


class LangchainPGEmbedding(init_db.Model):
    __tablename__ = "langchain_pg_embedding"

    id = init_db.Column(UUID(as_uuid=True), primary_key=True)
    collection_id = init_db.Column(
        UUID(as_uuid=True),
        init_db.ForeignKey("langchain_pg_collection.uuid", ondelete="CASCADE"),
        nullable=True,
    )
    embedding = init_db.Column(Vector(), nullable=True)
    document = init_db.Column(init_db.Text(), nullable=True)
    cmetadata = init_db.Column(init_db.JSON(), nullable=True)

    resource_id = init_db.Column(init_db.String(), nullable=True, index=True)

    collection = init_db.relationship(
        "LangchainPGCollection",
        back_populates="embeddings",
    )