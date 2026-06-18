import os
from functools import lru_cache

from dotenv import load_dotenv
from langchain_openai import ChatOpenAI, OpenAIEmbeddings


load_dotenv()


def _env(name, default=None):
    value = os.getenv(name)
    return value if value else default


@lru_cache(maxsize=1)
def get_chat_model():
    return ChatOpenAI(
        model=_env("CHAT_MODEL"),
        api_key=_env("TAMU_AI_CHAT_API_KEY"),
        base_url=_env("TAMU_AI_CHAT_BASE_URL"),
    )


@lru_cache(maxsize=1)
def get_embeddings_model():
    return OpenAIEmbeddings(
        model=_env("TAMU_AI_CHAT_EMBEDDING_MODEL"),
        api_key=_env("TAMU_AI_CHAT_API_KEY"),
        base_url=_env("TAMU_AI_CHAT_BASE_URL"),
        check_embedding_ctx_length=False,
    )
