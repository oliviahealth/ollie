import os
import subprocess
from flask import Flask
from dotenv import load_dotenv
from sqlalchemy import text

from database import db

load_dotenv()

# In your .env, this should look like:
DATABASE_URL = os.getenv("POSTGRES_DSN")

# Seed CSVs are mounted into the init container at /seed/*
COLLECTION_CSV_PATH = "/seed/langchain_pg_collection_rows.csv"
EMBEDDING_CSV_PATH = "/seed/langchain_pg_embedding_rows.csv"
LOCATION_CSV_PATH = "/seed/location_rows.csv"


def create_minimal_app():
    app = Flask(__name__)
    app.config["SQLALCHEMY_DATABASE_URI"] = DATABASE_URL
    app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False
    db.init_app(app)
    return app


def ensure_pgvector_extension():
    # pgvector type won't exist until extension is enabled
    with db.engine.begin() as conn:
        conn.execute(text("CREATE EXTENSION IF NOT EXISTS vector;"))


def ensure_langchain_tables():
    """
    Your SQLAlchemy models likely do NOT include LangChain's tables, so db.create_all()
    won't create them. Create them explicitly so \copy can seed them.

    NOTE on types:
      - uuid: UUID
      - cmetadata: JSONB
      - embedding: vector (pgvector)

    NOTE on embedding.id type:
      Many LangChain schemas use UUID. If your CSV's id is NOT a UUID, change
      `id UUID PRIMARY KEY` to `id TEXT PRIMARY KEY`.
    """
    with db.engine.begin() as conn:
        # Collection table
        conn.execute(text("""
        CREATE TABLE IF NOT EXISTS langchain_pg_collection (
            uuid UUID PRIMARY KEY,
            name TEXT,
            cmetadata JSONB
        );
        """))

        # Embedding table
        conn.execute(text("""
        CREATE TABLE IF NOT EXISTS langchain_pg_embedding (
            id UUID PRIMARY KEY,
            collection_id UUID REFERENCES langchain_pg_collection(uuid) ON DELETE CASCADE,
            embedding vector,
            document TEXT,
            cmetadata JSONB
        );
        """))

        # Indexes (helpful for retrieval + filtering by collection)
        conn.execute(text("""
        CREATE INDEX IF NOT EXISTS langchain_pg_embedding_collection_id_idx
        ON langchain_pg_embedding(collection_id);
        """))


def run_psql(sql: str):
    """
    Run a single psql -c statement against DATABASE_URL.
    """
    cmd = ["psql", DATABASE_URL, "-v", "ON_ERROR_STOP=1", "-c", sql]
    subprocess.run(cmd, check=True)


def psql_copy(table_name: str, csv_path: str, columns: str | None = None):
    """
    Uses psql \\copy (client-side) so the CSV only needs to exist in init container.
    columns: optional string like "(col1, col2, ...)" to force column order.
    """
    if not os.path.exists(csv_path):
        print(f"⚠️ CSV not found at {csv_path}, skipping seed for {table_name}.")
        return

    cols = f" {columns}" if columns else ""
    sql = f"\\copy {table_name}{cols} FROM '{csv_path}' WITH (FORMAT csv, HEADER true)"
    run_psql(sql)
    print(f"✅ Seeded {table_name} from {csv_path}")


def reset_tables():
    print("truncating seed tables...", flush=True)

    # Truncate all in one statement to satisfy FK constraints
    run_psql('TRUNCATE TABLE langchain_pg_embedding, langchain_pg_collection, "location" RESTART IDENTITY CASCADE;')

    print("✅ Truncated tables", flush=True)

def seed_location():
    # location is quoted in case it conflicts with reserved words or casing
    psql_copy('"location"', LOCATION_CSV_PATH)

def seed_langchain_pg_collection():
    # Expected CSV header/columns: uuid, name, cmetadata
    psql_copy("langchain_pg_collection", COLLECTION_CSV_PATH, "(uuid, name, cmetadata)")


def seed_langchain_pg_embedding():
    # Expected CSV header/columns: id, collection_id, embedding, document, cmetadata
    psql_copy(
        "langchain_pg_embedding",
        EMBEDDING_CSV_PATH,
        "(id, collection_id, embedding, document, cmetadata)"
    )


if __name__ == "__main__":
    if not DATABASE_URL:
        raise RuntimeError("POSTGRES_DSN is not set (expected in .env)")

    app = create_minimal_app()
    with app.app_context():
        print("==> Enabling pgvector extension...")
        ensure_pgvector_extension()

        print("==> Creating app tables (SQLAlchemy models)...")
        db.create_all()

        print("==> Ensuring LangChain tables exist...")
        ensure_langchain_tables()

        reset_tables()

        print("==> Seeding location table...")
        seed_location()

        print("==> Seeding langchain_pg_collection...")
        seed_langchain_pg_collection()

        print("==> Seeding langchain_pg_embedding...")
        seed_langchain_pg_embedding()

    print("init_db complete")
