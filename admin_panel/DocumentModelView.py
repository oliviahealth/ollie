from concurrent.futures import ThreadPoolExecutor

from flask_admin.contrib.sqla import ModelView
from wtforms import FileField
from sqlalchemy import text
from io import BytesIO
import uuid
import os

from retrievers.retriever_store import rebuild_pg_vector_retriever_async
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

    def _upload_s3_resource(self, file_id, file_name, file_bytes, file_content_type):
        s3_key = f"{self.model.__table__.name}/{file_id}-{file_name}"

        self.s3.upload_fileobj(
            BytesIO(file_bytes),
            s3_bucket_name,
            s3_key,
            ExtraArgs={
                "ContentType": file_content_type
            }
        )

        return s3_key

    def _delete_s3_resource(self, s3_key):
        self.s3.delete_object(
            Bucket=s3_bucket_name,
            Key=s3_key
        )

    def on_model_change(self, form, model, is_created):
        file = getattr(form.upload, "data", None)

        embedding_ids = None
        s3_resource_url = None

        # keep existing id on update, create new id on create
        resource_id = str(model.id) if (not is_created and model.id) else None

        if is_created:
            resource_id = str(uuid.uuid4())
            model.id = resource_id

        if not resource_id:
            raise ValueError("ID Error")

        # CREATE: file is required
        if is_created:
            if not file or not getattr(file, "filename", None):
                raise ValueError("File missing")

        # UPDATE with no new file: keep existing resource as-is
        if not is_created and (not file or not getattr(file, "filename", None)):
            self.session.add(model)
            self.session.flush()
            return

        file.stream.seek(0)
        filename = file.filename
        file_bytes = file.read()
        content_type = file.mimetype or "application/octet-stream"

        old_path = None
        if not is_created:
            old_path = model.path

        try:
            with ThreadPoolExecutor(max_workers=2) as executor:
                s3_future = executor.submit(
                    self._upload_s3_resource,
                    resource_id,
                    filename,
                    file_bytes,
                    content_type,
                )

                embeddings_future = executor.submit(
                    load_doc,
                    self.embeddings_model,
                    LANGCHAIN_PG_COLLECTION_NAME,
                    database_uri,
                    resource_id,
                    filename,
                    file_bytes,
                )

                s3_resource_url = s3_future.result()
                embedding_ids = embeddings_future.result()

            if not s3_resource_url:
                raise ValueError("Error uploading to s3")

            if not embedding_ids:
                raise ValueError("Error generating embedding ids")

            # on update, delete old embedding rows for this resource before relinking new ones
            if not is_created:
                self.session.execute(
                    text("""
                        DELETE FROM langchain_pg_embedding
                        WHERE resource_id = :resource_id
                    """),
                    {"resource_id": resource_id},
                )

            model.path = s3_resource_url

            self.session.add(model)
            self.session.flush()

            # link new embedding rows to this resource
            self.session.execute(
                text("""
                    UPDATE langchain_pg_embedding
                    SET resource_id = :resource_id
                    WHERE id = ANY(CAST(:embedding_ids AS uuid[]))
                """),
                {
                    "resource_id": resource_id,
                    "embedding_ids": [str(eid) for eid in embedding_ids],
                },
            )

            # optional: delete old S3 object after successful replacement
            if not is_created and old_path and old_path != s3_resource_url:
                try:
                    # if old_path is a full URL, extract key; otherwise assume it's already a key/path
                    old_key = old_path
                    if ".amazonaws.com/" in old_path:
                        old_key = old_path.split(".amazonaws.com/", 1)[1]
                    self._delete_s3_resource(old_key)
                except Exception:
                    pass

        except Exception:
            # cleanup newly created embeddings and uploaded file on failure
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

            if s3_resource_url:
                try:
                    s3_key = s3_resource_url
                    if ".amazonaws.com/" in s3_resource_url:
                        s3_key = s3_resource_url.split(".amazonaws.com/", 1)[1]
                    self._delete_s3_resource(s3_key)
                except Exception:
                    pass

            raise

    def after_model_change(self, form, model, is_created):
        # runs after commit on both create and edit
        rebuild_pg_vector_retriever_async()

        if is_created:
            print("Created successfully")
        else:
            print("Updated successfully")

    def on_model_delete(self, model):
        # runs before delete commit
        self.session.execute(
            text("""
            DELETE FROM langchain_pg_embedding
            WHERE resource_id = :resource_id
        """),
            {"resource_id": str(model.id)},
        )

        print("Deleting record")

    def after_model_delete(self, model):
        # runs after delete commit
        rebuild_pg_vector_retriever_async()

        if model.path:
            self._delete_s3_resource(model.path)

        print("Deleted successfully")
