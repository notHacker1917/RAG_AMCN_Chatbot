"""
FAISS-backed vector store with on-disk persistence.

The index is `IndexFlatIP` (inner product) which equals cosine
similarity given L2-normalised vectors. Metadata is persisted next to
the index in a pickle file.

This is intentionally simple and easy to swap for an HNSW / IVF index
once the corpus grows.
"""
from __future__ import annotations

import os
import pickle
import threading
from dataclasses import dataclass, field
from typing import Any, Dict, List, Tuple

import numpy as np

from config import settings
from utils.logger import get_logger

logger = get_logger(__name__)


@dataclass
class _Record:
    note_id: int
    chunk_index: int
    content: str
    metadata: Dict[str, Any] = field(default_factory=dict)


class VectorStore:
    """Persistent FAISS vector store."""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._index = None
        self._records: List[_Record] = []
        self._dim = settings.embedding_dim
        self._index_path = str(settings.resolve(settings.faiss_index_path))
        self._meta_path = str(settings.resolve(settings.faiss_meta_path))
        os.makedirs(os.path.dirname(self._index_path), exist_ok=True)
        self._load_if_exists()

    # ----------------- persistence -----------------
    def _load_if_exists(self) -> None:
        if not (os.path.exists(self._index_path) and os.path.exists(self._meta_path)):
            logger.info("No existing FAISS index found — will start empty.")
            return
        try:
            import faiss  # type: ignore

            self._index = faiss.read_index(self._index_path)
            with open(self._meta_path, "rb") as f:
                self._records = pickle.load(f)
            logger.info(
                f"Loaded FAISS index ({self._index.ntotal} vectors) from disk."
            )
        except Exception as e:  # pragma: no cover
            logger.warning(f"Could not load FAISS index: {e}. Starting fresh.")
            self._index = None
            self._records = []

    def save(self) -> None:
        if self._index is None:
            return
        import faiss  # type: ignore

        with self._lock:
            faiss.write_index(self._index, self._index_path)
            with open(self._meta_path, "wb") as f:
                pickle.dump(self._records, f)
        logger.info(f"Saved FAISS index ({self._index.ntotal} vectors).")

    # ----------------- index ops -----------------
    def _ensure_index(self) -> None:
        if self._index is not None:
            return
        import faiss  # type: ignore

        logger.info(f"Creating FAISS IndexFlatIP (dim={self._dim})")
        self._index = faiss.IndexFlatIP(self._dim)

    def add(
        self,
        vectors: np.ndarray,
        records: List[Dict[str, Any]],
    ) -> List[int]:
        """Add vectors + records. Returns assigned FAISS positions."""
        if vectors.ndim != 2 or vectors.shape[1] != self._dim:
            raise ValueError(
                f"Expected (n, {self._dim}); got {vectors.shape}"
            )
        if len(records) != vectors.shape[0]:
            raise ValueError("vectors and records length mismatch")

        with self._lock:
            self._ensure_index()
            start = self._index.ntotal  # type: ignore[union-attr]
            self._index.add(vectors)    # type: ignore[union-attr]
            for r in records:
                self._records.append(
                    _Record(
                        note_id=int(r["note_id"]),
                        chunk_index=int(r.get("chunk_index", 0)),
                        content=r["content"],
                        metadata=r.get("metadata", {}),
                    )
                )
            return list(range(start, start + vectors.shape[0]))

    def search(
        self, query_vec: np.ndarray, k: int = 5
    ) -> List[Tuple[float, _Record]]:
        """Return list of (score, record) ordered best-first."""
        if self._index is None or self._index.ntotal == 0:
            return []
        if query_vec.ndim == 1:
            query_vec = query_vec.reshape(1, -1)
        scores, idxs = self._index.search(query_vec, k)
        out: list[tuple[float, _Record]] = []
        for score, idx in zip(scores[0].tolist(), idxs[0].tolist()):
            if idx < 0 or idx >= len(self._records):
                continue
            out.append((float(score), self._records[idx]))
        return out

    @property
    def size(self) -> int:
        return self._index.ntotal if self._index is not None else 0

    def reset(self) -> None:
        with self._lock:
            self._index = None
            self._records = []
            for p in (self._index_path, self._meta_path):
                if os.path.exists(p):
                    os.remove(p)
