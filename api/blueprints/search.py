"""GET /search?q=... — plain text + semantic search."""
from __future__ import annotations

from flask import Blueprint, jsonify, request

from database.repository import search_notes
from database.session import get_session
from rag_pipeline import RAGPipeline
from utils.validators import ensure_int, ensure_str

bp = Blueprint("search", __name__)
_rag = RAGPipeline()


@bp.get("")
def search():
    q = ensure_str(request.args.get("q", ""), "q", max_len=500)
    if not q.strip():
        return jsonify({"query": q, "results": []})

    mode = (request.args.get("mode") or "semantic").lower()
    limit = ensure_int(request.args.get("limit", 10), "limit", lo=1, hi=100)

    if mode == "text":
        with get_session() as s:
            rows = search_notes(s, q, limit=limit)
            return jsonify(
                {
                    "query": q,
                    "mode": "text",
                    "results": [r.to_dict() for r in rows],
                }
            )

    # default: semantic
    chunks = _rag.similarity_search(q, top_k=limit)
    return jsonify(
        {
            "query": q,
            "mode": "semantic",
            "results": [
                {
                    "note_id": c.note_id,
                    "score": c.score,
                    "excerpt": c.content,
                    "metadata": c.metadata,
                }
                for c in chunks
            ],
        }
    )
