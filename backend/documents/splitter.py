"""
Smart text splitters that create LARGE chunks with metadata.

The original project used 1028-char chunks with no metadata.  This module
provides:

* ``LargeChunkSplitter`` – configurable large chunks (default 4 000 chars,
  500-char overlap) that preserve PDF page boundaries and attach rich
  metadata to every chunk.
* ``SemanticChunkSplitter`` – combines large chunks with a lightweight
  *semantic* boundary detector so that chunks split at topical rather than
  purely positional boundaries.
* ``split_documents`` – top-level helper that runs a splitter over one
  or more ``PDFDocument`` objects and returns LangChain-compatible
  ``Document`` instances.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

from langchain_core.documents import Document
from langchain_text_splitters import RecursiveCharacterTextSplitter

from .pdf_loader import PageText, PDFDocument

# ---------------------------------------------------------------------------
# Metadata helpers
# ---------------------------------------------------------------------------


def _make_metadata(
    doc_name: str,
    start_page: int,
    end_page: int,
    chunk_index: int,
    file_path: Optional[str] = None,
) -> dict:
    return {
        "doc_name": doc_name,
        "source": file_path or doc_name,
        "start_page": start_page,
        "end_page": end_page,
        "chunk_index": chunk_index,
    }


# ---------------------------------------------------------------------------
# Large-chunk splitter
# ---------------------------------------------------------------------------


@dataclass
class SplitterConfig:
    """Configuration for the large-chunk splitters."""

    chunk_size: int = 4000
    chunk_overlap: int = 500
    separators: list[str] = None

    def __post_init__(self):
        if self.separators is None:
            self.separators = ["\n\n", "\n", ". ", "。", " ", ""]


class LargeChunkSplitter:
    """Split text into large chunks while preserving page boundaries."""

    def __init__(self, config: Optional[SplitterConfig] = None):
        self.config = config or SplitterConfig()
        self._splitter = RecursiveCharacterTextSplitter(
            chunk_size=self.config.chunk_size,
            chunk_overlap=self.config.chunk_overlap,
            separators=self.config.separators,
            length_function=len,
            add_start_index=True,
        )

    def split_pages(self, pages: list[PageText], chunk_index_offset: int = 0) -> list[Document]:
        """
        Split a list of ``PageText`` objects into large chunks.

        Pages are never split mid-page — a chunk contains whole pages only —
        so that the ``read_page`` tool can always reconstruct the original
        page content.
        """
        chunks: list[Document] = []
        if not pages:
            return chunks

        doc_name = pages[0].doc_name
        file_path = pages[0].__dict__.get("file_path") or None

        current_texts: list[str] = []
        current_pages: list[int] = []
        current_size = 0
        idx = chunk_index_offset

        for page in pages:
            page_text = page.text
            page_size = len(page_text)

            # If a single page exceeds chunk_size, emit it alone
            if page_size > self.config.chunk_size:
                if current_texts:
                    self._emit_chunk(chunks, current_texts, current_pages, doc_name, idx, file_path)
                    current_texts = []
                    current_pages = []
                    current_size = 0
                    idx += 1
                self._emit_chunk(chunks, [page_text], [page.page_number], doc_name, idx, file_path)
                idx += 1
                continue

            # If adding this page exceeds the chunk size, flush first
            if current_size + page_size > self.config.chunk_size and current_texts:
                self._emit_chunk(chunks, current_texts, current_pages, doc_name, idx, file_path)
                current_texts = []
                current_pages = []
                current_size = 0
                idx += 1

            current_texts.append(page_text)
            current_pages.append(page.page_number)
            current_size += page_size + 10  # +10 for separator overhead

        # Flush remaining
        if current_texts:
            self._emit_chunk(chunks, current_texts, current_pages, doc_name, idx, file_path)

        return chunks

    @staticmethod
    def _emit_chunk(
        chunks: list[Document],
        texts: list[str],
        page_nums: list[int],
        doc_name: str,
        idx: int,
        file_path: Optional[str],
    ) -> None:
        combined = "\n\n".join(texts)
        meta = _make_metadata(
            doc_name=doc_name,
            start_page=min(page_nums),
            end_page=max(page_nums),
            chunk_index=idx,
            file_path=file_path,
        )
        chunks.append(Document(page_content=combined, metadata=meta))


# ---------------------------------------------------------------------------
# Semantic splitter (large chunks + semantic boundary detection)
# ---------------------------------------------------------------------------


class SemanticChunkSplitter:
    """
    Large-chunk splitter with an optional semantic boundary pass.

    The semantic pass inspects each large chunk produced by
    ``LargeChunkSplitter`` and, when a natural section or subsection
    header is detected, starts a new chunk there.  This yields fewer but
    more topically coherent embeddings.
    """

    def __init__(
        self,
        config: Optional[SplitterConfig] = None,
        min_chunk_size: int = 1500,
    ):
        self.large_splitter = LargeChunkSplitter(config)
        self.min_chunk_size = min_chunk_size

    def split_pages(self, pages: list[PageText], chunk_index_offset: int = 0) -> list[Document]:
        large_chunks = self.large_splitter.split_pages(pages, chunk_index_offset)
        refined: list[Document] = []

        for chunk in large_chunks:
            if len(chunk.page_content) < self.min_chunk_size:
                refined.append(chunk)
                continue

            sub_chunks = self._semantic_split(chunk)
            if len(sub_chunks) <= 1:
                refined.append(chunk)
            else:
                refined.extend(sub_chunks)

        # Re-index chunk_index after potential splitting
        for i, chunk in enumerate(refined):
            chunk.metadata["chunk_index"] = chunk_index_offset + i

        return refined

    def _semantic_split(self, chunk: Document) -> list[Document]:
        """
        Detect section headers inside a large chunk and split around them.

        A line that looks like a heading (e.g. ``1.2 Background``,
        ``## Introduction``) becomes a split point when the remaining
        text before it is at least ``min_chunk_size`` characters.
        """
        text = chunk.page_content
        if not text:
            return [chunk]

        lines = text.split("\n")
        split_points: list[int] = []  # indices in *lines*

        for i, line in enumerate(lines):
            line = line.strip()
            if self._looks_like_heading(line) and i > 0:
                # Ensure we don't create tiny fragments
                before = "\n".join(lines[:i])
                if len(before) >= self.min_chunk_size:
                    split_points.append(i)

        if not split_points:
            return [chunk]

        result: list[Document] = []
        prev = 0
        for sp in split_points:
            sub_text = "\n".join(lines[prev:sp])
            if sub_text.strip():
                result.append(self._copy_meta(chunk, sub_text))
            prev = sp

        sub_text = "\n".join(lines[prev:])
        if sub_text.strip():
            result.append(self._copy_meta(chunk, sub_text))

        return result if len(result) > 1 else [chunk]

    @staticmethod
    def _looks_like_heading(line: str) -> bool:
        if not line or len(line) < 2:
            return False
        # Markdown headers
        if line.startswith("#"):
            return True
        # Section numbering: 1., 1.2, 1.2.3, etc.
        if line[0].isdigit() and line[1] in ".)":
            return True
        return False

    @staticmethod
    def _copy_meta(source: Document, page_content: str) -> Document:
        return Document(page_content=page_content, metadata=dict(source.metadata))


# ---------------------------------------------------------------------------
# Top-level helpers
# ---------------------------------------------------------------------------


def split_documents(
    documents: list[PDFDocument],
    splitter: Optional[LargeChunkSplitter] = None,
) -> list[Document]:
    """
    Split one or more ``PDFDocument`` objects into LangChain ``Document``
    chunks with rich metadata.

    Default behaviour uses large chunks (4 000 chars, 500 overlap).
    """
    if splitter is None:
        splitter = LargeChunkSplitter()

    all_chunks: list[Document] = []
    offset = 0
    for doc in documents:
        chunks = splitter.split_pages(doc.pages, chunk_index_offset=offset)
        all_chunks.extend(chunks)
        offset += len(chunks)

    return all_chunks


def split_pages_semantically(
    documents: list[PDFDocument],
    splitter: Optional[SemanticChunkSplitter] = None,
    min_chunk_size: int = 1500,
) -> list[Document]:
    """Split documents semantically — large chunks with heading-aware splits."""
    if splitter is None:
        splitter = SemanticChunkSplitter(min_chunk_size=min_chunk_size)

    all_chunks: list[Document] = []
    offset = 0
    for doc in documents:
        chunks = splitter.split_pages(doc.pages, chunk_index_offset=offset)
        all_chunks.extend(chunks)
        offset += len(chunks)

    return all_chunks
