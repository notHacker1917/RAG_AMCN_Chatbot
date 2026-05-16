"""POST /query — main RAG endpoint."""
from __future__ import annotations

from flask import Blueprint, jsonify, request

from rag_pipeline import RAGPipeline
from utils.logger import get_logger
from utils.validators import ValidationError, ensure_int, ensure_str, require

logger = get_logger(__name__)

bp = Blueprint("query", __name__)
_rag = RAGPipeline()


@bp.post("")
def query():
    data = request.get_json(silent=True) or {}
    require(data, "query")

    q = ensure_str(data["query"], "query", max_len=4000)
    top_k = ensure_int(data.get("top_k", 5), "top_k", lo=1, hi=25)
    use_mpc = bool(data.get("use_mpc", False))
    history = data.get("history", [])
    if history and not isinstance(history, list):
        raise ValidationError("'history' must be a list of {role, content} dicts")

    if use_mpc:
        from mpc_module import secure_query

        logger.info("Running query through MPC simulation.")
        result = secure_query(q, top_k=top_k)
    else:
        result = _rag.generate_response_with_claude(
            q, top_k=top_k, chat_history=history
        )

    return jsonify(result)
