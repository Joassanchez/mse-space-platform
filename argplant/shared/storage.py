"""Storage backend abstraction for satellite data files.

Provides a Protocol-based interface so the local filesystem can be swapped
for MinIO/S3 without changing consumer code.
"""

from pathlib import Path
from typing import Protocol


class StorageBackend(Protocol):
    """Protocol defining the storage interface for file operations."""

    async def save(self, path: str, data: bytes) -> Path:
        """Persist raw data at the given relative path. Returns the full path."""
        ...

    async def exists(self, path: str) -> bool:
        """Check whether a file exists at the given relative path."""
        ...

    def get_path(self, path: str) -> Path:
        """Return the absolute path for a relative storage path."""
        ...


class LocalStorage:
    """Filesystem-backed storage implementation."""

    def __init__(self, root: Path) -> None:
        self._root = root

    async def save(self, path: str, data: bytes) -> Path:
        full = self._root / path
        full.parent.mkdir(parents=True, exist_ok=True)
        full.write_bytes(data)
        return full

    async def exists(self, path: str) -> bool:
        return (self._root / path).exists()

    def get_path(self, path: str) -> Path:
        return self._root / path
