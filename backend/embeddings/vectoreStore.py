"""
Vector store factory and config.

Provides a high-level :class:`SmartVectorStore` that wraps FAISS
with metadata-aware search and persistence helpers.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Optional

from langchain_community.vectorstores import FAISS
from langchain_core.documents import Document

from .smart_embedding import SmartEmbedding


@dataclass
class VectorStoreConfig:
    """Configuration for the vector store."""

    # Retrieval
    search_k: int = 10  # How many docs to fetch from FAISS before rerank
    final_k: int = 5  # How many docs to return after rerank
    score_threshold: Optional[float] = None

    # Persistence
    index_path: str = "faiss_index"
    save_on_build: bool = False


class SmartVectorStore:
    """
    Drop-in replacement for the original ``generateEmbeddingDb``.

    Wraps :class:`~embeddings.smart_embedding.SmartEmbedding` with a
    clean API used by the conversation chain and the agent's retrieval
    tool.
    """

    def __init__(
        self,
        embedding: Optional[SmartEmbedding] = None,
        config: Optional[VectorStoreConfig] = None,
    ):
        self.embedding = embedding or SmartEmbedding()
        self.config = config or VectorStoreConfig()
        self._store: Any = None

    def build(self, chunks: list[Document]) -> "SmartVectorStore":
        """Build the FAISS index from chunk Documents."""
        self._store = self.embedding.build_vector_store(chunks)
        if self.config.save_on_build:
            self.save()
        return self

    def as_retriever(self):
        """Return a LangChain-compatible retriever."""
        if self._store is None:
            raise RuntimeError("Vector store not built.")
        return self._store.as_retriever(
            search_type="similarity",
            search_kwargs={"k": self.config.search_k},
        )

    def search(self, query: str, top_k: Optional[int] = None) -> list[Document]:
        """Smart retrieval: vector search → hybrid merge → rerank."""
        k = top_k or self.config.final_k
        return self.embedding.similarity_search(query, top_k=k)

    @property
    def store(self) -> Optional[FAISS]:
        return self._store

    def save(self, path: Optional[str] = None) -> None:
        p = path or self.config.index_path
        if self._store is None:
            raise RuntimeError("No vector store to save.")
        self._store.save_local(p)

    def load(self, path: Optional[str] = None) -> "SmartVectorStore":
        p = path or self.config.index_path
        self.embedding.load(p)
        self._store = self.embedding._faiss_store  # noqa: SLF005
        return self


# ---------------------------------------------------------------------------
# Backwards-compatible factory (original signature)
# ---------------------------------------------------------------------------


def generateEmbeddingDb(
    chunks: list[Document],
    embeddings: SmartEmbedding,
) -> SmartVectorStore:
    """
    Create a :class:`SmartVectorStore` from chunk Documents and an
    :class:`SmartEmbedding` instance.

    .. note::
       The *embeddings* parameter is kept for backwards compatibility
       with the original API.  Pass a :class:`SmartEmbedding` (or any
       embedding object) and it will be used for indexing.
    """
    store = SmartVectorStore(embedding=embeddings)
    return store.build(chunks)
