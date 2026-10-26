from __future__ import annotations

import base64
import time
from pathlib import Path
from typing import Any

import requests

from arabic_pdf_md_agent.base.errors import PdfOcrExternalServiceError
from arabic_pdf_md_agent.base.pricing import (
    DEFAULT_INPUT_COST_USD_PER_1M_TOKENS,
    DEFAULT_OUTPUT_COST_USD_PER_1M_TOKENS,
)
from arabic_pdf_md_agent.base.utils import append_jsonl, utc_now_iso


class GeminiError(PdfOcrExternalServiceError):
    pass


class GeminiVisionClient:
    """Small REST client for Gemini generateContent vision calls."""

    def __init__(
        self,
        api_key: str,
        model: str,
        timeout_seconds: int = 90,
        max_retries: int = 2,
        retry_backoff_seconds: float = 1.25,
        usage_log_path: Path | None = None,
        input_cost_usd_per_1m_tokens: float = DEFAULT_INPUT_COST_USD_PER_1M_TOKENS,
        output_cost_usd_per_1m_tokens: float = DEFAULT_OUTPUT_COST_USD_PER_1M_TOKENS,
    ) -> None:
        self.api_key = api_key
        self.model = model
        self.timeout_seconds = timeout_seconds
        self.max_retries = max(0, max_retries)
        self.retry_backoff_seconds = max(0.0, retry_backoff_seconds)
        self.endpoint = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent"
        self.session = requests.Session()
        self.usage_log_path = usage_log_path
        self.input_cost_usd_per_1m_tokens = max(0.0, input_cost_usd_per_1m_tokens)
        self.output_cost_usd_per_1m_tokens = max(0.0, output_cost_usd_per_1m_tokens)
        self._usage_summary: dict[str, int | float] = {
            "model_calls": 0,
            "input_tokens": 0,
            "output_tokens": 0,
            "total_tokens": 0,
            "estimated_cost_usd": 0.0,
        }

    def generate_markdown_from_image(
        self,
        prompt: str,
        image_bytes: bytes,
        log_context: dict[str, Any] | None = None,
    ) -> str:
        parts: list[dict[str, Any]] = [
            {
                "inline_data": {
                    "mime_type": "image/png",
                    "data": base64.b64encode(image_bytes).decode("utf-8"),
                }
            },
            {"text": prompt},
        ]
        return self._generate_from_parts(
            parts=parts,
            modality="image",
            media_bytes=len(image_bytes),
            log_context=log_context,
        )

    def generate_markdown_from_pdf(
        self,
        prompt: str,
        pdf_bytes: bytes,
        log_context: dict[str, Any] | None = None,
    ) -> str:
        parts: list[dict[str, Any]] = [
            {
                "inline_data": {
                    "mime_type": "application/pdf",
                    "data": base64.b64encode(pdf_bytes).decode("utf-8"),
                }
            },
            {"text": prompt},
        ]
        return self._generate_from_parts(
            parts=parts,
            modality="pdf",
            media_bytes=len(pdf_bytes),
            log_context=log_context,
        )

    def _generate_from_parts(
        self,
        parts: list[dict[str, Any]],
        modality: str,
        media_bytes: int,
        log_context: dict[str, Any] | None = None,
    ) -> str:
        payload = {
            "contents": [{"parts": parts}],
            "generationConfig": {
                "temperature": 0,
                "topP": 0.95,
            },
        }

        total_attempts = self.max_retries + 1
        last_error: GeminiError | None = None

        for attempt in range(1, total_attempts + 1):
            started = time.monotonic()
            try:
                response = self.session.post(
                    self.endpoint,
                    params={"key": self.api_key},
                    json=payload,
                    timeout=self.timeout_seconds,
                )
            except requests.RequestException as error:
                elapsed_ms = int((time.monotonic() - started) * 1000)
                self._log_usage_event(
                    event="gemini_request_error",
                    modality=modality,
                    media_bytes=media_bytes,
                    attempt=attempt,
                    elapsed_ms=elapsed_ms,
                    log_context=log_context,
                    error=f"{error.__class__.__name__}: {error}",
                )
                last_error = GeminiError(f"Gemini request failed: {error.__class__.__name__}: {error}")
                if attempt < total_attempts:
                    self._sleep_before_retry(attempt=attempt)
                    continue
                raise last_error from error

            try:
                data = response.json()
            except ValueError as error:
                elapsed_ms = int((time.monotonic() - started) * 1000)
                self._log_usage_event(
                    event="gemini_request_error",
                    modality=modality,
                    media_bytes=media_bytes,
                    attempt=attempt,
                    elapsed_ms=elapsed_ms,
                    log_context=log_context,
                    http_status=response.status_code,
                    error=f"Non-JSON Gemini response: {response.text[:500]}",
                )
                last_error = GeminiError(
                    f"Non-JSON Gemini response status={response.status_code}: {response.text[:500]}"
                )
                if attempt < total_attempts and self._is_retryable_status(response.status_code):
                    self._sleep_before_retry(attempt=attempt)
                    continue
                raise last_error from error

            if response.status_code >= 400:
                elapsed_ms = int((time.monotonic() - started) * 1000)
                message = data.get("error", {}).get("message") or str(data)
                self._log_usage_event(
                    event="gemini_request_error",
                    modality=modality,
                    media_bytes=media_bytes,
                    attempt=attempt,
                    elapsed_ms=elapsed_ms,
                    log_context=log_context,
                    http_status=response.status_code,
                    error=message,
                )
                last_error = GeminiError(f"Gemini HTTP {response.status_code}: {message}")
                if attempt < total_attempts and self._is_retryable_status(response.status_code):
                    self._sleep_before_retry(attempt=attempt)
                    continue
                raise last_error

            text = self._extract_text(data)
            if text.strip():
                elapsed_ms = int((time.monotonic() - started) * 1000)
                self._record_success_usage(
                    payload=data,
                    modality=modality,
                    media_bytes=media_bytes,
                    attempt=attempt,
                    elapsed_ms=elapsed_ms,
                    response_chars=len(text),
                    log_context=log_context,
                )
                return text

            feedback = data.get("promptFeedback") or data.get("prompt_feedback")
            elapsed_ms = int((time.monotonic() - started) * 1000)
            self._log_usage_event(
                event="gemini_request_error",
                modality=modality,
                media_bytes=media_bytes,
                attempt=attempt,
                elapsed_ms=elapsed_ms,
                log_context=log_context,
                http_status=response.status_code,
                error=f"Gemini returned empty text. Feedback={feedback}",
            )
            last_error = GeminiError(f"Gemini returned empty text. Feedback={feedback}")
            if attempt < total_attempts and self._is_retryable_empty_response(feedback):
                self._sleep_before_retry(attempt=attempt)
                continue
            raise last_error

        if last_error is not None:
            raise last_error
        raise GeminiError("Gemini request failed with unknown error")

    @staticmethod
    def _extract_text(payload: dict[str, Any]) -> str:
        candidates = payload.get("candidates", [])
        chunks: list[str] = []
        for candidate in candidates:
            content = candidate.get("content", {})
            for part in content.get("parts", []):
                text = part.get("text")
                if isinstance(text, str):
                    chunks.append(text)
        return "\n".join(chunk for chunk in chunks if chunk)

    def usage_summary(self) -> dict[str, int | float]:
        summary = dict(self._usage_summary)
        summary["estimated_cost_usd"] = round(float(summary["estimated_cost_usd"]), 8)
        return summary

    def _record_success_usage(
        self,
        payload: dict[str, Any],
        modality: str,
        media_bytes: int,
        attempt: int,
        elapsed_ms: int,
        response_chars: int,
        log_context: dict[str, Any] | None,
    ) -> None:
        usage = payload.get("usageMetadata") or payload.get("usage_metadata") or {}
        input_tokens = self._usage_int(usage, "promptTokenCount", "prompt_token_count")
        candidate_output_tokens = self._usage_int(usage, "candidatesTokenCount", "candidates_token_count")
        total_tokens = self._usage_int(usage, "totalTokenCount", "total_token_count")
        thoughts_tokens = self._usage_int(usage, "thoughtsTokenCount", "thoughts_token_count")
        cached_tokens = self._usage_int(usage, "cachedContentTokenCount", "cached_content_token_count")
        output_tokens = candidate_output_tokens + thoughts_tokens
        if total_tokens == 0:
            total_tokens = input_tokens + output_tokens

        input_cost = self._estimate_cost(input_tokens, self.input_cost_usd_per_1m_tokens)
        output_cost = self._estimate_cost(output_tokens, self.output_cost_usd_per_1m_tokens)
        total_cost = input_cost + output_cost

        self._usage_summary["model_calls"] = int(self._usage_summary["model_calls"]) + 1
        self._usage_summary["input_tokens"] = int(self._usage_summary["input_tokens"]) + input_tokens
        self._usage_summary["output_tokens"] = int(self._usage_summary["output_tokens"]) + output_tokens
        self._usage_summary["total_tokens"] = int(self._usage_summary["total_tokens"]) + total_tokens
        self._usage_summary["estimated_cost_usd"] = float(self._usage_summary["estimated_cost_usd"]) + total_cost

        self._log_usage_event(
            event="gemini_request",
            modality=modality,
            media_bytes=media_bytes,
            attempt=attempt,
            elapsed_ms=elapsed_ms,
            log_context=log_context,
            input_tokens=input_tokens,
            candidate_output_tokens=candidate_output_tokens,
            output_tokens=output_tokens,
            total_tokens=total_tokens,
            thoughts_tokens=thoughts_tokens,
            cached_tokens=cached_tokens,
            input_cost_usd=round(input_cost, 8),
            output_cost_usd=round(output_cost, 8),
            estimated_cost_usd=round(total_cost, 8),
            input_cost_usd_per_1m_tokens=self.input_cost_usd_per_1m_tokens,
            output_cost_usd_per_1m_tokens=self.output_cost_usd_per_1m_tokens,
            response_chars=response_chars,
        )

    def _log_usage_event(
        self,
        event: str,
        modality: str,
        media_bytes: int,
        attempt: int,
        elapsed_ms: int,
        log_context: dict[str, Any] | None,
        **fields: Any,
    ) -> None:
        if self.usage_log_path is None:
            return
        payload: dict[str, Any] = {
            "ts_utc": utc_now_iso(),
            "event": event,
            "model": self.model,
            "modality": modality,
            "media_bytes": media_bytes,
            "attempt": attempt,
            "elapsed_ms": elapsed_ms,
            **(log_context or {}),
            **fields,
        }
        append_jsonl(self.usage_log_path, payload)

    @staticmethod
    def _usage_int(usage: dict[str, Any], *keys: str) -> int:
        for key in keys:
            value = usage.get(key)
            if isinstance(value, int):
                return value
            if isinstance(value, float):
                return int(value)
        return 0

    @staticmethod
    def _estimate_cost(tokens: int, usd_per_1m_tokens: float) -> float:
        return (tokens / 1_000_000.0) * usd_per_1m_tokens

    @staticmethod
    def _is_retryable_status(status_code: int) -> bool:
        return status_code in {408, 429, 500, 502, 503, 504}

    @staticmethod
    def _is_retryable_empty_response(feedback: Any) -> bool:
        if not isinstance(feedback, dict):
            return True
        block_reason = feedback.get("blockReason") or feedback.get("block_reason")
        return block_reason is None

    def _sleep_before_retry(self, attempt: int) -> None:
        if self.retry_backoff_seconds <= 0:
            return
        time.sleep(self.retry_backoff_seconds * attempt)
