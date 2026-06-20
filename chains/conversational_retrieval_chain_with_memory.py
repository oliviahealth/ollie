from langchain_core.retrievers import BaseRetriever
from langchain.memory import ConversationBufferMemory
from langchain_community.chat_message_histories import SQLChatMessageHistory
from langchain.chains import ConversationalRetrievalChain
from langchain.callbacks.streaming_stdout import StreamingStdOutCallbackHandler
from langchain.prompts import PromptTemplate

from retrievers.ContextDecidingRetriever import ContextDecidingRetriever
from prompts.index import MASTER_SYSTEM_PROMPT

# ---------------- Stream handler (unchanged) ----------------
class StreamCallbackHandler(StreamingStdOutCallbackHandler):
    def __init__(self, socketio_instance=None, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.socketio = socketio_instance

    def on_chain_start(self, serialized, prompts, **kwargs) -> None:
        if self.socketio:
            self.socketio.emit('stream_start')

    def on_llm_new_token(self, token, **kwargs) -> None:
        print(token, end='', flush=True)
        if self.socketio:
            self.socketio.emit('stream_data', token)

    def on_chain_end(self, response, **kwargs) -> None:
        if self.socketio:
            self.socketio.emit('stream_end')


def build_conversational_retrieval_chain_with_memory(llm, small_llm, retriever: BaseRetriever, conversation_id, connection_string, socket=None, allow_external: bool = False ):
    """
    Build a standard ConversationalRetrievalChain, but pass a retriever that
    decides (and augments) context before the chain composes the answer.
    """
    memory = ConversationBufferMemory(
        chat_memory=SQLChatMessageHistory(
            session_id=conversation_id, connection_string=connection_string),
        return_messages=True,
        memory_key="chat_history",
        output_key="answer",
    )

    if socket:
        llm.callbacks = [StreamCallbackHandler(socket)]

    condense_prompt = PromptTemplate(
        input_variables=["chat_history", "question"],
        template=(
            "Given the following conversation history and a follow-up question, rephrase the follow-up question "
            "to be a standalone question that captures ALL relevant context from the conversation.\n\n"
            "CRITICAL: If the conversation mentions any urgent situation (emergency, medical crisis, baby not breathing, "
            "choking, bleeding, injury, etc.), you MUST include that context in the standalone question even if the "
            "follow-up question doesn't explicitly mention it.\n\n"
            "For example:\n"
            "- If chat discussed 'baby not breathing' and user asks 'where can I go in college station', "
            "rephrase to: 'emergency medical services or hospitals for baby not breathing in college station'\n"
            "- If chat discussed 'newborn allergies' and user asks 'what foods should I avoid', "
            "rephrase to: 'foods to avoid for newborn with allergies'\n\n"
            "Chat History:\n{chat_history}\n\n"
            "Follow-up question: {question}\n\n"
            "Standalone question:"
        ),
    )

    qa_prompt = PromptTemplate(
        input_variables=["context", "question"],
        template=(
            "{system_prompt}\n\n"
            "[START OF CONTEXT]\n{context}\n[END OF CONTEXT]\n\n"
            "User question: {question}\n\nAnswer:"
        ),
    ).partial(system_prompt=MASTER_SYSTEM_PROMPT.strip())

    return ConversationalRetrievalChain.from_llm(
        llm=llm,
        memory=memory,
        retriever=retriever,
        condense_question_llm=small_llm,
        condense_question_prompt=condense_prompt,
        combine_docs_chain_kwargs={"prompt": qa_prompt},
        return_source_documents=True,
    )
