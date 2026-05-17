"""
End-to-end RAG pipeline:

    Note rows ──► chunker ──► embedder ──► FAISS vector store
                                                         │
    user query ──► embedder ──► similarity_search ──► retrieve_context
                                                         │
                                                         ▼
                                   generate_response_with_claude()
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable, List, Optional, Sequence

import numpy as np

from config import settings
from database.models import Note
from database.repository import update_note_embedding_id
from database.session import get_session
from utils.logger import get_logger

from .chunker import Chunk, chunk_text
from .embeddings import EmbeddingModel
from .vector_store import VectorStore, _Record

logger = get_logger(__name__)


@dataclass
class RetrievedChunk:
    note_id: int
    score: float
    content: str
    metadata: dict


class RAGPipeline:
    """High-level orchestrator for indexing and querying."""

    def __init__(
        self,
        embedder: Optional[EmbeddingModel] = None,
        store: Optional[VectorStore] = None,
    ) -> None:
        self.embedder = embedder or EmbeddingModel()
        self.store = store or VectorStore()

    # ============ INDEXING ============
    def build_vector_index(
        self,
        notes: Iterable[Note],
        *,
        chunk_size: int | None = None,
        chunk_overlap: int | None = None,
        persist: bool = True,
    ) -> int:
        """
        Chunk + embed + index a batch of notes. Returns # chunks added.
        """
        chunk_size = chunk_size or settings.chunk_size
        chunk_overlap = chunk_overlap or settings.chunk_overlap

        all_chunks: list[Chunk] = []
        note_id_per_chunk: list[int] = []
        for note in notes:
            cs = chunk_text(
                note.content,
                chunk_size=chunk_size,
                chunk_overlap=chunk_overlap,
                base_metadata={
                    "note_id": note.id,
                    "subtopic_id": note.subtopic_id,
                    "source_id": note.source_id,
                    "title": note.title or "",
                },
            )
            for c in cs:
                all_chunks.append(c)
                note_id_per_chunk.append(note.id)

        if not all_chunks:
            logger.info("No chunks produced — nothing to index.")
            return 0

        logger.info(f"Embedding {len(all_chunks)} chunks…")
        vectors = self.embedder.embed([c.text for c in all_chunks])
        records = [
            {
                "note_id": note_id_per_chunk[i],
                "chunk_index": c.index,
                "content": c.text,
                "metadata": c.metadata,
            }
            for i, c in enumerate(all_chunks)
        ]
        positions = self.store.add(vectors, records)

        # Persist an embedding-id reference back to the note row
        # (first chunk position is enough to indicate "indexed").
        seen: set[int] = set()
        with get_session() as s:
            for i, nid in enumerate(note_id_per_chunk):
                if nid in seen:
                    continue
                seen.add(nid)
                update_note_embedding_id(s, nid, f"faiss:{positions[i]}")

        if persist:
            self.store.save()
        logger.info(f"Indexed {len(all_chunks)} chunks ({self.store.size} total).")
        return len(all_chunks)

    # ============ RETRIEVAL ============
    def similarity_search(
        self,
        query: str,
        top_k: int | None = None,
    ) -> List[RetrievedChunk]:
        """Semantic search; returns ordered RetrievedChunk objects."""
        top_k = top_k or settings.top_k
        qv = self.embedder.embed_query(query)
        hits = self.store.search(qv, k=top_k)
        return [
            RetrievedChunk(
                note_id=rec.note_id,
                score=score,
                content=rec.content,
                metadata=rec.metadata,
            )
            for score, rec in hits
        ]

    def retrieve_context(
        self,
        query: str,
        top_k: int | None = None,
        max_chars: int = 6000,
    ) -> tuple[str, List[RetrievedChunk]]:
        """
        Return a (prompt-ready context block, [chunks]) tuple.
        Trims combined context to `max_chars` while preserving order.
        """
        chunks = self.similarity_search(query, top_k=top_k)
        pieces: list[str] = []
        used = 0
        for i, c in enumerate(chunks, start=1):
            label = f"[Source {i} | note_id={c.note_id} | score={c.score:.3f}]"
            block = f"{label}\n{c.content}"
            if used + len(block) > max_chars:
                break
            pieces.append(block)
            used += len(block)
        return "\n\n---\n\n".join(pieces), chunks

    # ============ GENERATION ============
    def generate_response_with_claude(
        self,
        query: str,
        *,
        top_k: int | None = None,
        chat_history: Sequence[dict] | None = None,
    ) -> dict:
        """
        Full RAG turn: retrieve → prompt Claude → return answer + sources.
        Returns a dict with keys: answer, sources, retrieval_count.
        """
        # Local import keeps RAG import-light when Claude isn't used.
        from rag_pipeline.claude_client import ClaudeClient
        from rag_pipeline.response_generator import build_rag_prompt

        context_block, retrieved = self.retrieve_context(query, top_k=top_k)
        system_prompt, user_prompt = build_rag_prompt(
            query=query, context=context_block
        )

        client = ClaudeClient()
        answer = client.complete(
            system=system_prompt,
            user=user_prompt,
            history=chat_history or [],
        )

        return {
            "answer": answer,
            "sources": [
                {
                    "note_id": c.note_id,
                    "score": c.score,
                    "excerpt": c.content[:300],
                    "metadata": c.metadata,
                }
                for c in retrieved
            ],
            "retrieval_count": len(retrieved),
        }
