import os
from functools import lru_cache

import boto3
from dotenv import load_dotenv
from langchain_aws import BedrockEmbeddings, ChatBedrockConverse

load_dotenv()

chat_model = os.getenv("CHAT_LARGE_MODEL")
small_chat_model = os.getenv("CHAT_SMALL_MODEL")
embedding_model = os.getenv("EMBEDDING_MODEL")
aws_region = os.getenv("AWS_DEFAULT_REGION")

def _env(name, default=None):
    value = os.getenv(name)
    return value if value else default

def _get_bedrock_runtime_client():
    client_kwargs = {
        "service_name": "bedrock-runtime",
        "region_name": aws_region,
    }

    access_key = _env("AWS_ADMIN_ACCESS_KEY_ID")
    secret_key = _env("AWS_ADMIN_SECRET_ACCESS_KEY")
    # session_token = _env("AWS_ADMIN_SESSION_TOKEN")

    if access_key:
        client_kwargs["aws_access_key_id"] = access_key
        client_kwargs["aws_secret_access_key"] = secret_key
        # client_kwargs["aws_session_token"] = session_token

    return boto3.client(**client_kwargs)


@lru_cache(maxsize=1)
def get_chat_model():
    return ChatBedrockConverse(
        model_id=chat_model,
        region_name=aws_region,
        client=_get_bedrock_runtime_client(),
    )

@lru_cache(maxsize=1)
def get_small_chat_model():
    return ChatBedrockConverse(
        model_id=small_chat_model,
        region_name=aws_region,
        client=_get_bedrock_runtime_client(),
    )

@lru_cache(maxsize=1)
def get_embeddings_model():
    return BedrockEmbeddings(
        model_id=embedding_model,
        region_name=aws_region,
        client=_get_bedrock_runtime_client(),
    )