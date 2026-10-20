"""Tests for embeddings/smart_embedding.py and vectoreStore.py"""

from unittest.mock import MagicMock, patch

import pytest
from langchain_core.documents import Document

from backend.embeddings.smart_embedding import (
    DEFAULT_EMBEDDING_MODEL,
    DEFAULT_LLM_MODEL,
    SmartEmbedding,
    SmartEmbeddingConfig,
)
from backend.embeddings.vectoreStore import (
    SmartVectorStore,
    generateEmbeddingDb,
)

# ---------------------------------------------------------------------------
# SmartEmbeddingConfig
# ---------------------------------------------------------------------------


class TestSmartEmbeddingConfig:
    def test_defaults(self):
        cfg = SmartEmbeddingConfig()
        assert cfg.embedding_model == DEFAULT_EMBEDDING_MODEL
        assert cfg.use_reranker is False  # GPT rerank is opt-in
        assert cfg.reranker_model == DEFAULT_LLM_MODEL
        assert cfg.use_hybrid is True
        assert cfg.use_rrf is True
        assert cfg.chunk_size == 4000
        assert cfg.chunk_overlap == 500

    def test_custom(self):
        cfg = SmartEmbeddingConfig(
            embedding_model="text-embedding-3-large",
            use_reranker=True,
            reranker_model="gpt-4o",
            use_hybrid=False,
            chunk_size=5000,
        )
        assert cfg.embedding_model == "text-embedding-3-large"
        assert cfg.use_reranker is True
        assert cfg.reranker_model == "gpt-4o"
        assert cfg.use_hybrid is False
        assert cfg.chunk_size == 5000


# ---------------------------------------------------------------------------
# SmartEmbedding
# ---------------------------------------------------------------------------


class TestSmartEmbedding:
    def test_init(self):
        emb = SmartEmbedding()
        assert emb.config is not None
        assert emb._embedding_model is None

    @patch("backend.embeddings.smart_embedding.SmartEmbedding.init_embedding_model")
    def test_build_vector_store(self, mock_init):
        """Test that build_vector_store creates a FAISS store from chunks."""
        mock_emb_model = MagicMock()
        mock_init.return_value = mock_emb_model

        emb = SmartEmbedding(SmartEmbeddingConfig(use_reranker=False))
        emb._embedding_model = mock_emb_model

        chunks = [
            Document(
                page_content="Test chunk",
                metadata={"doc_name": "a.pdf", "start_page": 1, "end_page": 1, "chunk_index": 0},
            )
        ]

        with patch("langchain_community.vectorstores.FAISS.from_documents") as mock_from:
            mock_store = MagicMock()
            mock_from.return_value = mock_store
            result = emb.build_vector_store(chunks)
            assert result is mock_store
            assert emb._chunks == chunks
            assert emb._faiss_store is mock_store

    @patch("backend.embeddings.smart_embedding.SmartEmbedding.init_embedding_model")
    def test_search_raises_without_store(self, mock_init):
        mock_init.return_value = MagicMock()
        emb = SmartEmbedding(SmartEmbeddingConfig(use_reranker=False))
        emb._embedding_model = MagicMock()
        with pytest.raises(RuntimeError, match="not built"):
            emb.similarity_search("test query")

    @patch("backend.embeddings.smart_embedding.SmartEmbedding.init_embedding_model")
    @patch("backend.embeddings.smart_embedding.SmartEmbedding.init_reranker")
    def test_similarity_search_with_reranker(self, mock_rerank, mock_init):
        mock_init.return_value = MagicMock()
        mock_rerank.return_value = MagicMock()  # GPT-based reranker

        emb = SmartEmbedding(SmartEmbeddingConfig(use_reranker=True))
        emb._embedding_model = MagicMock()

        docs = [
            Document(page_content="Doc A", metadata={"doc_name": "a.pdf"}),
            Document(page_content="Doc B", metadata={"doc_name": "b.pdf"}),
            Document(page_content="Doc C", metadata={"doc_name": "c.pdf"}),
        ]

        mock_faiss = MagicMock()
        mock_faiss.similarity_search.return_value = docs
        emb._faiss_store = mock_faiss

        with patch.object(emb, "_gpt_rerank") as mock_rerank_method:
            mock_rerank_method.return_value = docs[:2]
            result = emb.similarity_search("query", top_k=2)

        assert len(result) == 2

    def test_get_chunks_by_page(self):
        emb = SmartEmbedding(SmartEmbeddingConfig(use_reranker=False))
        emb._chunks = [
            Document(page_content="A", metadata={"doc_name": "a.pdf", "start_page": 1, "end_page": 2}),
            Document(page_content="B", metadata={"doc_name": "a.pdf", "start_page": 3, "end_page": 4}),
            Document(page_content="C", metadata={"doc_name": "b.pdf", "start_page": 1, "end_page": 1}),
        ]

        result = emb.get_chunks_by_page("a.pdf", 3)
        assert len(result) == 1
        assert result[0].page_content == "B"

    def test_get_chunks_by_page_not_found(self):
        emb = SmartEmbedding(SmartEmbeddingConfig(use_reranker=False))
        emb._chunks = []
        result = emb.get_chunks_by_page("nonexistent.pdf", 1)
        assert result == []

    def test_save_raises_without_store(self):
        emb = SmartEmbedding(SmartEmbeddingConfig(use_reranker=False))
        with pytest.raises(RuntimeError, match="No vector store"):
            emb.save("test_path")

    def test_load(self):
        emb = SmartEmbedding(SmartEmbeddingConfig(use_reranker=False))
        with patch("backend.embeddings.smart_embedding.SmartEmbedding.init_embedding_model") as mock_init:
            mock_init.return_value = MagicMock()
            with patch("langchain_community.vectorstores.FAISS.load_local") as mock_load:
                mock_store = MagicMock()
                mock_load.return_value = mock_store
                emb.load("test_path")
                assert emb._faiss_store is mock_store


