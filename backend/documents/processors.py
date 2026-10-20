"""
Document processing pipeline.

Orchestrates loading PDFs, splitting into large metadata-rich chunks,
and (optionally) summarising each chunk for HyDE-style retrieval.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

from langchain_core.documents import Document

from .loader import load_document
from .pdf_loader import PDFDocument
from .splitter import (
    LargeChunkSplitter,
    SemanticChunkSplitter,
    SplitterConfig,
    split_documents,
    split_pages_semantically,
)


@dataclass
class ProcessingConfig:
    """Configuration for the document processing pipeline."""

    # Splitting
    use_semantic_split: bool = True
    chunk_size: int = 4000
    chunk_overlap: int = 500
    min_semantic_chunk: int = 1500

    # Metadata
    attach_summaries: bool = False  # Generate per-chunk summaries for HyDE

    # Storage
    db_path: str = "faiss_index"

    def to_splitter_config(self) -> SplitterConfig:
        return SplitterConfig(
            chunk_size=self.chunk_size,
            chunk_overlap=self.chunk_overlap,
        )


class DocumentProcessor:
    """
    End-to-end document processor.

    Usage::

        processor = DocumentProcessor(ProcessingConfig())
        chunks = processor.process(file_paths)
        # chunks: list[Document] with metadata + large-chunk content
    """

    def __init__(self, config: Optional[ProcessingConfig] = None):
        self.config = config or ProcessingConfig()

    def process_files(self, file_paths: list[str]) -> list[Document]:
        """Load and split supported document files."""
        docs = [load_document(path) for path in file_paths]
        return self.process_documents(docs)

    def process_uploaded_files(self, uploaded_files) -> tuple[list[Document], list[PDFDocument]]:
        """
        Process Streamlit ``UploadedFile`` objects.

        Writes temp files, loads them as ``PDFDocument``, splits, and
        returns the chunks plus the original documents (needed by the
        agent's ``read_page`` tool).
        """
        temp_paths: list[str] = []
        try:
            for uf in uploaded_files:
                import tempfile
                from pathlib import Path

                suffix = Path(uf.name).suffix.lower() or ".pdf"
                with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp:
                    tmp.write(uf.read())
                    temp_paths.append(tmp.name)

            docs = [load_document(path) for path in temp_paths]
            chunks = self.process_documents(docs)
            return chunks, docs
        finally:
            for p in temp_paths:
                try:
                    import os

                    os.unlink(p)
                except OSError:
                    pass

    def process_documents(self, documents: list[PDFDocument]) -> list[Document]:
        """Split already-loaded ``PDFDocument`` objects into chunks."""
        if self.config.use_semantic_split:
            splitter: LargeChunkSplitter | SemanticChunkSplitter = SemanticChunkSplitter(
                config=self.config.to_splitter_config(),
                min_chunk_size=self.config.min_semantic_chunk,
            )
            chunks = split_pages_semantically(documents, splitter)  # type: ignore[arg-type]
        else:
            splitter = LargeChunkSplitter(self.config.to_splitter_config())
            chunks = split_documents(documents, splitter)

        if self.config.attach_summaries:
            chunks = self._attach_summaries(chunks)

        return chunks

    def _attach_summaries(self, chunks: list[Document]) -> list[Document]:
        """
        Generate a short extractive summary for each chunk and store it
        in metadata.  These summaries can be used as *hypothetical*
        query expansions (HyDE) to improve retrieval recall for
        long-tail questions.
        """
        for chunk in chunks:
            summary = self._extractive_summary(chunk.page_content)
            chunk.metadata["summary"] = summary

        return chunks

    @staticmethod
    def _extractive_summary(text: str, max_sentences: int = 3) -> str:
        import re

        sentences = re.split(r"(?<=[.!?])\s+", text.strip())
        return " ".join(sentences[:max_sentences]) if sentences else text[:200]
