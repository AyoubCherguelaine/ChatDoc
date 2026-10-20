"""
Embedding provider — fully OpenAI-based.

Originally used third-party API embeddings. Now defaults to
OpenAI's ``text-embedding-3-small`` (cheapest high-quality model) with
hybrid RAG (BM25 + dense RRF fusion) and optional GPT reranking.

The original public surface (``embeddings`` singleton + ``get_vectore_db``)
is preserved for backwards compatibility.
"""

from __future__ import annotations

from dotenv import load_dotenv

load_dotenv()

from .smart_embedding import SmartEmbedding, SmartEmbeddingConfig  # noqa: E402
from .vectoreStore import SmartVectorStore  # noqa: E402

# ---------------------------------------------------------------------------
# Default singleton embedding (lazy — models initialised on first use)
# ---------------------------------------------------------------------------

_default_config = SmartEmbeddingConfig(
    embedding_model="text-embedding-3-small",
    use_reranker=False,
    use_hybrid=True,
    use_rrf=True,
    hybrid_alpha=0.4,
)


def get_embedding_model(
    config: SmartEmbeddingConfig | None = None,
) -> SmartEmbedding:
    """Create a :class:`SmartEmbedding` with the given config."""
    cfg = config or _default_config
    return SmartEmbedding(cfg)


# Module-level singleton for backwards compatibility
embeddings: SmartEmbedding = get_embedding_model()


# ---------------------------------------------------------------------------
# Backwards-compatible factory
# ---------------------------------------------------------------------------


def get_vectore_db(
    chunks,
    embedding: SmartEmbedding | None = None,
) -> SmartVectorStore:
    """
    Build a smart vector store from chunk Documents.

    Parameters
    ----------
    chunks
        A list of LangChain ``Document`` objects (output of
        :func:`documents.splitter.split_documents`).
    embedding
        Optional :class:`SmartEmbedding` instance. Defaults to the
        module-level OpenAI singleton.
    """
    emb = embedding or embeddings
    return SmartVectorStore(embedding=emb).build(chunks)