# ---------------------------------------------------------------------------
# SmartVectorStore
# ---------------------------------------------------------------------------


class TestSmartVectorStore:
    def test_init_defaults(self):
        vs = SmartVectorStore()
        assert vs.config.search_k == 10
        assert vs.config.final_k == 5
        assert vs.config.index_path == "faiss_index"

    @patch.object(SmartVectorStore, "build")
    def test_build_mock(self, mock_build):
        mock_build.return_value = MagicMock()
        vs = SmartVectorStore()
        vs.build(
            [],
        )
        assert mock_build.called

    @patch.object(SmartVectorStore, "build")
    def test_search(self, mock_build):
        vs = SmartVectorStore()
        vs._store = MagicMock()
        mock_embedding = MagicMock()
        mock_embedding.similarity_search.return_value = ["doc1", "doc2"]
        vs.embedding = mock_embedding

        result = vs.search("test", top_k=2)
        assert len(result) == 2
        mock_embedding.similarity_search.assert_called_once_with("test", top_k=2)

    @patch.object(SmartVectorStore, "build")
    def test_as_retriever(self, mock_build):
        vs = SmartVectorStore()
        vs._store = MagicMock()
        retriever = vs.as_retriever()
        assert retriever is not None
        vs._store.as_retriever.assert_called_once()


# ---------------------------------------------------------------------------
# Backwards-compatible factory
# ---------------------------------------------------------------------------


class TestGenerateEmbeddingDb:
    def test_creates_smart_vector_store(self):
        mock_emb = MagicMock()
        mock_emb.build_vector_store.return_value = MagicMock()
        chunks = [Document(page_content="test")]

        # This should call SmartVectorStore.build which calls embedding.build_vector_store
        # We need to mock the build method
        with patch.object(SmartVectorStore, "build") as mock_build:
            mock_build.return_value = "result"
            result = generateEmbeddingDb(chunks, mock_emb)
            assert result == "result"
