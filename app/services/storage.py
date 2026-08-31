"""
Storage backend abstraction.

Provides a pluggable interface for file storage so the app can run with
local disk (default) or cloud object storage (S3, GCS, Azure Blob).

Set the ``STORAGE_BACKEND`` env var to switch:
  - ``local``  (default) — writes to ``UPLOAD_DIR``
  - ``s3``     — writes to an S3 bucket (requires ``boto3``)
"""

import os
import logging
from abc import ABC, abstractmethod
from pathlib import Path

from app.config import UPLOAD_DIR

logger = logging.getLogger(__name__)


class StorageBackend(ABC):
    """Abstract interface for file storage."""

    @abstractmethod
    def save(self, file_bytes: bytes, key: str) -> str:
        """Save *file_bytes* under *key* and return the storage URL / path."""
        ...

    @abstractmethod
    def load(self, key: str) -> bytes:
        """Load and return the bytes stored at *key*."""
        ...

    @abstractmethod
    def exists(self, key: str) -> bool:
        """Return ``True`` if *key* exists in the store."""
        ...

    @abstractmethod
    def delete(self, key: str) -> None:
        """Remove the object at *key*."""
        ...


class LocalStorageBackend(StorageBackend):
    """Stores files on the local filesystem under ``UPLOAD_DIR``."""

    def __init__(self, base_dir: str | None = None):
        self._base = Path(base_dir) if base_dir else UPLOAD_DIR
        self._base.mkdir(parents=True, exist_ok=True)

    def _path(self, key: str) -> Path:
        return self._base / key

    def save(self, file_bytes: bytes, key: str) -> str:
        path = self._path(key)
        path.write_bytes(file_bytes)
        return str(path)

    def load(self, key: str) -> bytes:
        return self._path(key).read_bytes()

    def exists(self, key: str) -> bool:
        return self._path(key).exists()

    def delete(self, key: str) -> None:
        path = self._path(key)
        if path.exists():
            path.unlink()


class S3StorageBackend(StorageBackend):
    """
    Stores files in an AWS S3 bucket.

    Required env vars:
        S3_BUCKET, AWS_ACCESS_KEY_ID, AWS_SECRET_ACCESS_KEY
    Optional:
        AWS_REGION (default: us-east-1)
    """

    def __init__(self):
        try:
            import boto3  # noqa: F401
        except ImportError:
            raise NotImplementedError(
                "S3StorageBackend requires the `boto3` package. "
                "Install it with: pip install boto3"
            )

        self._bucket = os.environ["S3_BUCKET"]
        self._region = os.getenv("AWS_REGION", "us-east-1")
        self._client = boto3.client("s3", region_name=self._region)
        logger.info("S3StorageBackend initialized: bucket=%s region=%s", self._bucket, self._region)

    def save(self, file_bytes: bytes, key: str) -> str:
        self._client.put_object(Bucket=self._bucket, Key=key, Body=file_bytes)
        return f"s3://{self._bucket}/{key}"

    def load(self, key: str) -> bytes:
        response = self._client.get_object(Bucket=self._bucket, Key=key)
        return response["Body"].read()

    def exists(self, key: str) -> bool:
        try:
            self._client.head_object(Bucket=self._bucket, Key=key)
            return True
        except Exception:
            return False

    def delete(self, key: str) -> None:
        self._client.delete_object(Bucket=self._bucket, Key=key)


# ---------------------------------------------------------------------------
# Factory
# ---------------------------------------------------------------------------
_backend_instance: StorageBackend | None = None


def get_storage_backend() -> StorageBackend:
    """Return the configured storage backend (singleton)."""
    global _backend_instance
    if _backend_instance is not None:
        return _backend_instance

    backend_type = os.getenv("STORAGE_BACKEND", "local").strip().lower()

    if backend_type == "s3":
        _backend_instance = S3StorageBackend()
    else:
        _backend_instance = LocalStorageBackend()

    return _backend_instance
