"""Tests for documents/splitter.py"""

from backend.documents.pdf_loader import PageText
from backend.documents.splitter import (
    LargeChunkSplitter,
    SemanticChunkSplitter,
    SplitterConfig,
    _make_metadata,
    split_documents,
    split_pages_semantically,
)

# ---------------------------------------------------------------------------
# Metadata helper
# ---------------------------------------------------------------------------


class TestMakeMetadata:
    def test_metadata_fields(self):
        meta = _make_metadata("doc.pdf", 1, 3, 0, "/path/doc.pdf")
        assert meta["doc_name"] == "doc.pdf"
        assert meta["source"] == "/path/doc.pdf"
        assert meta["start_page"] == 1
        assert meta["end_page"] == 3
        assert meta["chunk_index"] == 0

    def test_metadata_default_source(self):
        meta = _make_metadata("doc.pdf", 1, 1, 0)
        assert meta["source"] == "doc.pdf"
        assert "file_path" not in meta


# ---------------------------------------------------------------------------
# SplitterConfig
# ---------------------------------------------------------------------------


class TestSplitterConfig:
    def test_defaults(self):
        cfg = SplitterConfig()
        assert cfg.chunk_size == 4000
        assert cfg.chunk_overlap == 500
        assert cfg.separators is not None

    def test_custom(self):
        cfg = SplitterConfig(chunk_size=2000, chunk_overlap=200)
        assert cfg.chunk_size == 2000
        assert cfg.chunk_overlap == 200


# ---------------------------------------------------------------------------
# LargeChunkSplitter
# ---------------------------------------------------------------------------


def _make_pages(text_per_page: list[str], doc_name: str = "test.pdf") -> list[PageText]:
    pages = []
    total = len(text_per_page)
    for i, text in enumerate(text_per_page, 1):
        pages.append(PageText(i, text, doc_name, total))
    return pages


class TestLargeChunkSplitter:
    def test_single_page_chunk(self):
        pages = _make_pages(["Short text."])
        splitter = LargeChunkSplitter()
        chunks = splitter.split_pages(pages)
        assert len(chunks) == 1
        assert "Short text" in chunks[0].page_content
        assert chunks[0].metadata["doc_name"] == "test.pdf"
        assert chunks[0].metadata["start_page"] == 1
        assert chunks[0].metadata["end_page"] == 1

    def test_multiple_small_pages_merged(self):
        """Small pages should be merged into a single chunk."""
        pages = _make_pages(["Page 1 text. " * 50] * 5)
        splitter = LargeChunkSplitter(SplitterConfig(chunk_size=4000, chunk_overlap=500))
        chunks = splitter.split_pages(pages)
        assert len(chunks) == 1  # all fit in one chunk
        assert chunks[0].metadata["start_page"] == 1
        assert chunks[0].metadata["end_page"] == 5

    def test_large_page_single_chunk(self):
        """A page larger than chunk_size should be emitted on its own."""
        big_text = "X" * 5000
        pages = _make_pages([big_text])
        splitter = LargeChunkSplitter(SplitterConfig(chunk_size=1000))
        chunks = splitter.split_pages(pages)
        assert len(chunks) == 1
        assert len(chunks[0].page_content) == 5000

    def test_chunk_index_offset(self):
        pages = _make_pages(["A" * 3000, "B" * 3000])
        splitter = LargeChunkSplitter(SplitterConfig(chunk_size=1000))
        chunks = splitter.split_pages(pages, chunk_index_offset=5)
        indices = [c.metadata["chunk_index"] for c in chunks]
        assert indices == [5, 6]

    def test_no_pages(self):
        pages = _make_pages([])
        splitter = LargeChunkSplitter()
        chunks = splitter.split_pages(pages)
        assert chunks == []

    def test_metadata_on_all_chunks(self):
        pages = _make_pages(["A" * 2000, "B" * 2000, "C" * 2000])
        splitter = LargeChunkSplitter(SplitterConfig(chunk_size=1000))
        chunks = splitter.split_pages(pages)
        for c in chunks:
            assert "doc_name" in c.metadata
            assert "start_page" in c.metadata
            assert "end_page" in c.metadata
            assert "chunk_index" in c.metadata


# ---------------------------------------------------------------------------
# SemanticChunkSplitter
# ---------------------------------------------------------------------------


class TestSemanticChunkSplitter:
    def test_short_text_no_split(self):
        pages = _make_pages(["Short text."])
        splitter = SemanticChunkSplitter(min_chunk_size=1500)
        chunks = splitter.split_pages(pages)
        assert len(chunks) == 1

    def test_heading_detection(self):
        """A chunk with headings should be processed but not crash."""
        text = "1. Introduction\n\nThis is the introduction. " * 50
        text += "\n\n2. Methods\n\nThis is the methods section. " * 50
        pages = _make_pages([text])
        splitter = SemanticChunkSplitter(
            config=SplitterConfig(chunk_size=10000),
            min_chunk_size=200,
        )
        chunks = splitter.split_pages(pages)
        assert len(chunks) >= 1

    def test_large_chunk_passed_through(self):
        text = "No headings here. " * 200
        pages = _make_pages([text])
        splitter = SemanticChunkSplitter(
            config=SplitterConfig(chunk_size=100000),
            min_chunk_size=5000,
        )
        chunks = splitter.split_pages(pages)
        assert len(chunks) == 1


# ---------------------------------------------------------------------------
# Top-level helpers
# ---------------------------------------------------------------------------


class TestSplitDocuments:
    def test_split_documents_multiple(self):
        from backend.documents.pdf_loader import PDFDocument

        docs = [
            PDFDocument(
                name="doc1.pdf",
                pages=_make_pages(["A" * 3000], "doc1.pdf"),
            ),
            PDFDocument(
                name="doc2.pdf",
                pages=_make_pages(["B" * 3000], "doc2.pdf"),
            ),
        ]
        chunks = split_documents(docs, LargeChunkSplitter(SplitterConfig(chunk_size=1000)))
        assert len(chunks) == 2
        assert chunks[0].metadata["doc_name"] == "doc1.pdf"
        assert chunks[1].metadata["doc_name"] == "doc2.pdf"
        # Chunk indices should be sequential across documents
        indices = [c.metadata["chunk_index"] for c in chunks]
        assert indices == [0, 1]

    def test_split_pages_semantically(self):
        from backend.documents.pdf_loader import PDFDocument

        docs = [
            PDFDocument(
                name="doc.pdf",
                pages=_make_pages(["A" * 3000], "doc.pdf"),
            ),
        ]
        chunks = split_pages_semantically(docs, min_chunk_size=500)
        assert len(chunks) >= 1
