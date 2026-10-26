from __future__ import annotations

import sqlite3
from pathlib import Path
from typing import Any

from arabic_pdf_md_agent.base.utils import utc_now_iso


class GeminiUsageStore:
    """SQLite usage ledger for batch OCR runs."""

    def __init__(self, db_path: Path) -> None:
        self.db_path = db_path

    def initialize(self) -> None:
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        with self._connect() as conn:
            conn.executescript(
                """
                CREATE TABLE IF NOT EXISTS batch_runs(
                  run_id TEXT PRIMARY KEY,
                  model TEXT NOT NULL,
                  input_dir TEXT NOT NULL,
                  output_dir TEXT NOT NULL,
                  batch_job_name TEXT,
                  status TEXT NOT NULL,
                  created_at TEXT NOT NULL,
                  updated_at TEXT NOT NULL,
                  input_price_per_1m_usd REAL NOT NULL,
                  output_price_per_1m_usd REAL NOT NULL,
                  total_pdfs INTEGER NOT NULL DEFAULT 0,
                  total_pages INTEGER NOT NULL DEFAULT 0,
                  input_tokens INTEGER NOT NULL DEFAULT 0,
                  output_tokens INTEGER NOT NULL DEFAULT 0,
                  total_tokens INTEGER NOT NULL DEFAULT 0,
                  estimated_cost_usd REAL NOT NULL DEFAULT 0
                );

                CREATE TABLE IF NOT EXISTS pdf_usage(
                  run_id TEXT NOT NULL,
                  pdf_path TEXT NOT NULL,
                  pdf_stem TEXT NOT NULL,
                  status TEXT NOT NULL,
                  total_pages INTEGER NOT NULL DEFAULT 0,
                  processed_pages INTEGER NOT NULL DEFAULT 0,
                  failed_pages INTEGER NOT NULL DEFAULT 0,
                  input_tokens INTEGER NOT NULL DEFAULT 0,
                  output_tokens INTEGER NOT NULL DEFAULT 0,
                  total_tokens INTEGER NOT NULL DEFAULT 0,
                  estimated_cost_usd REAL NOT NULL DEFAULT 0,
                  updated_at TEXT NOT NULL,
                  PRIMARY KEY (run_id, pdf_path)
                );

                CREATE TABLE IF NOT EXISTS page_usage(
                  run_id TEXT NOT NULL,
                  request_key TEXT NOT NULL,
                  pdf_path TEXT NOT NULL,
                  page_number INTEGER NOT NULL,
                  status TEXT NOT NULL,
                  input_tokens INTEGER NOT NULL DEFAULT 0,
                  output_tokens INTEGER NOT NULL DEFAULT 0,
                  total_tokens INTEGER NOT NULL DEFAULT 0,
                  estimated_cost_usd REAL NOT NULL DEFAULT 0,
                  error TEXT,
                  updated_at TEXT NOT NULL,
                  PRIMARY KEY (run_id, request_key)
                );
                """
            )

    def upsert_run(
        self,
        *,
        run_id: str,
        model: str,
        input_dir: Path,
        output_dir: Path,
        status: str,
        input_price_per_1m_usd: float,
        output_price_per_1m_usd: float,
        total_pdfs: int = 0,
        total_pages: int = 0,
        batch_job_name: str | None = None,
    ) -> None:
        now = utc_now_iso()
        with self._connect() as conn:
            conn.execute(
                """
                INSERT INTO batch_runs(
                  run_id, model, input_dir, output_dir, batch_job_name, status,
                  created_at, updated_at, input_price_per_1m_usd, output_price_per_1m_usd,
                  total_pdfs, total_pages
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(run_id) DO UPDATE SET
                  model=excluded.model,
                  input_dir=excluded.input_dir,
                  output_dir=excluded.output_dir,
                  batch_job_name=COALESCE(excluded.batch_job_name, batch_runs.batch_job_name),
                  status=excluded.status,
                  updated_at=excluded.updated_at,
                  input_price_per_1m_usd=excluded.input_price_per_1m_usd,
                  output_price_per_1m_usd=excluded.output_price_per_1m_usd,
                  total_pdfs=excluded.total_pdfs,
                  total_pages=excluded.total_pages
                """,
                (
                    run_id,
                    model,
                    str(input_dir),
                    str(output_dir),
                    batch_job_name,
                    status,
                    now,
                    now,
                    input_price_per_1m_usd,
                    output_price_per_1m_usd,
                    total_pdfs,
                    total_pages,
                ),
            )

    def update_run_status(self, run_id: str, status: str, batch_job_name: str | None = None) -> None:
        with self._connect() as conn:
            conn.execute(
                """
                UPDATE batch_runs
                SET status = ?,
                    batch_job_name = COALESCE(?, batch_job_name),
                    updated_at = ?
                WHERE run_id = ?
                """,
                (status, batch_job_name, utc_now_iso(), run_id),
            )

    def upsert_page_usage(
        self,
        *,
        run_id: str,
        request_key: str,
        pdf_path: str,
        page_number: int,
        status: str,
        input_tokens: int,
        output_tokens: int,
        total_tokens: int,
        estimated_cost_usd: float,
        error: str | None = None,
    ) -> None:
        with self._connect() as conn:
            conn.execute(
                """
                INSERT INTO page_usage(
                  run_id, request_key, pdf_path, page_number, status,
                  input_tokens, output_tokens, total_tokens, estimated_cost_usd,
                  error, updated_at
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(run_id, request_key) DO UPDATE SET
                  pdf_path=excluded.pdf_path,
                  page_number=excluded.page_number,
                  status=excluded.status,
                  input_tokens=excluded.input_tokens,
                  output_tokens=excluded.output_tokens,
                  total_tokens=excluded.total_tokens,
                  estimated_cost_usd=excluded.estimated_cost_usd,
                  error=excluded.error,
                  updated_at=excluded.updated_at
                """,
                (
                    run_id,
                    request_key,
                    pdf_path,
                    page_number,
                    status,
                    input_tokens,
                    output_tokens,
                    total_tokens,
                    estimated_cost_usd,
                    error,
                    utc_now_iso(),
                ),
            )

    def rebuild_pdf_usage(self, run_id: str, pdf_pages: dict[str, dict[str, Any]]) -> None:
        now = utc_now_iso()
        with self._connect() as conn:
            for pdf_path, metadata in pdf_pages.items():
                row = conn.execute(
                    """
                    SELECT
                      SUM(CASE WHEN status = 'success' THEN 1 ELSE 0 END) AS processed_pages,
                      SUM(CASE WHEN status != 'success' THEN 1 ELSE 0 END) AS failed_pages,
                      COALESCE(SUM(input_tokens), 0) AS input_tokens,
                      COALESCE(SUM(output_tokens), 0) AS output_tokens,
                      COALESCE(SUM(total_tokens), 0) AS total_tokens,
                      COALESCE(SUM(estimated_cost_usd), 0) AS estimated_cost_usd
                    FROM page_usage
                    WHERE run_id = ? AND pdf_path = ?
                    """,
                    (run_id, pdf_path),
                ).fetchone()
                processed_pages = int(row["processed_pages"] or 0)
                failed_pages = int(row["failed_pages"] or 0)
                total_pages = int(metadata.get("total_pages") or 0)
                explicit_status = str(metadata.get("status") or "")
                if explicit_status in {"invalid_pdf", "skipped_existing"}:
                    status = explicit_status
                elif processed_pages == 0 and total_pages > 0:
                    status = "failed"
                elif failed_pages > 0 or processed_pages < total_pages:
                    status = "partial"
                else:
                    status = "success"
                conn.execute(
                    """
                    INSERT INTO pdf_usage(
                      run_id, pdf_path, pdf_stem, status, total_pages,
                      processed_pages, failed_pages, input_tokens, output_tokens,
                      total_tokens, estimated_cost_usd, updated_at
                    )
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    ON CONFLICT(run_id, pdf_path) DO UPDATE SET
                      pdf_stem=excluded.pdf_stem,
                      status=excluded.status,
                      total_pages=excluded.total_pages,
                      processed_pages=excluded.processed_pages,
                      failed_pages=excluded.failed_pages,
                      input_tokens=excluded.input_tokens,
                      output_tokens=excluded.output_tokens,
                      total_tokens=excluded.total_tokens,
                      estimated_cost_usd=excluded.estimated_cost_usd,
                      updated_at=excluded.updated_at
                    """,
                    (
                        run_id,
                        pdf_path,
                        str(metadata.get("pdf_stem") or Path(pdf_path).stem),
                        status,
                        total_pages,
                        processed_pages,
                        failed_pages,
                        int(row["input_tokens"] or 0),
                        int(row["output_tokens"] or 0),
                        int(row["total_tokens"] or 0),
                        float(row["estimated_cost_usd"] or 0.0),
                        now,
                    ),
                )

    def rebuild_run_totals(self, run_id: str, status: str) -> dict[str, Any]:
        with self._connect() as conn:
            row = conn.execute(
                """
                SELECT
                  COUNT(*) AS total_pdfs,
                  COALESCE(SUM(total_pages), 0) AS total_pages,
                  COALESCE(SUM(input_tokens), 0) AS input_tokens,
                  COALESCE(SUM(output_tokens), 0) AS output_tokens,
                  COALESCE(SUM(total_tokens), 0) AS total_tokens,
                  COALESCE(SUM(estimated_cost_usd), 0) AS estimated_cost_usd
                FROM pdf_usage
                WHERE run_id = ?
                """,
                (run_id,),
            ).fetchone()
            totals = dict(row)
            conn.execute(
                """
                UPDATE batch_runs
                SET status = ?,
                    total_pdfs = ?,
                    total_pages = ?,
                    input_tokens = ?,
                    output_tokens = ?,
                    total_tokens = ?,
                    estimated_cost_usd = ?,
                    updated_at = ?
                WHERE run_id = ?
                """,
                (
                    status,
                    int(totals["total_pdfs"] or 0),
                    int(totals["total_pages"] or 0),
                    int(totals["input_tokens"] or 0),
                    int(totals["output_tokens"] or 0),
                    int(totals["total_tokens"] or 0),
                    float(totals["estimated_cost_usd"] or 0.0),
                    utc_now_iso(),
                    run_id,
                ),
            )
            return totals

    def get_pdf_usage(self, run_id: str, pdf_path: str) -> dict[str, Any] | None:
        with self._connect() as conn:
            row = conn.execute(
                """
                SELECT
                  pdf_path,
                  pdf_stem,
                  status,
                  total_pages,
                  processed_pages,
                  failed_pages,
                  input_tokens,
                  output_tokens,
                  total_tokens,
                  estimated_cost_usd,
                  updated_at
                FROM pdf_usage
                WHERE run_id = ? AND pdf_path = ?
                """,
                (run_id, pdf_path),
            ).fetchone()
        if row is None:
            return None
        return dict(row)

    def fetch_run(self, run_id: str) -> dict[str, Any] | None:
        with self._connect() as conn:
            row = conn.execute("SELECT * FROM batch_runs WHERE run_id = ?", (run_id,)).fetchone()
            return dict(row) if row else None

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn
