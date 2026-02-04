import os
import glob
from datetime import datetime

from langchain.text_splitter import NLTKTextSplitter
from langchain.document_loaders import TextLoader
from langchain_postgres import PGVector
from langchain_postgres.vectorstores import PGVector
from langchain.embeddings import OpenAIEmbeddings

def load_docs(embeddings_model, documents_path, collection_name, database_uri):
    '''
    Loads vectorized knowledge base embeddings into vector database (PGVector).

    Iterates through knowledge base, calculates 1536 dimensional vector embeddings for each document and stores them in vector database.

    Chunk size is currently set to 200 with an overlap of 0. This may have to be adjusted in the future.

    Note: This function calls OpenAIEmbeddings() which costs money to run and can be fairly expensive so try to limit this operation.
          Ideally, the vector database should only need to be loaded initially and whenever we have new data
    '''
    
    text_splitter = NLTKTextSplitter()

    file_paths = glob.glob(os.path.join(documents_path, '**', '*.txt'), recursive=True)

    vector_store = PGVector(
        embeddings=embeddings_model,
        collection_name=collection_name,
        connection=database_uri,
        use_jsonb=True,
    )

    # Process each file
    for file_path in file_paths:
        try:
            # Load and split the document
            loader = TextLoader(file_path)
            docs = loader.load_and_split(text_splitter=text_splitter)

            # Add documents to the vector store
            vector_store.add_documents(docs)

            print(f"Processed {file_path}")
        except Exception as e:
            print(f"Error processing {file_path}: {e}")

docs_path = "./knowledge_base/"
collection_name = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
database_uri = os.getenv("POSTGRESQL_CONNECTION_STRING")

# Using OpenAI embeddings for now
openai_api_key = os.getenv("OPENAI_API_KEY")
embeddings_model = OpenAIEmbeddings(openai_api_key=openai_api_key)

load_docs(embeddings_model=embeddings_model, documents_path=docs_path, collection_name=collection_name, database_uri=database_uri)