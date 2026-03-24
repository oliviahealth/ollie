import threading
import os
from retrievers.TableColumnRetriever import build_table_column_retriever

connection_uri = os.getenv("POSTGRES_DSN")

table_column_retriever = None

_retriever_lock = threading.Lock()

# versioning
_rebuild_version = 0
_rebuild_version_lock = threading.Lock()

def rebuild_table_column_retriever(version):
    new_retriever = build_table_column_retriever(
        connection_uri=connection_uri,
        table_name="location",
    )

    # only apply if this is still the latest rebuild
    with _rebuild_version_lock:
        if version != _rebuild_version:
            print(f"Skipping outdated rebuild (version {version})")
            return

    with _retriever_lock:
        global table_column_retriever
        
        table_column_retriever = new_retriever

    print(f"Retriever rebuilt successfully (version {version})")

def rebuild_table_column_retriever_async():
    global _rebuild_version
    
    # increment version → invalidates any in-progress rebuild
    with _rebuild_version_lock:
        _rebuild_version += 1
        current_version = _rebuild_version

    thread = threading.Thread(
        target=rebuild_table_column_retriever,
        args=(current_version,),
        daemon=True,
    )
    thread.start()