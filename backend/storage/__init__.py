"""
Object storage package supporting MinIO and local filesystem fallback.
"""

from .minio import MinioStorageService, storage_service

__all__ = ["MinioStorageService", "storage_service"]

