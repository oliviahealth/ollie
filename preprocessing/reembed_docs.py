import csv
import os
import sys
from pathlib import Path

from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from utils.openai_provider import get_embeddings_model


CSV_PATH = os.getenv("LANGCHAIN_PG_EMBEDDING_CSV_PATH", "data/langchain_pg_embedding_rows.csv")
DATABASE_URI = os.getenv("POSTGRESQL_CONNECTION_STRING")
BATCH_SIZE = int(os.getenv("LANGCHAIN_PG_EMBEDDING_BATCH_SIZE", "50"))
ERROR_LOG_PATH = os.getenv(
    "LANGCHAIN_PG_EMBEDDING_ERROR_LOG",
    "preprocessing/reembed_langchain_pg_embedding_errors.txt",
)


def load_rows(csv_path):
    with open(csv_path, newline="", encoding="utf-8") as handle:
        reader = csv.DictReader(handle)
        for row in reader:
            yield row


def count_rows(csv_path):
    with open(csv_path, newline="", encoding="utf-8") as handle:
        return sum(1 for _ in csv.DictReader(handle))


def rebuild_embeddings(csv_path, database_uri):
    engine = create_engine(database_uri)
    Session = sessionmaker(bind=engine)
    session = Session()
    embeddings_model = get_embeddings_model()
    total = count_rows(csv_path)
    processed = 0
    failed = 0
    pending = 0

    try:
        with open(ERROR_LOG_PATH, "w", encoding="utf-8") as error_log:
            for row in load_rows(csv_path):
                row_id = row.get("id")
                document = row.get("document")

                if not row_id or not document:
                    failed += 1
                    error_log.write(f"{row_id or '[missing-id]'}: missing document\n")
                    continue

                try:
                    embedding = embeddings_model.embed_query(document)

                    session.execute(
                        text(
                            "UPDATE langchain_pg_embedding "
                            "SET embedding = :embedding "
                            "WHERE id = :id"
                        ),
                        {"embedding": embedding, "id": row_id},
                    )

                    processed += 1
                    pending += 1
                    if pending >= BATCH_SIZE:
                        session.commit()
                        pending = 0
                        print(f"Committed {processed} rows")

                    remaining = total - processed - failed
                    print(f"Rebuilt embedding for {row_id} ({remaining} remaining)")
                except Exception as exc:
                    session.rollback()
                    failed += 1
                    error_log.write(f"{row_id}: {exc}\n")
                    print(f"Skipped {row_id}: {exc}")

            if pending:
                session.commit()

        print(f"Done. processed={processed} failed={failed} errors={ERROR_LOG_PATH}")
    finally:
        session.close()


if __name__ == "__main__":
    if not DATABASE_URI:
        raise RuntimeError("POSTGRESQL_CONNECTION_STRING is not set")

    rebuild_embeddings(CSV_PATH, DATABASE_URI)