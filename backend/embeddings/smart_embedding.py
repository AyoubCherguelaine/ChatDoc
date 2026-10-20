"""
Smart embedding layer — fully OpenAI-based.

Key features:

1. **Cheap OpenAI embeddings** – defaults to ``text-embedding-3-small``
   (the cheapest high-quality OpenAI embedding model).

2. **Large chunks** – designed to work with the 4 000-char chunks
   produced by :mod:`documents.splitter`.

3. **Hybrid RAG (text + embedding)** – combines dense vector search
   (OpenAI embeddings via FAISS) with sparse keyword search (BM25)
   using Reciprocal Rank Fusion (RRF) for robust retrieval.

4. **Metadata-aware** – chunks carry ``doc_name``, ``start_page``,
   ``end_page`` and ``chunk_index`` for accurate citations.

5. **Optional GPT reranking** – uses ``gpt-6-luna`` to score and
   re-rank top candidates when extra precision is needed.
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from typing import Any, Optional

from dotenv import load_dotenv
from langchain_core.documents import Document

load_dotenv()

# ---------------------------------------------------------------------------
# Model selection
# ---------------------------------------------------------------------------

DEFAULT_EMBEDDING_MODEL = "text-embedding-3-small"
DEFAULT_LLM_MODEL = "gpt-6-luna"


@dataclass
class SmartEmbeddingConfig:
    """Configuration for :class:`SmartEmbedding`."""

    # Embedding — OpenAI cheap model (only option)
    embedding_model: str = DEFAULT_EMBEDDING_MODEL
    embedding_api_key: Optional[str] = None  # Auto from env if None

    # Reranking — optional GPT-based reranker
    use_reranker: bool = False  # gpt-6-luna rerank (extra cost, use sparingly)
    reranker_model: str = DEFAULT_LLM_MODEL
    rerank_top_k: int = 10

    # Hybrid RAG: dense (embedding) + sparse (BM25 text search)
    use_hybrid: bool = True  # Default ON — combines text + embedding
    hybrid_alpha: float = 0.4  # Weight for dense (0 = pure BM25, 1 = pure dense)

    # RRF fusion for hybrid results
    use_rrf: bool = True  # Reciprocal Rank Fusion instead of score averaging
    rrf_k: int = 60  # RRF constant (default 60 works well in practice)

    # Chunking
    chunk_size: int = 4000
    chunk_overlap: int = 500

    # Retriever
    search_k: int = 20  # Docs fetched before rerank/fusion

    # Misc
    encode_kwargs: dict = field(default_factory=lambda: {"normalize_embeddings": True})


class SmartEmbedding:
    """
    Embedding layer with OpenAI embeddings and hybrid search.

    Uses OpenAI's ``text-embedding-3-small`` for dense embeddings and
    BM25 for sparse keyword search, fused via RRF for robust retrieval.
    """

    def __init__(self, config: Optional[SmartEmbeddingConfig] = None):
        self.config = config or SmartEmbeddingConfig()
        self._embedding_model: Any = None
        self._reranker: Any = None
        self._faiss_store: Any = None
        self._bm25_retriever: Any = None
        self._chunks: list[Document] = []

    # ------------------------------------------------------------------
    # Model initialisation
    # ------------------------------------------------------------------

    def init_embedding_model(self) -> Any:
        """Create / load the OpenAI embedding model (lazy)."""
        if self._embedding_model is not None:
            return self._embedding_model

        from langchain_openai import OpenAIEmbeddings

        api_key = self.config.embedding_api_key or os.getenv("OPENAI_API_KEY")
        self._embedding_model = OpenAIEmbeddings(
            api_key=str(api_key) if api_key else None,  # type: ignore[arg-type]
            model=self.config.embedding_model,
        )
        return self._embedding_model

    @property
    def embedding_model(self) -> Any:
        """Public accessor — initialises on first access."""
        return self.init_embedding_model()

    def init_reranker(self) -> Any:
        """Create / load the GPT-based reranker (lazy, optional)."""
        if not self.config.use_reranker:
            return None
        if self._reranker is not None:
            return self._reranker

        from langchain_openai import ChatOpenAI

        api_key = os.getenv("OPENAI_API_KEY")
        self._reranker = ChatOpenAI(
            model=self.config.reranker_model,
            api_key=api_key,  # type: ignore[arg-type]
        )
        return self._reranker

    # ------------------------------------------------------------------
    # Vector store operations
    # ------------------------------------------------------------------

    def build_vector_store(self, chunks: list[Document]) -> Any:
        """
        Build FAISS (dense) + BM25 (sparse) indexes from chunk Documents.
        """
        from langchain_community.vectorstores import FAISS

        self._chunks = chunks
        embeddings = self.init_embedding_model()

        self._faiss_store = FAISS.from_documents(documents=chunks, embedding=embeddings)

        if self.config.use_hybrid:
            from langchain_community.retrievers import BM25Retriever

            self._bm25_retriever = BM25Retriever.from_documents(chunks)
            self._bm25_retriever.k = self.config.search_k

        # Optionally init GPT reranker
        if self.config.use_reranker:
            self.init_reranker()

        return self._faiss_store

    def similarity_search(self, query: str, top_k: int = 5) -> list[Document]:
        """
        Hybrid retrieval: dense vector search + BM25 text search → RRF fusion → optional GPT rerank.

        This implements the "text + embedding" hybrid RAG pattern.
        """
        if self._faiss_store is None:
            raise RuntimeError("Vector store not built. Call build_vector_store() first.")

        search_k = max(top_k, self.config.rerank_top_k)

        # --- Step 1: dense (embedding) search ---
        dense_docs = self._faiss_store.similarity_search(query, k=search_k)

        # --- Step 2: sparse (BM25 text/keyword) search ---
        sparse_docs: list[Document] = []
        if self.config.use_hybrid and self._bm25_retriever is not None:
            self._bm25_retriever.k = search_k
            sparse_docs = self._bm25_retriever.invoke(query)

        # --- Step 3: hybrid fusion ---
        if dense_docs and sparse_docs and self.config.use_hybrid:
            if self.config.use_rrf:
                fused = self._reciprocal_rank_fusion(dense_docs, sparse_docs)
            else:
                fused = self._weighted_fusion(dense_docs, sparse_docs)
        elif dense_docs:
            fused = dense_docs
        else:
            fused = sparse_docs

        # --- Step 4: optional GPT rerank ---
        if self.config.use_reranker and self._reranker is not None:
            fused = self._gpt_rerank(query, fused, top_k)
        else:
            fused = fused[:top_k]

        return fused

    def _reciprocal_rank_fusion(
        self,
        dense: list[Document],
        sparse: list[Document],
    ) -> list[Document]:
        """
        Combine results from dense and sparse retrieval using RRF.

        RRF score = sum(1 / (rank + k)) for each list the doc appears in.
        """
        k = self.config.rrf_k
        scores: dict[int, float] = {}
        doc_map: dict[int, Document] = {}

        # Dense ranks
        for rank, doc in enumerate(dense):
            key = id(doc)
            doc_map[key] = doc
            scores[key] = scores.get(key, 0.0) + 1.0 / (rank + k)

        # Sparse ranks
        for rank, doc in enumerate(sparse):
            key = id(doc)
            if key in doc_map:
                scores[key] += 1.0 / (rank + k)
            else:
                doc_map[key] = doc
                scores[key] = 1.0 / (rank + k)

        ranked_keys = sorted(scores.keys(), key=lambda k: scores[k], reverse=True)
        return [doc_map[k] for k in ranked_keys]

    def _weighted_fusion(
        self,
        dense: list[Document],
        sparse: list[Document],
    ) -> list[Document]:
        """Merge dense + sparse results using weighted score averaging."""
        alpha = self.config.hybrid_alpha
        seen: dict[int, Document] = {}
        scores: dict[int, float] = {}

        for i, doc in enumerate(dense):
            key = id(doc)
            seen[key] = doc
            scores[key] = scores.get(key, 0.0) + alpha * (1.0 - i / max(len(dense), 1))

        for i, doc in enumerate(sparse):
            key = id(doc)
            seen[key] = doc
            scores[key] = scores.get(key, 0.0) + (1 - alpha) * (1.0 - i / max(len(sparse), 1))

        ordered = sorted(seen.keys(), key=lambda k: scores[k], reverse=True)
        return [seen[k] for k in ordered]

    def _gpt_rerank(
        self,
        query: str,
        docs: list[Document],
        top_k: int,
    ) -> list[Document]:
        """Re-rank documents using gpt-6-luna for relevance scoring."""
        if not docs:
            return docs

        llm = self._reranker
        try:
            from langchain_core.messages import HumanMessage

            # Build a prompt to score each document's relevance
            doc_list = "\n\n".join(f"[{i + 1}] {d.page_content[:300]}" for i, d in enumerate(docs))
            prompt = (
                f"Query: {query}\n\n"
                f"Documents:\n{doc_list}\n\n"
                f"Rate each document's relevance to the query on a scale of 0-10.\n"
                f"Output ONLY a JSON list of objects: "
                f'[{{"index": 1, "score": 8.5}}, ...]\n'
                f"JSON:"
            )
            response = llm.invoke([HumanMessage(content=prompt)])
            import json

            content = response.content if hasattr(response, "content") else str(response)
            scores = json.loads(content.strip())
            score_map = {s["index"]: s["score"] for s in scores}
            ranked = sorted(
                enumerate(docs),
                key=lambda x: score_map.get(x[0] + 1, 0.0),
                reverse=True,
            )
            return [doc for _, doc in ranked[:top_k]]
        except Exception:
            # Fall back to original order on any error
            return docs[:top_k]

    # ------------------------------------------------------------------
    # Utilities
    # ------------------------------------------------------------------

    @property
    def chunks(self) -> list[Document]:
        return self._chunks

    def get_chunks_by_page(self, doc_name: str, page_num: int) -> list[Document]:
        """Return all chunks that include content from *page_num*."""
        return [
            c
            for c in self._chunks
            if c.metadata.get("doc_name") == doc_name
            and c.metadata.get("start_page", 0) <= page_num
            and c.metadata.get("end_page", 0) >= page_num
        ]

    def save(self, path: str) -> None:
        """Persist the FAISS index to disk."""
        if self._faiss_store is None:
            raise RuntimeError("No vector store to save.")
        self._faiss_store.save_local(path)

    def load(self, path: str) -> None:
        """Load a FAISS index from disk."""
        from langchain_community.vectorstores import FAISS

        embeddings = self.init_embedding_model()
        self._faiss_store = FAISS.load_local(path, embeddings, allow_dangerous_deserialization=True)


# ---------------------------------------------------------------------------
# Convenience aliases
# ---------------------------------------------------------------------------

EmbeddingModel = SmartEmbedding
