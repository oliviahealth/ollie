import textwrap
import os

from pydantic import BaseModel, Field

from langchain_core.retrievers import BaseRetriever
from langchain_core.documents import Document
from langchain_openai import ChatOpenAI

class ContextJudge(BaseModel):
    sufficient: bool = Field(
        description="True when the provided context is enough to answer the question."
    )


llm = ChatOpenAI(
    model=os.getenv("CHAT_MODEL"),
    api_key=os.getenv("TAMU_AI_CHAT_API_KEY"),
    base_url=os.getenv("TAMU_AI_CHAT_BASE_URL"),
)

structured_judge = llm.with_structured_output(
    ContextJudge,
    method="json_schema",
    strict=True,
)

def judge_context(query, context_docs):
    """
    True  -> context is sufficient
    False -> context is insufficient (should fetch extra context)
    """
    combined = "\n\n---\n\n".join(
        (getattr(d, "page_content", "") or "").strip()
            for d in (context_docs or [])
            if (getattr(d, "page_content", "") or "").strip()
    )

    system_msg = (
        "You are a careful judge. Determine if the provided context is enough "
        "to confidently and accurately answer the question. "
        'Respond ONLY with JSON: {"sufficient": true|false}'
    )
    user_msg = f"Question:\n{query}\n\nContext:\n{combined or '[empty]'}"

    try:
        response = structured_judge.invoke([
            {"role": "system", "content": system_msg},
            {"role": "user", "content": user_msg},
        ])
        return bool(response.sufficient)
    except Exception:
        return False
    
def fetch_external_context(conversation_id, query):
    """
    Return extra context snippets (NOT a final answer).
    """
    system_msg = (
        "You are an information-gathering assistant. Given a user's question, "
        "provide concise additional context or key facts from general knowledge that could help answer the question "
        "more completely. Do NOT write the final answer—just provide extra factual context as bullet points or "
        "short paragraphs."
    )
    user_msg = (
        f"conversation_id: {conversation_id or 'new'}\n"
        f"Question: {query}\n\n"
    )

    try:
        resp = llm.invoke([
            {"role": "system", "content": system_msg},
            {"role": "user", "content": user_msg},
        ])
        return (resp.content or "").strip()
    except Exception:
        return ""

class ContextDecidingRetriever(BaseRetriever):
    """
    Wraps a base retriever. On each call:
      - fetch KB docs
      - judge sufficiency
      - if weak and external allowed, fetch extra context and append as a Document
      - return merged docs
    """

    base_retriever: BaseRetriever
    conversation_id: str = None
    allow_external: bool = False
    socket: any = None

    def _get_relevant_documents(self, query: str, *, run_manager = None):
        # 1) KB retrieval
        kb_docs = self.base_retriever.get_relevant_documents(query)

        # 2) Judge sufficiency (before answer composition)
        sufficient = judge_context(query, kb_docs)
        if sufficient or not self.allow_external:
            return kb_docs
        
        print("fetching additional context")

        extra = (fetch_external_context( self.conversation_id, query) or "").strip()
        if extra:
            kb_docs.append(
                Document(
                    page_content=textwrap.dedent(
                        f"[EXTERNAL CONTEXT]\n{extra}").strip(),
                    metadata={"source": "external_context"},
                )
            )
        return kb_docs

    async def _aget_relevant_documents(self, query, *, run_manager = None):
        # Simple async wrapper around sync behavior
        return self._get_relevant_documents(query, run_manager=run_manager)
