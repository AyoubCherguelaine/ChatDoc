"""
Google AI Document Intelligence service.

Provides advanced document understanding, multimodal processing, structural parsing,
key-value entity extraction, and table analysis powered by Google AI (Gemini / Document AI).
"""

from __future__ import annotations

import logging
import os
from pathlib import Path
from typing import Any, Optional

logger = logging.getLogger(__name__)

GOOGLE_AI_DOCUMENT_SYSTEM_PROMPT = """\
You are Google AI Document Intelligence, an advanced multimodal document understanding engine.
Your purpose is to thoroughly examine documents, analyze layout hierarchy, extract key-value entities,
tabulate tabular data, and provide comprehensive, high-fidelity insights.

Guidelines:
1. Identify the document type, genre, and overall structure.
2. Extract key entities and metadata (e.g. organizations, dates, monetary amounts, reference IDs, parties).
3. Identify and transcribe tables into clean Markdown tables.
4. Highlight key clauses, commitments, or data points with specific page/section citations.
5. Present structured, clear, and citable Markdown output.
"""


class GoogleDocumentAIService:
    """Service for processing documents with Google AI / Gemini."""

    def __init__(self, llm: Any = None, api_key: Optional[str] = None):
        self.api_key = api_key or os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY")
        self.llm = llm

    def _get_llm(self) -> Any:
        if self.llm is not None:
            return self.llm
        try:
            from backend.chat.chatWithVSDB import get_llm
            return get_llm(model_name=os.getenv("DEFAULT_GOOGLE_MODEL", "gemini-1.5-flash"))
        except Exception:
            try:
                from langchain_google_genai import ChatGoogleGenerativeAI
                kwargs = {"model": "gemini-1.5-flash"}
                if self.api_key:
                    kwargs["google_api_key"] = self.api_key
                return ChatGoogleGenerativeAI(**kwargs)
            except Exception as exc:
                logger.warning("Could not initialize Google GenAI LLM: %s. Using default fallback.", exc)
                from backend.chat.chatWithVSDB import get_llm
                return get_llm()

    def analyze_document_text(
        self,
        text: str,
        doc_name: str = "document",
        task: str = "comprehensive",
    ) -> str:
        """Analyze document text using Google AI Document Intelligence."""
        llm = self._get_llm()

        task_instructions = {
            "entities": "Extract all key entities, metadata, dates, identifiers, and key-value pairs into structured tables and lists.",
            "layout": "Analyze the structural layout, section headers, hierarchy, and organizational flow of the document.",
            "tables": "Extract all numerical tables, matrices, and tabular datasets into clear Markdown tables.",
            "comprehensive": (
                "Provide a comprehensive Google AI Document Intelligence report:\n"
                "- Document Classification & Metadata\n"
                "- Executive Summary\n"
                "- Key Entities & Form Fields (Key-Value pairs)\n"
                "- Tables & Structured Data\n"
                "- Key Findings & Citations"
            ),
        }.get(task, task)

        prompt = (
            f"{GOOGLE_AI_DOCUMENT_SYSTEM_PROMPT}\n\n"
            f"=== DOCUMENT: {doc_name} ===\n"
            f"Task: {task_instructions}\n\n"
            f"Document Text:\n{text[:12000]}\n\n"
            f"Produce the structured Google AI Document analysis in GitHub-flavored Markdown:"
        )

        try:
            from langchain_core.messages import HumanMessage, SystemMessage
            response = llm.invoke([
                SystemMessage(content=GOOGLE_AI_DOCUMENT_SYSTEM_PROMPT),
                HumanMessage(content=prompt),
            ])
            content = response.content if hasattr(response, "content") else str(response)
            return content.strip() if isinstance(content, str) else str(content)
        except Exception as exc:
            return f"ERROR: Google AI Document analysis failed: {exc}"

    def analyze_pdf(
        self,
        pdf_path: Path,
        task: str = "comprehensive",
    ) -> str:
        """Analyze a PDF file using text or vision-based extraction."""
        pdf_path = Path(pdf_path)
        if not pdf_path.exists():
            return f"ERROR: File not found: {pdf_path}"

        # Attempt to read text directly via PyMuPDF or pypdf
        text = ""
        try:
            import fitz  # PyMuPDF
            doc = fitz.open(str(pdf_path))
            pages_text = [page.get_text() for page in doc]
            text = "\n\n".join(pages_text)
            doc.close()
        except Exception:
            pass

        if not text.strip():
            # Scanned PDF fallback: use vision / OCR
            try:
                from backend.agent.tools.ocr import OcrService
                ocr_service = OcrService(llm=self._get_llm())
                text = ocr_service.ocr_read_pages(pdf_path, 1, 5)
            except Exception as exc:
                return f"ERROR: Failed to read PDF content: {exc}"

        return self.analyze_document_text(text, doc_name=pdf_path.name, task=task)
