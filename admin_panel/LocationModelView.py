from flask_admin.contrib.sqla import ModelView
import uuid


class LocationModelView(ModelView):
    def __init__(self, model, session, embeddings_model, **kwargs):
        super().__init__(model, session, **kwargs)
        self.embeddings_model = embeddings_model

    def on_model_change(self, form, model, is_created):
        # runs before commit on both create and edit
        if is_created:
            print("Creating record")
            model.id = str(uuid.uuid4())  # manually assign an id

            form_entries = []

            for key, value in form.data.items():
                form_entries.append(f"{key}={value}")

            text_to_embed = ', '.join(form_entries)

            embedding = self.embeddings_model.embed_query(text_to_embed)

            model.embedding = embedding # assign embedding
        else:
            print("Updating record")

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
