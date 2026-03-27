from flask_admin.contrib.sqla import ModelView
from wtforms import FileField
from sqlalchemy import text
from io import BytesIO
import uuid
import os

from preprocessing.load_docs import load_doc

database_uri = os.getenv("POSTGRESQL_CONNECTION_STRING")
s3_bucket_name = os.getenv("AWS_S3_BUCKET_NAME")
LANGCHAIN_PG_COLLECTION_NAME = os.getenv("LANGCHAIN_PG_COLLECTION_NAME")


class DocumentModelView(ModelView):
    form_extra_fields = {
        "upload": FileField("Upload File")
    }
    form_excluded_columns = ("langchain_pg_embedding_collection", "path")

    def __init__(self, model, session, embeddings_model, s3, **kwargs):
        super().__init__(model, session, **kwargs)
        self.embeddings_model = embeddings_model
        self.s3 = s3

    def _upload_s3_resource(self, file_bytes, file_content_type, s3_key):
        self.s3.upload_fileobj(
            BytesIO(file_bytes),
            s3_bucket_name,
            s3_key,
            ExtraArgs={
                "ContentType": file_content_type
            }
        )

        s3_resource_url = f"https://{s3_bucket_name}.s3.amazonaws.com/{s3_key}"

        return s3_resource_url

    def _delete_s3_resource(self, s3_key):
        self.s3.delete_object(
            Bucket=s3_bucket_name,
            Key=s3_key
        )

    def on_model_change(self, form, model, is_created):
        file = form.upload.data
        file.stream.seek(0)

        if not file or not getattr(file, "filename", None):
            raise ValueError("File missing")

        filename = file.filename
        file_bytes = file.read()
        content_type = file.mimetype or "application/octet-stream"
        embedding_ids = None

        # get the existing id if this is an update or generate a new id
        id = str(model.id) if (not is_created and model.id) else None

        if is_created:
            id = uuid.uuid4()
            model.id = id

        if not id:
            raise ValueError("ID Error")

        s3_key = f"local_resources/{id}-{filename}"

        try:
            # upload file to s3 and link with model
            s3_resource_url = self._upload_s3_resource(
                file_bytes, content_type, s3_key)
            model.path = s3_resource_url

            # parse and generate embeddings
            embedding_ids = load_doc(
                self.embeddings_model,
                LANGCHAIN_PG_COLLECTION_NAME,
                database_uri,
                id,
                filename,
                file_bytes,
            )

            if not embedding_ids:
                raise ValueError("Error generating embedding ids")

            self.session.add(model)
            self.session.flush()

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

                    if model.path:
                        self._delete_s3_resource(s3_key)
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
        if model.path:
            self._delete_s3_resource(model.path.split(".amazonaws.com/")[1])
            
        print("Deleted successfully")
