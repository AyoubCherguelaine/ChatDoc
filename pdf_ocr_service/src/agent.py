from __future__ import annotations

from arabic_pdf_md_agent.base.agent import DomainAgent
from arabic_pdf_md_agent.base.schemas import (
    DocumentExtractionResult,
    ExtractionConfig,
    RunSummary,
)


class ArabicPdfMdCoordinator:
    """Stable coordinator entrypoint for the Arabic PDF Markdown mini-project."""

    def __init__(
        self,
        domain_agent: DomainAgent | None = None,
    ) -> None:
        if domain_agent is None:
            from arabic_pdf_md_agent.pdf_ocr_service.agent import PdfOcrDomainAgent

            self.domain_agent = PdfOcrDomainAgent()
        else:
            self.domain_agent = domain_agent

    def run(self, config: ExtractionConfig) -> tuple[list[DocumentExtractionResult], RunSummary]:
        return self.domain_agent.run(config)


def run_extraction(config: ExtractionConfig) -> tuple[list[DocumentExtractionResult], RunSummary]:
    return ArabicPdfMdCoordinator().run(config)
