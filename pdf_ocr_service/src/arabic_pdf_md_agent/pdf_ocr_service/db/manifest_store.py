from __future__ import annotations

from pathlib import Path

from arabic_pdf_md_agent.base.schemas import DocumentExtractionResult, RunSummary, dataclass_to_json
from arabic_pdf_md_agent.base.utils import write_json


class ManifestStore:
    """Writes per-document metadata and global run summary."""

    def __init__(self, output_dir: Path) -> None:
        self.output_dir = output_dir
        self.manifests_dir = output_dir / "_manifests"

    def save_document(self, result: DocumentExtractionResult) -> None:
        doc_name = result.pdf_path.stem
        payload = dataclass_to_json(result)
        write_json(self.manifests_dir / f"{doc_name}.json", payload)

    def save_summary(self, summary: RunSummary) -> None:
        payload = dataclass_to_json(summary)
        write_json(self.output_dir / "run_summary.json", payload)
