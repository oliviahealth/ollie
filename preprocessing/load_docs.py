import os
import glob
import uuid
from datetime import datetime
from io import BytesIO
from pdf2image import convert_from_bytes
from PIL import Image
import pytesseract

from langchain_core.documents import Document
from langchain.text_splitter import NLTKTextSplitter
from langchain.document_loaders import TextLoader
from langchain_postgres import PGVector
from langchain_postgres.vectorstores import PGVector
from langchain.embeddings import OpenAIEmbeddings

text_splitter = NLTKTextSplitter()

def transcribe_image(image) -> str:
    try:
        return pytesseract.image_to_string(image)
    except Exception as e:
        print(f"Error during transcription: {e}")
        return ""

def extract_text_from_pdf_bytes(file_bytes: bytes, filename: str) -> str:
    images = convert_from_bytes(file_bytes)
    full_transcription = ""

    for i, image in enumerate(images):
        print(f"Transcribing {filename} page {i + 1}...")
        transcription = transcribe_image(image)
        full_transcription += transcription + "\n"

    return full_transcription.strip()

def extract_text_from_image_bytes(file_bytes: bytes) -> str:
    with Image.open(BytesIO(file_bytes)) as img:
        return transcribe_image(img).strip()


def load_doc(embeddings_model, collection_name, database_uri, doc_id, filename, file_bytes):
    """
    Loads vectorized knowledge base embeddings into PGVector for a single uploaded file bytes.

    Supports:
    - .pdf via OCR
    - .txt via utf-8 decode
    - .jpg / .jpeg / .png via OCR

    Returns:
        list[str]: embedding IDs for the created chunks
    """

    text_splitter = NLTKTextSplitter()

    vector_store = PGVector(
        embeddings=embeddings_model,
        collection_name=collection_name,
        connection=database_uri,
        use_jsonb=True,
    )

    try:
        lower_name = filename.lower()

        if lower_name.endswith(".pdf"):
            text = extract_text_from_pdf_bytes(file_bytes, filename)
        elif lower_name.endswith(".txt"):
            text = file_bytes.decode("utf-8")
        elif lower_name.endswith((".jpg", ".jpeg", ".png")):
            text = extract_text_from_image_bytes(file_bytes)
        else:
            raise ValueError(f"Unsupported file type: {filename}")

        if not text.strip():
            raise ValueError(f"No readable text found in {filename}")

        metadata = {
            "source": {
                "id": str(doc_id) ,
                "path": filename
            }
        }

        base_doc = Document(
            page_content=text,
            metadata=metadata
        )

        docs = text_splitter.split_documents([base_doc])

        embedding_ids = [uuid.uuid4() for _ in docs]
        vector_store.add_documents(docs, ids=embedding_ids)

        print(f"Processed Document {filename}")
        return embedding_ids

    except Exception as e:
        print(f"Error processing Document {filename}: {e}")
        return []

def load_docs(embeddings_model, documents_path, collection_name, database_uri):
    '''
    Loads vectorized knowledge base embeddings into vector database (PGVector).

    Iterates through knowledge base, calculates 1536 dimensional vector embeddings for each document and stores them in vector database.

    Chunk size is currently set to 200 with an overlap of 0. This may have to be adjusted in the future.

    Note: This function calls OpenAIEmbeddings() which costs money to run and can be fairly expensive so try to limit this operation.
          Ideally, the vector database should only need to be loaded initially and whenever we have new data
    '''

    file_paths = glob.glob(os.path.join(
        documents_path, '**', '*.txt'), recursive=True)

    vector_store = PGVector(
        embeddings=embeddings_model,
        collection_name=collection_name,
        connection=database_uri,
        use_jsonb=True,
    )

    # Process each file
    for file_path in file_paths:
        try:
            loader = TextLoader(file_path)
            docs = loader.load_and_split(text_splitter=text_splitter)

            for doc in docs:
                doc.metadata = {
                    "source": {
                        "id": str(uuid.uuid4()),
                        "path": f"./{file_path}"
                    }
                }

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

# load_docs(embeddings_model=embeddings_model, documents_path=docs_path,
#           collection_name=collection_name, database_uri=database_uri)
