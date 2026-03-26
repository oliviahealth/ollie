from flask_admin.contrib.sqla import ModelView
from wtforms import FileField
from sqlalchemy import text
import uuid
import os

from langchain.embeddings import OpenAIEmbeddings
from preprocessing.load_docs import load_doc

openai_api_key = os.getenv("OPENAI_API_KEY")
database_uri = os.getenv("POSTGRESQL_CONNECTION_STRING")
LANGCHAIN_PG_COLLECTION_NAME = os.getenv("LANGCHAIN_PG_COLLECTION_NAME")

embeddings_model = OpenAIEmbeddings(openai_api_key=openai_api_key)

class DocumentModelView(ModelView):
    form_extra_fields = {
        "upload": FileField("Upload File")
    }
    form_excluded_columns = ("collection_id",)
   
    def __init__(self, model, session, embeddings_model, **kwargs):
        super().__init__(model, session, **kwargs)
        self.embeddings_model = embeddings_model

    def on_model_change(self, form, model, is_created):
        file = form.upload.data

        if not file or not getattr(file, "filename", None):
            return
            
        res = load_doc(
            embeddings_model,
            LANGCHAIN_PG_COLLECTION_NAME,
            database_uri,
            file,
        )

        id = res.get('id')
        embedding_ids = res.get('embedding_ids')

        model.id = str(id)

        self.session.add(model)
        self.session.flush()

        if not embedding_ids:
            return

        # Delete old embeddings on update
        if not is_created:
            self.session.execute(
                text("""
                DELETE FROM langchain_pg_embedding
                WHERE local_resource_id = :resource_id
                """),
                {"resource_id": str(model.id)},
            )

        self.session.execute(
            text("""
            UPDATE langchain_pg_embedding
            SET local_resource_id = :resource_id
            WHERE id = ANY(:embedding_ids)
            """),
            {
                "resource_id": str(model.id),
                "embedding_ids": embedding_ids,
            },
        )

        # example: modify fields before save
        # model.updated_by = current_user.email

    def after_model_change(self, form, model, is_created):
        # runs after commit on both create and edit
        if is_created:
            print("Created successfully")
        else:
            print("Updated successfully")

    def on_model_delete(self, model):
        # runs before delete commit
        print("Deleting record")

    def after_model_delete(self, model):
        # runs after delete commit
        print("Deleted successfully")
