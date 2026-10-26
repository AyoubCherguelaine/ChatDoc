from __future__ import annotations

from typing import Protocol

from .schemas import DocumentExtractionResult, ExtractionConfig, RunSummary


class DomainAgent(Protocol):
    """Contract for domain agents called by the coordinator."""

    def run(self, config: ExtractionConfig) -> tuple[list[DocumentExtractionResult], RunSummary]:
        ...
