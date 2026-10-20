"""
Document tools for the free agent.

These are the concrete tools the agent can call in its ReAct loop.
Each tool corresponds to a capability mentioned by the user:

* ``search_documents`` — vector-search with smart embedding + reranking
* ``read_page``       — read a specific page ("special pages")
* ``read_pages``      — read a range of pages
* ``list_documents``  — enumerate loaded PDFs
* ``summarize``       — summarise arbitrary text or a page range
* ``compare_documents`` — compare information across multiple documents
* ``get_metadata``    — retrieve chunk metadata (page refs, source)

Tools are registered with the :class:`ToolRegistry` via
:meth:`DocumentToolKit.register_all`.
"""

from __future__ import annotations

import re
from typing import Any, Optional

from backend.documents.loader import load_document
from backend.documents.pdf_loader import PDFDocument
from backend.embeddings.smart_embedding import SmartEmbedding
from backend.embeddings.vectoreStore import SmartVectorStore


class DocumentToolKit:
    """
    A collection of document-search and -reading tools bound to a
    :class:`SmartVectorStore` and/or a list of loaded :class:`PDFDocument`
    objects.

    Parameters
    ----------
    vector_store
        The smart vector store (FAISS + reranker) for semantic search.
    documents
        Loaded ``PDFDocument`` objects for page-level reading.
    llm
        Optional LLM used by the ``summarize`` tool.
    """

    def __init__(
        self,
        vector_store: Optional[SmartVectorStore] = None,
        documents: Optional[list[PDFDocument]] = None,
        llm: Optional[Any] = None,
    ):
        self.vector_store = vector_store
        self.documents: list[PDFDocument] = documents or []
        self._doc_map: dict[str, PDFDocument] = {d.name: d for d in self.documents}
        self.llm = llm

    # ------------------------------------------------------------------
    # Builder
    # ------------------------------------------------------------------

    @classmethod
    def from_chunks(
        cls,
        chunks: list,
        documents: Optional[list[PDFDocument]] = None,
        embedding: Optional[Any] = None,
    ) -> "DocumentToolKit":
        """Create a tool kit from chunks (builds a SmartVectorStore)."""
        from backend.embeddings.vectoreStore import SmartVectorStore

        emb = embedding or SmartEmbedding()
        vs = SmartVectorStore(embedding=emb).build(chunks)
        return cls(vector_store=vs, documents=documents)

    @classmethod
    def from_file_paths(
        cls,
        file_paths: list[str],
        embedding: Optional[Any] = None,
        llm: Optional[Any] = None,
    ) -> "DocumentToolKit":
        """End-to-end: load PDFs, split, build store, create tools."""
        from backend.documents.processors import DocumentProcessor, ProcessingConfig
        from backend.embeddings.vectoreStore import SmartVectorStore

        docs = [load_document(path) for path in file_paths]
        processor = DocumentProcessor(ProcessingConfig())
        chunks = processor.process_documents(docs)

        emb = embedding or SmartEmbedding()
        vs = SmartVectorStore(embedding=emb).build(chunks)
        return cls(vector_store=vs, documents=docs, llm=llm)

    def add_documents(self, documents: list[PDFDocument]) -> None:
        self.documents.extend(documents)
        for d in documents:
            self._doc_map[d.name] = d

    def register_all(self, registry) -> None:
        """Register every tool in this kit with a :class:`ToolRegistry`."""
        from backend.agent.tools.registry import Tool

        registry.register(
            Tool(
                name="search_documents",
                description=(
                    "Search the document collection for content relevant to "
                    "a query. Uses hybrid search (BM25 + dense embeddings) "
                    "with RRF fusion for high precision. Returns matching text "
                    "snippets with document name and page metadata."
                ),
                parameters={
                    "type": "object",
                    "properties": {
                        "query": {
                            "type": "string",
                            "description": "The search query. Be specific.",
                        },
                        "top_k": {
                            "type": "integer",
                            "description": "Number of results (default 5, max 15).",
                            "default": 5,
                        },
                    },
                    "required": ["query"],
                },
                func=self.search_documents,
            )
        )

        registry.register(
            Tool(
                name="read_page",
                description=(
                    "Read the full text of a specific page from a loaded "
                    "document (PDF page, or logical section for Word/Excel). Use this after a search to examine the "
                    "source in detail or to read a page that was cited in "
                    "search results."
                ),
                parameters={
                    "type": "object",
                    "properties": {
                        "doc_name": {
                            "type": "string",
                            "description": "Name of the uploaded file.",
                        },
                        "page_num": {
                            "type": "integer",
                            "description": "1-indexed PDF page or non-PDF section number.",
                        },
                    },
                    "required": ["doc_name", "page_num"],
                },
                func=self.read_page,
            )
        )

        registry.register(
            Tool(
                name="read_pages",
                description=(
                    "Read a contiguous range of pages from a PDF document. "
                    "Useful for reviewing a section that spans multiple "
                    "pages."
                ),
                parameters={
                    "type": "object",
                    "properties": {
                        "doc_name": {
                            "type": "string",
                            "description": "Name of the uploaded file.",
                        },
                        "start_page": {
                            "type": "integer",
                            "description": "First page (1-indexed).",
                        },
                        "end_page": {
                            "type": "integer",
                            "description": "Last page (1-indexed, inclusive).",
                        },
                    },
                    "required": ["doc_name", "start_page", "end_page"],
                },
                func=self.read_pages,
            )
        )

        registry.register(
            Tool(
                name="list_documents",
                description=("List all loaded documents with their page counts and file paths."),
                parameters={
                    "type": "object",
                    "properties": {},
                    "required": [],
                },
                func=self.list_documents,
            )
        )

        registry.register(
            Tool(
                name="summarize",
                description=(
                    "Generate a concise summary of the provided text. The "
                    "input can be raw text or a reference to content you "
                    "already retrieved."
                ),
                parameters={
                    "type": "object",
                    "properties": {
                        "text": {
                            "type": "string",
                            "description": "The text to summarize (max ~8000 tokens).",
                        },
                    },
                    "required": ["text"],
                },
                func=self.summarize,
            )
        )

        registry.register(
            Tool(
                name="compare_documents",
                description=(
                    "Search for a topic across ALL loaded documents and "
                    "return results grouped by document, to see how each "
                    "document treats the same subject."
                ),
                parameters={
                    "type": "object",
                    "properties": {
                        "query": {
                            "type": "string",
                            "description": "The comparison topic / query.",
                        },
                        "top_k_per_doc": {
                            "type": "integer",
                            "description": "Results per document (default 3).",
                            "default": 3,
                        },
                    },
                    "required": ["query"],
                },
                func=self.compare_documents,
            )
        )

        registry.register(
            Tool(
                name="get_metadata",
                description=(
                    "Retrieve metadata about a chunk or page — document "
                    "name, page range, source file path. Useful for "
                    "verifying citations."
                ),
                parameters={
                    "type": "object",
                    "properties": {
                        "doc_name": {
                            "type": "string",
                            "description": "Name of the uploaded file.",
                        },
                        "page_num": {
                            "type": "integer",
                            "description": "1-indexed PDF page or non-PDF section number.",
                        },
                    },
                    "required": ["doc_name", "page_num"],
                },
                func=self.get_metadata,
            )
        )

    # ------------------------------------------------------------------
    # Tool implementations
    # ------------------------------------------------------------------

    # -- search_documents ------------------------------------------------

    def search_documents(self, query: str, top_k: int = 5) -> str:
        """Vector-search the document collection."""
        if self.vector_store is None:
            return "ERROR: No vector store available. Documents not loaded."

        top_k = max(1, min(top_k, 15))
        docs = self.vector_store.search(query, top_k=top_k)

        if not docs:
            return "No results found."

        lines = []
        for i, doc in enumerate(docs, 1):
            meta = doc.metadata
            lines.append(
                f"--- Result {i} ---\n"
                f"Document: {meta.get('doc_name', 'unknown')}\n"
                f"Pages: {meta.get('start_page', '?')}"
                f"-{meta.get('end_page', '?')}\n"
                f"Text: {doc.page_content[:800].strip()}"
            )
        return "\n".join(lines)

    # -- read_page -------------------------------------------------------

    def read_page(self, doc_name: str, page_num: int) -> str:
        """Read a single page from a loaded PDFDocument."""
        doc = self._find_document(doc_name)
        if doc is None:
            return self._list_available_error()

        page = doc.get_page(page_num)
        if page is None:
            return f"ERROR: Page {page_num} is out of range. Document has {doc.total_pages} pages."

        header = f"=== {doc.name} — Page {page.page_number} of {page.total_pages} ==="
        return f"{header}\n\n{page.text.strip()}"

    def read_pages(self, doc_name: str, start_page: int, end_page: int) -> str:
        """Read a range of pages from a loaded PDFDocument."""
        doc = self._find_document(doc_name)
        if doc is None:
            return self._list_available_error()

        if start_page > end_page:
            start_page, end_page = end_page, start_page

        pages = doc.get_pages(start_page, end_page)
        if not pages:
            return f"ERROR: Pages {start_page}-{end_page} are out of range. Document has {doc.total_pages} pages."

        parts = [f"=== {doc.name} — Pages {p.page_number} of {p.total_pages} ===" for p in pages]
        texts = [p.text.strip() for p in pages]
        return "\n\n".join(f"{h}\n\n{t}" for h, t in zip(parts, texts))

    # -- list_documents --------------------------------------------------

    def list_documents(self) -> str:
        """List all loaded documents with metadata."""
        if not self.documents:
            return "No documents loaded."

        lines = ["Loaded documents:"]
        for doc in self.documents:
            loc = doc.file_path or "(in-memory)"
            lines.append(f"  • {doc.name} — {doc.total_pages} pages — {loc}")
        return "\n".join(lines)

    # -- summarize -------------------------------------------------------

    def summarize(self, text: str) -> str:
        """Summarize text using the configured LLM (or extractive fallback)."""
        if not text.strip():
            return "No text provided to summarize."

        # Truncate to avoid token limits
        max_chars = 8000
        if len(text) > max_chars:
            text = text[:max_chars] + "... [truncated]"

        if self.llm is not None:
            try:
                from langchain_core.messages import HumanMessage

                summary_prompt = "Summarize the following text in 3-5 bullet points:\n\n{text}\n\nSummary:"

                if hasattr(self.llm, "invoke"):
                    response = self.llm.invoke([HumanMessage(content=summary_prompt.format(text=text))])
                    return response.content if hasattr(response, "content") else str(response)
                return self._extractive_summary(text)
            except Exception:
                # Fall through to extractive
                pass

        # Extractive fallback
        return self._extractive_summary(text)

    @staticmethod
    def _extractive_summary(text: str, num_sentences: int = 3) -> str:
        sentences = re.split(r"(?<=[.!?])\s+", text.strip())
        top = sentences[:num_sentences]
        return "• " + "\n• ".join(top) if top else text[:200]

    # -- compare_documents -----------------------------------------------

    def compare_documents(self, query: str, top_k_per_doc: int = 3) -> str:
        """Search across all documents and group results by source."""
        if not self.documents:
            return "No documents loaded."

        if self.vector_store is None:
            return "No vector store available."

        results = self.vector_store.search(query, top_k=top_k_per_doc * len(self.documents))

        grouped: dict[str, list] = {}
        for doc in results:
            name = doc.metadata.get("doc_name", "unknown")
            grouped.setdefault(name, []).append(doc)

        if not grouped:
            return f"No results for '{query}' across documents."

        lines = [f"=== Comparison for: '{query}' ==="]
        for name, docs in grouped.items():
            lines.append(f"\n--- {name} ({len(docs)} matches) ---")
            for i, doc in enumerate(docs, 1):
                meta = doc.metadata
                lines.append(f"  {i}. [p. {meta.get('start_page', '?')}] {doc.page_content[:300].strip()}")
        return "\n".join(lines)

    # -- get_metadata ----------------------------------------------------

    def get_metadata(self, doc_name: str, page_num: int) -> str:
        """Return metadata about a specific page in a document."""
        doc = self._find_document(doc_name)
        if doc is None:
            return self._list_available_error()

        page = doc.get_page(page_num)
        if page is None:
            return f"ERROR: Page {page_num} not found (doc has {doc.total_pages} pages)."

        # Also check which chunks reference this page
        chunk_refs = []
        if self.vector_store is not None and self.vector_store.embedding is not None:
            chunks = self.vector_store.embedding.get_chunks_by_page(doc_name, page.page_number)
            chunk_refs = [
                f"chunk {c.metadata.get('chunk_index', '?')} "
                f"pages {c.metadata.get('start_page', '?')}-{c.metadata.get('end_page', '?')}"
                for c in chunks
            ]

        return (
            f"Document: {doc.name}\n"
            f"File: {doc.file_path or '(in-memory)'}\n"
            f"Total pages: {doc.total_pages}\n"
            f"Page: {page.page_number}\n"
            f"Chunks referencing this page: {chunk_refs if chunk_refs else 'none (not indexed)'}"
        )

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _find_document(self, doc_name: str) -> Optional[PDFDocument]:
        """Find a document by exact or fuzzy name match."""
        if doc_name in self._doc_map:
            return self._doc_map[doc_name]

        # Fuzzy: allow substring or case-insensitive match
        lower = doc_name.lower()
        for name, doc in self._doc_map.items():
            if lower in name.lower() or name.lower() in lower:
                return doc

        return None

    def _list_available_error(self) -> str:
        names = ", ".join(self._doc_map.keys()) if self._doc_map else "none"
        return f"ERROR: Document not found. Available documents: {names}"
