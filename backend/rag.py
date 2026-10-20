"""
RAG orchestration for the DocuChat backend.

Reuses the existing Python pipeline:

* ``documents``  — PDF loading (PyMuPDF) + metadata-rich chunking
* ``embeddings``  — OpenAI embeddings + hybrid (BM25 + dense) retrieval
* ``agent``       — free ReAct agent with document tools
* ``chat``        — conversational retrieval chain + prompts

Documents are processed at upload time (text extraction, chunking, embedding
indexing).  The in-memory FAISS index is cached for the lifetime of the process;
chunk *text* + metadata is also persisted in PostgreSQL so an index can be
rebuilt (and re-embedded) from the database if the process restarts.
"""

from __future__ import annotations

import shutil
import threading
import uuid
from pathlib import Path
from typing import Optional

from langchain_core.documents import Document
from langchain_core.messages import AIMessage, HumanMessage, SystemMessage

from backend.agent.agent import AgentConfig, FreeAgent
from backend.agent.tools.document_tools import DocumentToolKit
from backend.chat.chatWithVSDB import get_conversation_chain, get_llm
from backend.documents.loader import load_document
from backend.documents.processors import DocumentProcessor, ProcessingConfig
from backend.embeddings.smart_embedding import SmartEmbedding, SmartEmbeddingConfig
from backend.embeddings.vectoreStore import SmartVectorStore

from .config import settings
from .db import get_conn, query


class IndexBundle:
    """Cached, in-memory representation of a processed document."""

    def __init__(self, doc_id: str):
        self.doc_id = doc_id
        self.vector_store: Optional[SmartVectorStore] = None
        self.pdf_docs: list = []
        self.model_name: str = settings.DEFAULT_MODEL

    def ensure_loaded(self) -> None:
        if self.vector_store is not None:
            return
        # Rebuild the FAISS index from persisted chunks (re-embeds).
        rows = (
            query(
                "SELECT text, metadata FROM docuchat.chunks WHERE document_id = %s ORDER BY chunk_index",
                (self.doc_id,),
            )
            or []
        )
        chunks: list[Document] = [Document(page_content=r["text"], metadata=r["metadata"] or {}) for r in rows]
        if not chunks:
            return
        emb = SmartEmbedding(_emb_config())
        vs = SmartVectorStore(embedding=emb).build(chunks)
        self.vector_store = vs
        file_path = _pdf_path(self.doc_id)
        if file_path.exists():
            self.pdf_docs = [load_document(file_path)]


_registry: dict[str, IndexBundle] = {}
_lock = threading.RLock()


def _emb_config() -> SmartEmbeddingConfig:
    return SmartEmbeddingConfig(
        embedding_model=settings.EMBEDDING_MODEL,
        embedding_api_key=settings.OPENAI_API_KEY or None,
        use_reranker=False,
        use_hybrid=True,
        use_rrf=True,
    )


def _ensure_dirs() -> None:
    Path(settings.UPLOAD_DIR).mkdir(parents=True, exist_ok=True)
    Path(settings.INDEX_DIR).mkdir(parents=True, exist_ok=True)


def _pdf_path(doc_id: str) -> Path:
    # original filename stored on the documents row
    row = query("SELECT filename FROM docuchat.documents WHERE id = %s", (doc_id,), one=True)
    if not row:
        return Path(settings.UPLOAD_DIR) / f"{doc_id}.pdf"
    return Path(settings.UPLOAD_DIR) / doc_id / row["filename"]


def process_upload(user_id: str, file_path: Path, original_filename: str, file_size: int, mime: str) -> tuple[int, int]:
    """Process an uploaded document: chunk, embed-index, persist chunks.

    Returns (chunk_count, page_count).
    """
    _ensure_dirs()
    doc_id = str(uuid.uuid4())

    # Parse and embed before publishing metadata. Failed processing leaves no partial document.
    original_filename = Path(original_filename.replace("\\", "/")).name
    if not original_filename or original_filename in {".", ".."}:
        raise ValueError("Invalid filename")
    doc_dir = Path(settings.UPLOAD_DIR) / doc_id
    doc_dir.mkdir(parents=True, exist_ok=True)
    dest = doc_dir / original_filename
    try:
        shutil.copyfile(file_path, dest)
        try:
            pdf_doc = load_document(dest)
        except ValueError:
            raise
        except Exception as exc:
            raise ValueError("This file could not be read. Check that it is a valid, unencrypted document.") from exc
        page_count = pdf_doc.total_pages
        processor = DocumentProcessor(
            ProcessingConfig(
                use_semantic_split=True,
                chunk_size=4000,
                chunk_overlap=500,
                min_semantic_chunk=1500,
            )
        )
        chunks = processor.process_documents([pdf_doc])
        if not chunks:
            raise ValueError("No readable content found in this file.")
        emb = SmartEmbedding(_emb_config())
        vs = SmartVectorStore(embedding=emb).build(chunks)
        with get_conn() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    "INSERT INTO docuchat.documents "
                    "(id, user_id, filename, original_filename, file_size, mime_type, page_count) "
                    "VALUES (%s, %s, %s, %s, %s, %s, %s)",
                    (doc_id, user_id, original_filename, original_filename, file_size, mime, page_count),
                )
                for idx, ch in enumerate(chunks):
                    meta = {
                        **ch.metadata,
                        "doc_name": original_filename,
                        "source": original_filename,
                        "chunk_index": idx,
                    }
                    cur.execute(
                        "INSERT INTO docuchat.chunks "
                        "(id, document_id, page_index, chunk_index, text, metadata) "
                        "VALUES (%s, %s, %s, %s, %s, %s)",
                        (str(uuid.uuid4()), doc_id, ch.metadata.get("start_page"), idx, ch.page_content, _jsonb(meta)),
                    )
    except Exception:
        shutil.rmtree(doc_dir, ignore_errors=True)
        raise

    with _lock:
        bundle = IndexBundle(doc_id)
        bundle.vector_store = vs
        bundle.pdf_docs = [pdf_doc]
        _registry[doc_id] = bundle

    return len(chunks), page_count


