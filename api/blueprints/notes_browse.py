"""GET /subjects, /units, /topics — hierarchy browsing."""
from __future__ import annotations

from flask import Blueprint, jsonify, request

from database.repository import list_subjects, list_topics, list_units
from database.session import get_session
from utils.validators import ensure_int

bp = Blueprint("browse", __name__)


@bp.get("/subjects")
def subjects():
    with get_session() as s:
        rows = list_subjects(s)
        return jsonify(
            [
                {
                    "id": r.id,
                    "name": r.name,
                    "description": r.description,
                    "unit_count": len(r.units),
                }
                for r in rows
            ]
        )


@bp.get("/units")
def units():
    subject_id = request.args.get("subject_id")
    sid = ensure_int(subject_id, "subject_id", lo=1) if subject_id else None
    with get_session() as s:
        rows = list_units(s, subject_id=sid)
        return jsonify(
            [
                {
                    "id": r.id,
                    "subject_id": r.subject_id,
                    "name": r.name,
                    "topic_count": len(r.topics),
                }
                for r in rows
            ]
        )


@bp.get("/topics")
def topics():
    unit_id = request.args.get("unit_id")
    uid = ensure_int(unit_id, "unit_id", lo=1) if unit_id else None
    with get_session() as s:
        rows = list_topics(s, unit_id=uid)
        return jsonify(
            [
                {
                    "id": r.id,
                    "unit_id": r.unit_id,
                    "name": r.name,
                    "subtopic_count": len(r.subtopics),
                }
                for r in rows
            ]
        )
