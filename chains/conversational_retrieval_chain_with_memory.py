from langchain_core.retrievers import BaseRetriever
from langchain.memory import ConversationBufferMemory
from langchain_community.chat_message_histories import SQLChatMessageHistory
from langchain.chains import ConversationalRetrievalChain
from langchain.callbacks.streaming_stdout import StreamingStdOutCallbackHandler

from retrievers.ContextDecidingRetriever import ContextDecidingRetriever

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


def build_conversational_retrieval_chain_with_memory( llm, retriever: BaseRetriever, conversation_id, connection_string, socket=None, allow_external: bool = False ):
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
        llm.streaming = True
        llm.callbacks = [StreamCallbackHandler(socket)]

    deciding_retriever = ContextDecidingRetriever(
        base_retriever=retriever,
        conversation_id=conversation_id,
        allow_external=allow_external,
        socket=socket,
    )

    return ConversationalRetrievalChain.from_llm(
        llm=llm,
        memory=memory,
        retriever=deciding_retriever,
        condense_question_llm=llm,
        return_source_documents=True,
    )
