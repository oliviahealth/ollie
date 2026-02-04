from langchain_postgres import PGVector

# Build native pg retriever for the langchain_pg_embedding table
def build_pg_vector_retriever(collection_name, embeddings_model, connection_uri):
    pg_vector_store = PGVector(
        embeddings=embeddings_model,
        collection_name=collection_name,
        connection=connection_uri,
        use_jsonb=True,
    )

    pg_vector_retriever = pg_vector_store.as_retriever(search_type="mmr")

    return pg_vector_retriever