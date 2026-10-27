"""S3 object storage backed by SeaweedFS, without a filesystem fallback."""
from __future__ import annotations

from pathlib import Path
from typing import BinaryIO

import boto3
from botocore.config import Config
from botocore.exceptions import BotoCoreError, ClientError

from backend.config import settings


class S3StorageService:
    """Keep objects in a dedicated S3 service and sign browser download URLs."""

    def __init__(self, endpoint: str | None = None, public_endpoint: str | None = None,
                 access_key: str | None = None, secret_key: str | None = None,
                 bucket: str | None = None):
        self.endpoint = endpoint or settings.S3_ENDPOINT_URL
        self.public_endpoint = public_endpoint or settings.S3_PUBLIC_ENDPOINT_URL
        self.bucket = bucket or settings.S3_BUCKET
        options = {
            "aws_access_key_id": access_key or settings.S3_ACCESS_KEY,
            "aws_secret_access_key": secret_key or settings.S3_SECRET_KEY,
            "region_name": settings.S3_REGION,
            "config": Config(signature_version="s3v4", s3={"addressing_style": "path"},
                             connect_timeout=3, read_timeout=30,
                             retries={"max_attempts": 2, "mode": "standard"}),
        }
        self._client = boto3.client("s3", endpoint_url=self.endpoint, **options)
        # Signing must use the browser-facing hostname, not the Docker service name.
        self._public_client = boto3.client("s3", endpoint_url=self.public_endpoint, **options)

    @staticmethod
    def _validate_name(object_name: str) -> None:
        if not object_name or object_name.startswith("/") or ".." in object_name.split("/"):
            raise ValueError("Invalid storage object name")

    def is_healthy(self) -> bool:
        try:
            self._client.head_bucket(Bucket=self.bucket)
            return True
        except (BotoCoreError, ClientError):
            return False

    def exists(self, object_name: str) -> bool:
        self._validate_name(object_name)
        try:
            self._client.head_object(Bucket=self.bucket, Key=object_name)
            return True
        except ClientError as exc:
            if exc.response["Error"]["Code"] in ("404", "NoSuchKey", "NotFound"):
                return False
            raise

    def upload(self, object_name: str, data: bytes | BinaryIO | str | Path,
               content_type: str = "application/octet-stream") -> str:
        self._validate_name(object_name)
        options = {"Bucket": self.bucket, "Key": object_name, "ContentType": content_type}
        if isinstance(data, (str, Path)):
            with Path(data).open("rb") as source:
                self._client.put_object(Body=source, **options)
        elif isinstance(data, bytes) or hasattr(data, "read"):
            self._client.put_object(Body=data, **options)
        else:
            raise ValueError("Unsupported upload data type")
        return f"s3://{self.bucket}/{object_name}"

    def download_to_file(self, object_name: str, dest_path: str | Path) -> Path:
        self._validate_name(object_name)
        dest = Path(dest_path)
        dest.parent.mkdir(parents=True, exist_ok=True)
        self._client.download_file(self.bucket, object_name, str(dest))
        return dest

    def get_bytes(self, object_name: str) -> bytes:
        self._validate_name(object_name)
        response = self._client.get_object(Bucket=self.bucket, Key=object_name)
        try:
            return response["Body"].read()
        finally:
            response["Body"].close()

    def get_presigned_url(self, object_name: str, expires_seconds: int = 3600) -> str:
        self._validate_name(object_name)
        if not 1 <= expires_seconds <= 86400:
            raise ValueError("Download expiry must be between 1 and 86400 seconds")
        return self._public_client.generate_presigned_url(
            "get_object", Params={"Bucket": self.bucket, "Key": object_name},
            ExpiresIn=expires_seconds,
        )

    def delete(self, object_name: str) -> bool:
        self._validate_name(object_name)
        self._client.delete_object(Bucket=self.bucket, Key=object_name)
        return True


storage_service = S3StorageService()
