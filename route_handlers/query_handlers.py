import json
import os
import openai

from chains.conversational_retrieval_chain_with_memory import build_conversational_retrieval_chain_with_memory
from langchain.chat_models import ChatOpenAI
from langchain.embeddings import OpenAIEmbeddings

from socketio_instance import socketio
from retrievers.PGVectorRetriever import build_pg_vector_retriever
from retrievers.TableColumnRetriever import build_table_column_retriever

llm = ChatOpenAI()
openai_embeddings = OpenAIEmbeddings()
connection_uri = os.getenv("POSTGRES_DSN")

# Create a retriever for the default langchain_pg_embedding table (direct questions)
pg_vector_retriever = build_pg_vector_retriever('2024-11-15 12:59:57', openai_embeddings, connection_uri)

# Creating a TableColumnRetriever to index all of the columns for the location table when retrieving documents (location based questions)
table_column_retriever = build_table_column_retriever(
    connection_uri=connection_uri,
    table_name="location",
    column_names=["id", "name", "address", "city", "state", "country", "zip_code", "latitude", "longitude", "description", "phone", "sunday_hours", "monday_hours",
                    "tuesday_hours", "wednesday_hours", "thursday_hours", "friday_hours", "saturday_hours", "rating", "address_link", "website", "resource_type", "county"],
    embedding_column_name="embedding"
)

def search_direct_questions(conversation_id, search_query, allow_external):
    '''
    Direct question handler searches OliviaHealth.org knowledge base for most relevant data relating to user query
    Data is passed to LLM to generate output
    Memory is updated with user query and answer

    Examples of direct questions: 'Newborn nutritonal advice', 'How do hormonal IUDs prevent pregnancy', 'What is mastitis treated with'
    '''

    # Build the retrieval QA chain with SQL memory
    # Must pass in the session_id from the message_store table
    retrieval_qa_chain = build_conversational_retrieval_chain_with_memory(
        llm, pg_vector_retriever, conversation_id, connection_uri, socketio, allow_external)

    # Invoke RAG process
    response = retrieval_qa_chain.invoke(search_query)

    print(response)


    answer = response.get('answer')

    return answer

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
        llm, table_column_retriever, conversation_id, connection_uri, socketio)
    
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
    Given a search query, determine weather its a location-based or direct-answer question or if more information is needed.
    Reconstruct the entire conversation history, then prompt OpenAI with tools to make the determination
    Need to provide an array of tools so OpenAI can make the reccomendation. See: https://platform.openai.com/docs/assistants/tools/function-calling
    '''

    # Prompt OpenAI to make determination
    response = openai.chat.completions.create(
        model="gpt-4o",
        messages=messages,
        tools=tools,
    )

    # If we have a refusal (ex: for unsafe questions), return an error
    refusal = response.choices[0].message.refusal
    if (refusal):
        return "Something went wrong: OpenAi Classification Refusal", 500
    
    return response


# Defining list of tools to use with OpenAI function calling
tools = [
    {
        "type": 'function',
        "function": {
            "name": "search_direct_questions",
            "description": "Retrieve a direct answer from the knowlege base based on a user question. Call this whenever you get a direct question that should be answer without a specific location. For example when a user asks 'newborn nutritional advice' or 'birth control alternatives'",
            "parameters": {
                "type": "object",
                "properties": {
                    "id": {
                        "type": "string",
                        "description": "The conversation id. For new conversations, this will be null, however for existing conversations, this will be passed in by the user to continue that conversation",
                    },
                    "query": {
                        "type": "string",
                        "description": "The question the user is trying to find an answer for"
                    }
                },
                "required": ["id", "query"],
                "additionalProperties": False
            }
        }
    },
    {
        "type": 'function',
        "function": {
            "name": "search_location_questions",
            "description": "Retrieve a location from the locations table based on a user question. Call this whenever you get a question that should be answer with a specific location. For example when a user asks 'mental health support in Bryan, Texas' or 'Where can i get a root canal in Corpus Christi'",
            "parameters": {
                "type": "object",
                "properties": {
                    "id": {
                        "type": "string",
                        "description": "The conversation id. For new conversations, this will be null, however for existing conversations, this will be passed in by the user to continue that conversation",
                    },
                    "query": {
                        "type": "string",
                        "description": "The question the user is trying to find an answer for"
                    }
                },
                "required": ["id", "query"],
                "additionalProperties": False
            }
        }
    }
]
