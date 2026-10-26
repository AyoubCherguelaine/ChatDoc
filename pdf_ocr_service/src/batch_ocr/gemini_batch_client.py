from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import requests

from arabic_pdf_md_agent.base.errors import PdfOcrExternalServiceError


class GeminiBatchError(PdfOcrExternalServiceError):
    pass


class GeminiBatchClient:
    """REST client for Gemini File API and BatchGenerateContent."""

    def __init__(self, api_key: str, model: str, timeout_seconds: int = 90) -> None:
        self.api_key = api_key
        self.model = model
        self.timeout_seconds = timeout_seconds
        self.session = requests.Session()

    def upload_file(self, path: Path, *, display_name: str, mime_type: str) -> dict[str, Any]:
        data = path.read_bytes()
        start_response = self.session.post(
            "https://generativelanguage.googleapis.com/upload/v1beta/files",
            params={"key": self.api_key},
            headers={
                "X-Goog-Upload-Protocol": "resumable",
                "X-Goog-Upload-Command": "start",
                "X-Goog-Upload-Header-Content-Length": str(len(data)),
                "X-Goog-Upload-Header-Content-Type": mime_type,
                "Content-Type": "application/json",
            },
            json={"file": {"display_name": display_name}},
            timeout=self.timeout_seconds,
        )
        if start_response.status_code >= 400:
            raise GeminiBatchError(self._error_message("Gemini file upload start failed", start_response))

        upload_url = start_response.headers.get("x-goog-upload-url") or start_response.headers.get(
            "X-Goog-Upload-URL"
        )
        if not upload_url:
            raise GeminiBatchError("Gemini file upload start response did not include x-goog-upload-url")

        upload_response = self.session.post(
            upload_url,
            headers={
                "Content-Length": str(len(data)),
                "X-Goog-Upload-Offset": "0",
                "X-Goog-Upload-Command": "upload, finalize",
                "Content-Type": mime_type,
            },
            data=data,
            timeout=self.timeout_seconds,
        )
        if upload_response.status_code >= 400:
            raise GeminiBatchError(self._error_message("Gemini file upload failed", upload_response))
        return self._json(upload_response)

    def create_batch(self, batch_input_file_name: str, *, display_name: str) -> dict[str, Any]:
        endpoint = f"https://generativelanguage.googleapis.com/v1beta/models/{self.model}:batchGenerateContent"
        payload = {
            "batch": {
                "display_name": display_name,
                "input_config": {"file_name": batch_input_file_name},
            }
        }
        response = self.session.post(
            endpoint,
            params={"key": self.api_key},
            json=payload,
            timeout=self.timeout_seconds,
        )
        if response.status_code >= 400:
            raise GeminiBatchError(self._error_message("Gemini batch creation failed", response))
        return self._json(response)

    def get_batch(self, batch_name: str) -> dict[str, Any]:
        response = self.session.get(
            f"https://generativelanguage.googleapis.com/v1beta/{batch_name}",
            params={"key": self.api_key},
            timeout=self.timeout_seconds,
        )
        if response.status_code >= 400:
            raise GeminiBatchError(self._error_message("Gemini batch status failed", response))
        return self._json(response)

    def download_file(self, file_name: str) -> bytes:
        response = self.session.get(
            f"https://generativelanguage.googleapis.com/v1beta/{file_name}:download",
            params={"key": self.api_key, "alt": "media"},
            timeout=self.timeout_seconds,
        )
        if response.status_code >= 400:
            raise GeminiBatchError(self._error_message("Gemini file download failed", response))
        return response.content

    @staticmethod
    def batch_name(payload: dict[str, Any]) -> str:
        name = payload.get("name") or payload.get("batch", {}).get("name")
        if not isinstance(name, str) or not name.strip():
            raise GeminiBatchError(f"Gemini batch response did not include a batch name: {payload}")
        return name.strip()

    @staticmethod
    def batch_state(payload: dict[str, Any]) -> str:
        state = payload.get("state") or payload.get("metadata", {}).get("state")
        if isinstance(state, dict):
            state = state.get("name")
        return str(state or "JOB_STATE_UNKNOWN")

    @staticmethod
    def result_file_name(payload: dict[str, Any]) -> str | None:
        candidates = (
            payload.get("dest", {}).get("fileName"),
            payload.get("dest", {}).get("file_name"),
            payload.get("output", {}).get("fileName"),
            payload.get("output", {}).get("file_name"),
            payload.get("metadata", {}).get("dest", {}).get("fileName"),
            payload.get("metadata", {}).get("dest", {}).get("file_name"),
        )
        for candidate in candidates:
            if isinstance(candidate, str) and candidate.strip():
                return candidate.strip()
        return None

    @staticmethod
    def _json(response: requests.Response) -> dict[str, Any]:
        try:
            payload = response.json()
        except ValueError as error:
            raise GeminiBatchError(f"Gemini returned non-JSON response: {response.text[:500]}") from error
        if not isinstance(payload, dict):
            raise GeminiBatchError(f"Gemini returned non-object JSON: {payload}")
        return payload

    @staticmethod
    def _error_message(prefix: str, response: requests.Response) -> str:
        try:
            payload = response.json()
            message = payload.get("error", {}).get("message") or json.dumps(payload, ensure_ascii=False)
        except ValueError:
            message = response.text[:500]
        return f"{prefix} status={response.status_code}: {message}"
