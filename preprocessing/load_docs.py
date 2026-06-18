import os
import glob
import uuid
from datetime import datetime
from io import BytesIO
from pdf2image import convert_from_bytes
from PIL import Image
import pytesseract
import tempfile
from pathlib import Path

import speech_recognition as sr
from moviepy import VideoFileClip, AudioFileClip

from langchain_core.documents import Document
from langchain.text_splitter import NLTKTextSplitter
from langchain.document_loaders import TextLoader
from langchain_postgres import PGVector
from langchain_postgres.vectorstores import PGVector

from utils.openai_provider import get_embeddings_model

text_splitter = NLTKTextSplitter()
embeddings_model = get_embeddings_model()

def transcribe_image(image):
    try:
        return pytesseract.image_to_string(image)
    except Exception as e:
        print(f"Error during transcription: {e}")
        return ""


def extract_text_from_pdf_bytes(file_bytes, filename):
    images = convert_from_bytes(file_bytes)
    full_transcription = ""

    for i, image in enumerate(images):
        print(f"Transcribing {filename} page {i + 1}...")
        transcription = transcribe_image(image)
        full_transcription += transcription + "\n"

    return full_transcription.strip()


def extract_text_from_image_bytes(file_bytes):
    with Image.open(BytesIO(file_bytes)) as img:
        return transcribe_image(img).strip()


def extract_text_from_video_bytes(file_bytes, filename):
    """
    Extracts spoken text from a video file by:
    1. Writing the video bytes to a temporary file
    2. Extracting audio to a temporary .wav file
    3. Transcribing the audio with speech_recognition

    Supports common video formats such as .mp4 and .mov.
    """
    recognizer = sr.Recognizer()
    suffix = Path(filename).suffix.lower()

    with tempfile.NamedTemporaryFile(suffix=suffix, delete=True) as temp_video_file:
        temp_video_file.write(file_bytes)
        temp_video_file.flush()

        with tempfile.NamedTemporaryFile(suffix=".wav", delete=True) as temp_audio_file:
            temp_audio_path = temp_audio_file.name

            video = None
            try:
                video = VideoFileClip(temp_video_file.name)

                if video.audio is None:
                    raise ValueError(
                        f"No audio track found in video: {filename}")

                video.audio.write_audiofile(
                    temp_audio_path, logger=None)

                with sr.AudioFile(temp_audio_path) as source:
                    audio = recognizer.record(source)

                try:
                    text = recognizer.recognize_google(audio)
                except sr.UnknownValueError:
                    raise ValueError(
                        f"Could not understand audio in video: {filename}")
                except sr.RequestError as e:
                    raise ValueError(
                        f"Speech recognition request failed for {filename}: {e}")

                return text

            finally:
                if video is not None:
                    video.close()


def extract_text_from_audio_bytes(file_bytes: bytes, filename: str) -> str:
    """
    Extracts spoken text from an audio file.

    Supports:
    - .wav directly through speech_recognition
    - .mp3 / .m4a by converting to temporary .wav first
    """
    recognizer = sr.Recognizer()
    suffix = Path(filename).suffix.lower()

    # WAV can be read directly by speech_recognition
    if suffix == ".wav":
        with tempfile.NamedTemporaryFile(suffix=".wav", delete=True) as temp_audio_file:
            temp_audio_file.write(file_bytes)
            temp_audio_file.flush()

            with sr.AudioFile(temp_audio_file.name) as source:
                audio = recognizer.record(source)

            try:
                return recognizer.recognize_google(audio)
            except sr.UnknownValueError:
                raise ValueError(
                    f"Could not understand audio in file: {filename}")
            except sr.RequestError as e:
                raise ValueError(
                    f"Speech recognition request failed for {filename}: {e}")

    # MP3 / M4A need conversion to WAV first
    elif suffix in (".mp3", ".m4a"):
        with tempfile.NamedTemporaryFile(suffix=suffix, delete=True) as temp_input_file:
            temp_input_file.write(file_bytes)
            temp_input_file.flush()

            with tempfile.NamedTemporaryFile(suffix=".wav", delete=True) as temp_wav_file:
                temp_wav_path = temp_wav_file.name

                try:
                    audio_clip = AudioFileClip(temp_input_file.name)
                    audio_clip.write_audiofile(temp_wav_path, logger=None)
                    audio_clip.close()

                    with sr.AudioFile(temp_wav_path) as source:
                        audio = recognizer.record(source)

                    try:
                        return recognizer.recognize_google(audio)
                    except sr.UnknownValueError:
                        raise ValueError(
                            f"Could not understand audio in file: {filename}")
                    except sr.RequestError as e:
                        raise ValueError(
                            f"Speech recognition request failed for {filename}: {e}")

                except Exception as e:
                    raise ValueError(
                        f"Failed to process audio file {filename}: {e}")

    else:
        raise ValueError(f"Unsupported audio file type: {filename}")


def load_doc(embeddings_model, collection_name, database_uri, doc_id, filename, file_bytes):
    """
    Loads vectorized knowledge base embeddings into PGVector for a single uploaded file.

    Supports:
    - .pdf via OCR
    - .txt via utf-8 decode
    - .jpg / .jpeg / .png via OCR
    - .mp4 / .mov via audio transcription
    - .mp3 / .wav / .m4a via audio transcription

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

        elif lower_name.endswith((".mp4", ".mov")):
            text = extract_text_from_video_bytes(file_bytes, filename)

        elif lower_name.endswith((".mp3", ".wav", ".m4a")):
            text = extract_text_from_audio_bytes(file_bytes, filename)

        else:
            raise ValueError(f"Unsupported file type: {filename}")

        if not text or not text.strip():
            raise ValueError(f"No readable text found in {filename}")

        metadata = {
            "source": {
                "id": str(doc_id),
                "path": filename,
            }
        }

        base_doc = Document(
            page_content=text,
            metadata=metadata,
        )

        docs = text_splitter.split_documents([base_doc])

        embedding_ids = [str(uuid.uuid4()) for _ in docs]
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

# load_docs(embeddings_model=embeddings_model, documents_path=docs_path,
#           collection_name=collection_name, database_uri=database_uri)
