"""
Top-level `secure_query()` entrypoint used by the Flask API when the
client sets `"use_mpc": true`.

Workflow
--------
1. Load the in-process FAISS records (simulated "owned" data).
2. Distribute them across `MPC_NUM_PARTIES` simulated parties.
3. Embed the query, then run the secure inner-product protocol.
4. Look up the top-k notes from the database and ask Claude to
   answer using the privacy-preserving retrieval results.
"""
from __future__ import annotations

from typing import List

import numpy as np

from config import settings
from database.repository import get_notes_by_ids
from database.session import get_session
from rag_pipeline.claude_client import ClaudeClient
from rag_pipeline.embeddings import EmbeddingModel
from rag_pipeline.response_generator import build_rag_prompt
from rag_pipeline.vector_store import VectorStore
from utils.logger import get_logger

from .parties import MPCOrchestrator

logger = get_logger(__name__)


def _load_corpus_from_faiss() -> tuple[np.ndarray, List[int], dict[int, str]]:
    """
    Read the FAISS-side records straight out of the vector store. We
    extract the (already-normalised) vectors by re-embedding their
    stored text — a real privacy-preserving system would never let
    the orchestrator do this, but it's adequate for the simulation.
    """
    store = VectorStore()
    if store.size == 0:
        return np.zeros((0, settings.embedding_dim), dtype=np.float32), [], {}

    embedder = EmbeddingModel()
    texts: list[str] = []
    note_ids: list[int] = []
    note_text: dict[int, str] = {}
    # Access the private records list — acceptable inside the package.
    for rec in store._records:  # type: ignore[attr-defined]
        texts.append(rec.content)
        note_ids.append(rec.note_id)
        # collapse multiple chunks per note id by keeping the longest
        if rec.note_id not in note_text or len(rec.content) > len(note_text[rec.note_id]):
            note_text[rec.note_id] = rec.content
    vectors = embedder.embed(texts)
    return vectors, note_ids, note_text


def secure_query(query: str, top_k: int = 5) -> dict:
    """
    Run an MPC-style query and generate a Claude answer using the
    privacy-preserving retrieval result.
    """
    embedder = EmbeddingModel()
    qv = embedder.embed_query(query).flatten()

    corpus, note_ids, _ = _load_corpus_from_faiss()
    if corpus.shape[0] == 0:
        return {
            "answer": "No notes have been indexed yet — upload some first.",
            "sources": [],
            "retrieval_count": 0,
            "mpc": {"parties": settings.mpc_num_parties, "note_count": 0},
        }

    orchestrator = MPCOrchestrator()
    orchestrator.distribute_notes(corpus, note_ids)
    ranked = orchestrator.top_k(qv, k=top_k)

    # Build context from DB
    with get_session() as s:
        notes = {n.id: n for n in get_notes_by_ids(s, [nid for nid, _ in ranked])}

    context_parts: list[str] = []
    sources: list[dict] = []
    for i, (nid, score) in enumerate(ranked, start=1):
        note = notes.get(nid)
        if not note:
            continue
        label = f"[Source {i} | note_id={nid} | score={score:.3f}]"
        context_parts.append(f"{label}\n{note.content}")
        sources.append(
            {
                "note_id": nid,
                "score": float(score),
                "excerpt": note.content[:300],
                "metadata": {"title": note.title, "via": "mpc"},
            }
        )

    system, user = build_rag_prompt(query=query, context="\n\n---\n\n".join(context_parts))
    try:
        answer = ClaudeClient().complete(system=system, user=user)
    except Exception as e:
        logger.error(f"Claude call failed inside MPC pipeline: {e}")
        answer = (
            "Privacy-preserving retrieval succeeded but generation failed. "
            f"Underlying error: {e}"
        )

    return {
        "answer": answer,
        "sources": sources,
        "retrieval_count": len(sources),
        "mpc": {
            "parties": settings.mpc_num_parties,
            "note_count": int(corpus.shape[0]),
            "protocol": "additive-shared inner product (educational)",
        },
    }
