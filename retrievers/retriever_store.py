import threading
import os

from retrievers.PGVectorRetriever import build_pg_vector_retriever
from retrievers.TableColumnRetriever import build_table_column_retriever
from utils.openai_provider import get_embeddings_model

connection_uri = os.getenv("POSTGRES_DSN")
langchain_pg_collection_name = os.getenv("LANGCHAIN_PG_COLLECTION_NAME")

embeddings_provider = get_embeddings_model()

table_column_retriever = None
pg_vector_retriever = None

_pg_vector_retriever_rebuild_version = 0
_table_column_retriever_rebuild_version = 0

_pg_vector_retriever_lock = threading.Lock()
_table_column_retriever_lock = threading.Lock()

def rebuild_pg_vector_retriever(version):
    new_retriever = build_pg_vector_retriever(langchain_pg_collection_name, embeddings_provider, connection_uri)

    with _pg_vector_retriever_lock:
        if version != _pg_vector_retriever_rebuild_version:
            print(f"Skipping outdated rebuild (version {version})")
            return
        
    with _pg_vector_retriever_lock:
        global pg_vector_retriever
        
        pg_vector_retriever = new_retriever

    print(f"PG Vector retriever rebuilt successfully (version {version})")
    
def rebuild_table_column_retriever(version):
    new_retriever = build_table_column_retriever(
        connection_uri=connection_uri,
        table_name="location",
    )

    # only apply if this is still the latest rebuild
    with _table_column_retriever_lock:
        if version != _table_column_retriever_rebuild_version:
            print(f"Skipping outdated rebuild (version {version})")
            return

    with _table_column_retriever_lock:
        global table_column_retriever
        
        table_column_retriever = new_retriever

    print(f"Table-column retriever rebuilt successfully (version {version})")

def rebuild_pg_vector_retriever_async():
    global _pg_vector_retriever_rebuild_version

    with _pg_vector_retriever_lock:
        _pg_vector_retriever_rebuild_version += 1
        current_version = _pg_vector_retriever_rebuild_version

    thread = threading.Thread(
        target=rebuild_pg_vector_retriever,
        args=(current_version,),
        daemon=True
    )

    thread.start()

def rebuild_table_column_retriever_async():
    global _table_column_retriever_rebuild_version
    
    # increment version → invalidates any in-progress rebuild
    with _table_column_retriever_lock:
        _table_column_retriever_rebuild_version += 1
        current_version = _table_column_retriever_rebuild_version

    thread = threading.Thread(
        target=rebuild_table_column_retriever,
        args=(current_version,),
        daemon=True,
    )
    thread.start()