def get_bundle(doc_id: str) -> IndexBundle:
    """Return a cached bundle, rebuilding from the DB if necessary."""
    with _lock:
        bundle = _registry.get(doc_id)
        if bundle is not None:
            bundle.ensure_loaded()
            return bundle
        bundle = IndexBundle(doc_id)
        bundle.ensure_loaded()
        _registry[doc_id] = bundle
        return bundle


def get_history(session_id: str) -> list:
    rows = query(
        "SELECT role, content FROM (SELECT role, content, created_at FROM docuchat.messages "
        "WHERE session_id = %s ORDER BY created_at DESC LIMIT 20) recent ORDER BY created_at ASC",
        (session_id,),
    )
    messages: list = []
    for r in rows or []:
        if r["role"] == "user":
            messages.append(HumanMessage(content=r["content"]))
        else:
            messages.append(AIMessage(content=r["content"]))
    return messages


def _jsonb(val) -> str:
    import json

    return json.dumps(val)


def stream_chat(
    doc_id: str,
    query: str,
    history: list,
    model_name: str = settings.DEFAULT_MODEL,
    mode: str = "conversational",
    response_style: str = "balanced",
):
    """Yield streamed text chunks for a user turn.

    ``mode`` is ``"conversational"`` (retrieval+LLM) or ``"agent"`` (ReAct).
    """
    bundle = get_bundle(doc_id)
    if bundle.vector_store is None:
        yield "[ERROR] Document index not available. Re-upload the document."
        return

    instruction = {
        "concise": "Keep the answer brief and focused, using bullets where useful.",
        "balanced": "Give a clear answer with the evidence needed to support it.",
        "detailed": "Provide a thorough analysis with headings and specific evidence.",
    }.get(response_style, "")
    query = query + "\n\nResponse preference: " + instruction
    if mode == "agent":
        yield from _stream_agent(bundle, query, history, model_name)
    else:
        yield from _stream_conversational(bundle, query, history, model_name)


def _stream_conversational(bundle: IndexBundle, query: str, history: list, model_name: str):
    chain = get_conversation_chain(bundle.vector_store, model_name=model_name)
    docs = chain._retrieve(query)  # type: ignore[attr-defined]
    context = chain._format_docs(docs)  # type: ignore[attr-defined]

    messages: list = [
        SystemMessage(content=chain.system_prompt.format(context=context)),
    ]
    messages.extend(history[-20:])
    messages.append(HumanMessage(content=query))

    llm = chain.llm
    emitted = False
    try:
        for chunk in llm.stream(messages):
            content = chunk.content if hasattr(chunk, "content") else str(chunk)
            if content:
                emitted = True
                yield content
    except Exception:
        if emitted:
            raise
        # Fallback to a single non-streaming completion.
        try:
            resp = llm.invoke(messages)
            content = resp.content if hasattr(resp, "content") else str(resp)
            if content:
                yield content
        except Exception:
            raise


def _stream_agent(bundle: IndexBundle, query: str, history: list, model_name: str):
    llm = get_llm(model_name=model_name)
    toolkit = DocumentToolKit(
        vector_store=bundle.vector_store,
        documents=bundle.pdf_docs,
        llm=llm,
    )
    agent = FreeAgent(
        llm=llm,
        tool_kit=toolkit,
        config=AgentConfig(max_iterations=8, verbose=False),
    )
    recent = "\n".join(f"{m.type}: {m.content}" for m in history[-10:])
    result = agent.run("Conversation context (for reference only):\n" + recent + "\n\nCurrent request:\n" + query)
    text = result.response or ""
    # Stream the final answer in small pieces for a fluid UI.
    for i in range(0, len(text), 60):
        yield text[i : i + 60]
