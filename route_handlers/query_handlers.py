import json
import os

from typing import Literal, Optional
from pydantic import BaseModel, Field

from chains.conversational_retrieval_chain_with_memory import build_conversational_retrieval_chain_with_memory
from langchain_openai import ChatOpenAI

from socketio_instance import socketio
import retrievers.retriever_store as retriever_store

connection_uri = os.getenv("POSTGRES_DSN")

# 1. Define the structural schema using Pydantic
class SearchClassification(BaseModel):
    function_name: Literal["search_direct_questions", "search_location_questions", "follow_up"] = Field(
        description="The appropriate function strategy to execute based on the user's intent."
    )
    query: str = Field(
        description="The summarized search query. MUST be an empty string if function_name is 'follow_up'."
    )
    response: Optional[str] = Field(
        default="",
        description="The user-facing follow-up response message. Only required if function_name is 'follow_up'."
    )

llm = ChatOpenAI(
    model=os.getenv("CHAT_MODEL"),
    api_key=os.getenv("TAMU_AI_CHAT_API_KEY"),
    base_url=os.getenv("TAMU_AI_CHAT_BASE_URL")
)

structured_classifier = llm.with_structured_output(
    SearchClassification,
    method="json_schema",
    strict=True,
)

def search_direct_questions(conversation_id, search_query, allow_external):
    '''
    Direct question handler searches OliviaHealth.org knowledge base for most relevant data relating to user query
    Data is passed to LLM to generate output
    Memory is updated with user query and answer

    Examples of direct questions: 'Newborn nutritonal advice', 'How do hormonal IUDs prevent pregnancy', 'What is mastitis treated with'

    Collects and aggregates the identifiers of referenced documents. Each ID maps directly to its corresponding document record on OliviaHealth.com.
    '''

    # Build the retrieval QA chain with SQL memory
    # Must pass in the session_id from the message_store table
    retrieval_qa_chain = build_conversational_retrieval_chain_with_memory(
        llm, retriever_store.pg_vector_retriever, conversation_id, connection_uri, socketio, allow_external)

    # Invoke RAG process
    response = retrieval_qa_chain.invoke(search_query)

    documents = []

    for doc in response["source_documents"]:
        if doc.metadata['source'].get('id'):
            documents.append(doc.metadata['source']['id'])

    answer = response.get('answer')

    return {'answer': answer, 'documents': documents}

def search_location_questions(conversation_id, search_query):
    '''
    Location question handler searches Locations table for most relevant locations relating to user query
    Data is converted to JSON array of locations
    Data is also passed to LLM to generate output
    Reponse includes the LLM response and the raw json array of locations
    Memory is updated with user query and answer

    Examples of location questions: 'Dental Services in Corpus Christi', 'Where can I get mental health support in Bryan'
    '''
    retrieval_qa_chain = build_conversational_retrieval_chain_with_memory(
        llm, retriever_store.table_column_retriever, conversation_id, connection_uri, socketio)
    
    response = retrieval_qa_chain.invoke(search_query)
    answer = response.get('answer')
    source_documents = response.get('source_documents')

    # Return the LLM response and the JSON
    return {
        "response": answer,
        "locations": [json.loads(doc.page_content) for doc in source_documents]
    }

def determine_search_type(messages):
    '''
    Given a search query, determine whether it's location-based, direct-answer, or needs follow-up.
    Returns a JSON object with the selected function name, summarized query, and optional follow-up response.
    '''

    system_instruction = {
        "role": "system",
        "content": (
            "Analyze the conversation history. Select 'search_direct_questions' for general knowledge, "
            "'search_location_questions' for local/map queries, or 'follow_up' if you need the user "
            "to clarify or give more information. If you select 'follow_up', the 'query' property "
            "must be empty, and you must write a helpful follow-up question in the 'response' property."
        )
    }
    
    classifier_messages = messages + [system_instruction]

    response = structured_classifier.invoke(classifier_messages)

    return response.model_dump() if hasattr(response, "model_dump") else response
