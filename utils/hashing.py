"""Hashing helpers — used for de-duplication and file integrity checks."""
from __future__ import annotations

import hashlib
from pathlib import Path


def sha256_bytes(data: bytes) -> str:
    """Return hex SHA-256 of bytes."""
    return hashlib.sha256(data).hexdigest()


def sha256_file(path: str | Path, chunk: int = 1 << 16) -> str:
    """Return hex SHA-256 of a file read in chunks."""
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for block in iter(lambda: f.read(chunk), b""):
            h.update(block)
    return h.hexdigest()


def sha256_text(text: str) -> str:
    """Return hex SHA-256 of a string (utf-8)."""
    return sha256_bytes(text.encode("utf-8"))
