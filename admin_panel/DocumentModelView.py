from flask_admin.contrib.sqla import ModelView
from wtforms import FileField
from sqlalchemy import text
import uuid
import os

from preprocessing.load_docs import load_doc

database_uri = os.getenv("POSTGRESQL_CONNECTION_STRING")
LANGCHAIN_PG_COLLECTION_NAME = os.getenv("LANGCHAIN_PG_COLLECTION_NAME")

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
            raise ValueError("File missing")

        # get the existing id if this is an update or generate a new id
        id = str(model.id) if (not is_created and model.id) else None

        if is_created:
            id = uuid.uuid4()
            model.id = id

        if not id:
            raise ValueError("ID Error")

        embedding_ids = load_doc(
            self.embeddings_model,
            LANGCHAIN_PG_COLLECTION_NAME,
            database_uri,
            id,
            file,
        )

        self.session.add(model)
        self.session.flush()

        if not embedding_ids:
            raise ValueError("Error generating embedding ids")

        try:
            # delete old records if update
            if not is_created:
                self.session.execute(
                    text("""
                        DELETE FROM langchain_pg_embedding
                        WHERE local_resource_id = :resource_id
                    """),
                    {"resource_id": id},
                )

            # Link langchain_pg_embedding with location_resources
            if embedding_ids:
                self.session.execute(
                    text("""
                        UPDATE langchain_pg_embedding
                        SET local_resource_id = :resource_id
                        WHERE id = ANY(CAST(:embedding_ids AS uuid[]))
                    """),
                    {
                        "resource_id": str(model.id),
                        "embedding_ids": [str(eid) for eid in embedding_ids],
                    },
                )

        except Exception:
            # cleanup embeddings created by load_doc on failure
            if embedding_ids:
                try:
                    self.session.execute(
                        text("""
                            DELETE FROM langchain_pg_embedding
                            WHERE id = ANY(CAST(:embedding_ids AS uuid[]))
                        """),
                        {"embedding_ids": [str(eid) for eid in embedding_ids]},
                    )
                    self.session.flush()
                except Exception:
                    pass
            
            # reraise exception
            raise

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
