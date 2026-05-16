"""Health & meta endpoints."""
from __future__ import annotations

from flask import Blueprint, jsonify

from config import settings

bp = Blueprint("health", __name__)


@bp.get("/health")
def health():
    return jsonify(
        {
            "status": "ok",
            "model": settings.claude_model,
            "embedding_model": settings.embedding_model,
        }
    )
