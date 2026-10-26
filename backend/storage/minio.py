"""
MinIO Object Storage Service for Enterprise Document Management.

Provides S3-compatible document storage, presigned URLs for client viewing,
and automated fallback to local disk when MinIO is not running.
"""

from __future__ import annotations

import io
import logging
from pathlib import Path
from typing import BinaryIO, Optional, Union

import urllib3
from minio import Minio

from backend.config import settings

logger = logging.getLogger("docuchat.storage")


class MinioStorageService:
    """Production MinIO object storage service with resilience fallback."""

    def __init__(
        self,
        endpoint: Optional[str] = None,
        access_key: Optional[str] = None,
        secret_key: Optional[str] = None,
        bucket: Optional[str] = None,
        secure: Optional[bool] = None,
    ):
        self.endpoint = endpoint or settings.MINIO_ENDPOINT
        self.access_key = access_key or settings.MINIO_ACCESS_KEY
        self.secret_key = secret_key or settings.MINIO_SECRET_KEY
        self.bucket = bucket or settings.MINIO_BUCKET
        self.secure = secure if secure is not None else settings.MINIO_SECURE

        self._client: Optional[Minio] = None
        self._minio_available: Optional[bool] = None
        self.local_fallback_dir = Path(settings.UPLOAD_DIR) / "minio_fallback"
        self.local_fallback_dir.mkdir(parents=True, exist_ok=True)

    def _get_client(self) -> Optional[Minio]:
        """Lazy-initialize Minio client and test connection."""
        if settings.STORAGE_BACKEND == "local":
            self._minio_available = False
            return None

        if self._client is not None:
            return self._client if self._minio_available else None

        try:
            http_client = urllib3.PoolManager(
                timeout=urllib3.Timeout(connect=0.5, read=1.0),
                retries=urllib3.Retry(total=1, backoff_factor=0.1),
            )
            client = Minio(
                endpoint=self.endpoint,
                access_key=self.access_key,
                secret_key=self.secret_key,
                secure=self.secure,
                http_client=http_client,
            )
            # Check bucket / connection
            if not client.bucket_exists(self.bucket):
                client.make_bucket(self.bucket)
                logger.info("Created MinIO bucket '%s'", self.bucket)
            self._client = client
            self._minio_available = True
            return self._client
        except Exception as exc:
            logger.info("MinIO unavailable at %s (%s). Falling back to local storage.", self.endpoint, exc)
            self._minio_available = False
            return None

    def is_healthy(self) -> bool:
        """Check if MinIO is actively accessible."""
        try:
            client = self._get_client()
            if client is None:
                return False
            return client.bucket_exists(self.bucket)
        except Exception:
            return False

    def upload(
        self,
        object_name: str,
        data: Union[bytes, BinaryIO, str, Path],
        content_type: str = "application/octet-stream",
    ) -> str:
        """
        Upload file or bytes to MinIO (or fallback storage).
        Returns object identifier / URI.
        """
        object_name = object_name.lstrip("/")

        # Convert data to byte buffer if needed
        if isinstance(data, (str, Path)):
            p = Path(data)
            raw_bytes = p.read_bytes()
            length = len(raw_bytes)
            stream = io.BytesIO(raw_bytes)
        elif isinstance(data, bytes):
            length = len(data)
            stream = io.BytesIO(data)
        elif hasattr(data, "read"):
            content = data.read()
            length = len(content)
            stream = io.BytesIO(content)
        else:
            raise ValueError("Unsupported data type for MinIO upload.")

        client = self._get_client()
        if client is not None:
            try:
                client.put_object(
                    bucket_name=self.bucket,
                    object_name=object_name,
                    data=stream,
                    length=length,
                    content_type=content_type,
                )
                logger.info("Uploaded '%s' to MinIO bucket '%s' (%d bytes)", object_name, self.bucket, length)
                return f"minio://{self.bucket}/{object_name}"
            except Exception as exc:
                logger.warning("MinIO upload failed (%s). Saving to local fallback.", exc)

        # Local fallback
        dest = self.local_fallback_dir / object_name
        dest.parent.mkdir(parents=True, exist_ok=True)
        stream.seek(0)
        dest.write_bytes(stream.read())
        return f"file://{dest}"

    def download_to_file(self, object_name: str, dest_path: Union[str, Path]) -> Path:
        """Download an object to a local file path."""
        object_name = object_name.lstrip("/")
        dest = Path(dest_path)
        dest.parent.mkdir(parents=True, exist_ok=True)

        client = self._get_client()
        if client is not None:
            try:
                client.fget_object(self.bucket, object_name, str(dest))
                return dest
            except Exception as exc:
                logger.warning("MinIO fget_object failed (%s). Checking local fallback.", exc)

        # Check local fallback
        src = self.local_fallback_dir / object_name
        if src.exists():
            dest.write_bytes(src.read_bytes())
            return dest

        raise FileNotFoundError(f"Object '{object_name}' not found in MinIO or local storage.")

    def get_bytes(self, object_name: str) -> bytes:
        """Read full object bytes directly into memory."""
        object_name = object_name.lstrip("/")
        client = self._get_client()
        if client is not None:
            try:
                response = client.get_object(self.bucket, object_name)
                try:
                    return response.read()
                finally:
                    response.close()
                    response.release_conn()
            except Exception as exc:
                logger.warning("MinIO get_object failed (%s). Checking local fallback.", exc)

        src = self.local_fallback_dir / object_name
        if src.exists():
            return src.read_bytes()

        raise FileNotFoundError(f"Object '{object_name}' not found.")

    def get_presigned_url(self, object_name: str, expires_seconds: int = 3600) -> str:
        """Generate a presigned GET URL for secure client downloads."""
        object_name = object_name.lstrip("/")
        client = self._get_client()
        if client is not None:
            try:
                import datetime
                return client.get_presigned_url(
                    method="GET",
                    bucket_name=self.bucket,
                    object_name=object_name,
                    expires=datetime.timedelta(seconds=expires_seconds),
                )
            except Exception as exc:
                logger.warning("Failed to generate MinIO presigned URL: %s", exc)

        # Fallback local URL or path
        return f"/api/documents/download/{object_name}"

    def delete(self, object_name: str) -> bool:
        """Delete an object from MinIO and local fallback."""
        object_name = object_name.lstrip("/")
        deleted = False

        client = self._get_client()
        if client is not None:
            try:
                client.remove_object(self.bucket, object_name)
                deleted = True
            except Exception as exc:
                logger.warning("Failed to remove MinIO object %s: %s", object_name, exc)

        local_file = self.local_fallback_dir / object_name
        if local_file.exists():
            local_file.unlink(missing_ok=True)
            deleted = True

        return deleted


# Global instance
storage_service = MinioStorageService()
