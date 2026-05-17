"""
Token-aware overlapping chunker.

Uses `tiktoken` when available so chunk sizes are measured in real
tokens; otherwise falls back to a word-based approximation. Splits
prefer paragraph and sentence boundaries to keep chunks coherent.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List

_PARA_RE = re.compile(r"\n{2,}")
_SENT_RE = re.compile(r"(?<=[.!?])\s+")


def _token_counter() -> Callable[[str], int]:
    """Return a callable that counts tokens — tiktoken if installed."""
    try:
        import tiktoken  # type: ignore

        enc = tiktoken.get_encoding("cl100k_base")
        return lambda text: len(enc.encode(text))
    except Exception:  # pragma: no cover
        return lambda text: max(1, len(text.split()))


_count_tokens = _token_counter()


@dataclass
class Chunk:
    """A chunk passed downstream to the embedding step."""

    text: str
    index: int
    metadata: Dict[str, Any] = field(default_factory=dict)
    token_count: int = 0


def split_into_units(text: str) -> List[str]:
    """Split text into paragraphs, then sentences for fine-grained units."""
    units: list[str] = []
    for para in _PARA_RE.split(text):
        para = para.strip()
        if not para:
            continue
        sents = [s.strip() for s in _SENT_RE.split(para) if s.strip()]
        units.extend(sents if sents else [para])
    return units


def chunk_text(
    text: str,
    *,
    chunk_size: int = 800,
    chunk_overlap: int = 120,
    base_metadata: Dict[str, Any] | None = None,
) -> List[Chunk]:
    """
    Pack sentence/paragraph units into chunks of `chunk_size` tokens
    with `chunk_overlap` overlap. Returns ordered list.
    """
    if chunk_overlap >= chunk_size:
        raise ValueError("chunk_overlap must be smaller than chunk_size")

    units = split_into_units(text)
    if not units:
        return []

    base = dict(base_metadata or {})
    chunks: list[Chunk] = []
    buffer: list[str] = []
    buf_tokens = 0
    idx = 0

    def emit() -> None:
        nonlocal idx, buffer, buf_tokens
        if not buffer:
            return
        body = " ".join(buffer).strip()
        chunks.append(
            Chunk(
                text=body,
                index=idx,
                metadata={**base, "chunk_index": idx},
                token_count=buf_tokens,
            )
        )
        idx += 1
        # overlap — keep tail tokens
        if chunk_overlap <= 0:
            buffer = []
            buf_tokens = 0
            return
        tail: list[str] = []
        tail_tokens = 0
        for unit in reversed(buffer):
            tail.insert(0, unit)
            tail_tokens += _count_tokens(unit)
            if tail_tokens >= chunk_overlap:
                break
        buffer = tail
        buf_tokens = tail_tokens

    for unit in units:
        utok = _count_tokens(unit)
        # Edge case: a single unit larger than chunk_size — hard split
        if utok > chunk_size:
            emit()
            words = unit.split()
            step = max(1, chunk_size // max(1, _count_tokens(" ".join(words[:50])) // 50 or 1))
            for i in range(0, len(words), step):
                piece = " ".join(words[i : i + step])
                chunks.append(
                    Chunk(
                        text=piece,
                        index=idx,
                        metadata={**base, "chunk_index": idx},
                        token_count=_count_tokens(piece),
                    )
                )
                idx += 1
            continue

        if buf_tokens + utok > chunk_size and buffer:
            emit()
        buffer.append(unit)
        buf_tokens += utok

    emit()
    return chunks
