import os
import subprocess

from flask import Flask
from dotenv import load_dotenv
from sqlalchemy import text

from init_database import init_db

load_dotenv()

DATABASE_URL = os.getenv("POSTGRES_DSN")

# Seed CSVs are mounted into the init container at /seed/*
COLLECTION_CSV_PATH = "/seed/langchain_pg_collection_rows.csv"
EMBEDDING_CSV_PATH = "/seed/langchain_pg_embedding_rows.csv"
LOCATION_CSV_PATH = "/seed/location_rows.csv"
LOCAL_RESOURCES_CSV_PATH = "/seed/local_resource_rows.csv"


def create_minimal_app():
    app = Flask(__name__)
    app.config["SQLALCHEMY_DATABASE_URI"] = DATABASE_URL
    app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False
    init_db.init_app(app)
    return app


def ensure_pgvector_extension():
    with init_db.engine.begin() as conn:
        conn.execute(text("CREATE EXTENSION IF NOT EXISTS vector;"))


def run_psql(sql: str):
    cmd = ["psql", DATABASE_URL, "-v", "ON_ERROR_STOP=1", "-c", sql]
    subprocess.run(cmd, check=True)


def psql_copy(table_name: str, csv_path: str, columns: str | None = None):
    if not os.path.exists(csv_path):
        print(f"⚠️ CSV not found at {csv_path}, skipping seed for {table_name}.")
        return

    cols = f" {columns}" if columns else ""
    sql = (
        f"\\copy {table_name}{cols} "
        f"FROM '{csv_path}' "
        f"WITH (FORMAT csv, HEADER true, NULL 'NULL')"
    )

    run_psql(sql)
    print(f"✅ Seeded {table_name} from {csv_path}")


def reset_tables():
    print("Truncating seed tables...", flush=True)

    run_psql(
        """
        TRUNCATE TABLE
            langchain_pg_embedding,
            langchain_pg_collection,
            local_resources,
            "location",
            message_store
        RESTART IDENTITY CASCADE;
        """
    )

    print("✅ Truncated tables", flush=True)


def seed_location():
    psql_copy('"location"', LOCATION_CSV_PATH)


def seed_local_resources():
    psql_copy(
        "local_resources",
        LOCAL_RESOURCES_CSV_PATH,
        "(id, title, subtitle, video_url, video_id, transcript, thumbnail_url, url, path)",
    )


def seed_langchain_pg_collection():
    psql_copy(
        "langchain_pg_collection",
        COLLECTION_CSV_PATH,
        "(uuid, name, cmetadata)",
    )


def seed_langchain_pg_embedding():
    psql_copy(
        "langchain_pg_embedding",
        EMBEDDING_CSV_PATH,
        "(id, collection_id, embedding, document, cmetadata, resource_id)",
    )


if __name__ == "__main__":
    if not DATABASE_URL:
        raise RuntimeError("POSTGRES_DSN is not set (expected in .env)")

    app = create_minimal_app()

    with app.app_context():
        print("==> Enabling pgvector extension...")
        ensure_pgvector_extension()

        print("==> Creating app tables (SQLAlchemy models)...")
        init_db.create_all()

        print("==> Resetting tables...")
        reset_tables()

        print("==> Seeding location table...")
        seed_location()

        print("==> Seeding local_resources table...")
        seed_local_resources()

        print("==> Seeding langchain_pg_collection...")
        seed_langchain_pg_collection()

        print("==> Seeding langchain_pg_embedding...")
        seed_langchain_pg_embedding()

    print("init_app complete")