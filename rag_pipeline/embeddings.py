"""
Embedding model wrapper.

Lazily loads `sentence-transformers` (default: BAAI/bge-large-en-v1.5)
and exposes `embed(texts)` returning a `numpy.ndarray` of shape
(n, dim). Embeddings are L2-normalised so cosine similarity can be
computed via FAISS inner-product.
"""
from __future__ import annotations

import threading
from typing import Iterable, List

import numpy as np

from config import settings
from utils.logger import get_logger

logger = get_logger(__name__)


class EmbeddingModel:
    """Singleton-style wrapper around SentenceTransformer."""

    _lock = threading.Lock()
    _instance: "EmbeddingModel | None" = None

    def __new__(cls) -> "EmbeddingModel":
        with cls._lock:
            if cls._instance is None:
                cls._instance = super().__new__(cls)
                cls._instance._model = None  # type: ignore[attr-defined]
            return cls._instance

    # Lazy load — avoids slow import at module-load time.
    def _ensure_model(self) -> None:
        if self._model is not None:  # type: ignore[attr-defined]
            return
        with self._lock:
            if self._model is not None:  # type: ignore[attr-defined]
                return
            from sentence_transformers import SentenceTransformer  # type: ignore

            logger.info(
                f"Loading embedding model '{settings.embedding_model}' "
                f"(dim={settings.embedding_dim})…"
            )
            self._model = SentenceTransformer(settings.embedding_model)  # type: ignore[attr-defined]

    @property
    def dim(self) -> int:
        return int(settings.embedding_dim)

    def embed(self, texts: Iterable[str]) -> np.ndarray:
        """Return an (n, dim) float32 array of L2-normalised embeddings."""
        self._ensure_model()
        texts = [t if t else " " for t in texts]
        # BGE recommends a query prefix for queries — we standardise on
        # passage-style embeddings here and apply the query prefix in
        # `embed_query`.
        vectors = self._model.encode(  # type: ignore[attr-defined]
            texts,
            batch_size=32,
            show_progress_bar=False,
            convert_to_numpy=True,
            normalize_embeddings=True,
        )
        return vectors.astype(np.float32)

    def embed_query(self, query: str) -> np.ndarray:
        """Embed a single query string (1, dim)."""
        prefix = ""
        if "bge" in settings.embedding_model.lower():
            prefix = "Represent this sentence for searching relevant passages: "
        return self.embed([prefix + query])
