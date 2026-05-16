"""
Upload endpoints.

POST /upload          — multipart/form-data file upload (PDF/DOCX/JSON)
POST /upload/url      — JSON {"url": "..."} for web pages
"""
from __future__ import annotations

import os
import tempfile

from flask import Blueprint, jsonify, request
from werkzeug.utils import secure_filename

from config import settings
from data_ingestion import IngestionPipeline
from database.models import ContentType, Difficulty
from database.repository import get_notes_by_ids
from database.session import get_session
from rag_pipeline import RAGPipeline
from utils.logger import get_logger
from utils.validators import ValidationError, require

logger = get_logger(__name__)

bp = Blueprint("upload", __name__)

_pipeline = IngestionPipeline()
_rag = RAGPipeline()


_ALLOWED_EXT = {".pdf", ".docx", ".json"}


def _ingest_and_index(location: str, form: dict, mimetype: str | None = None):
    require(form, "subject", "unit", "topic", "subtopic")

    difficulty_str = (form.get("difficulty") or "medium").lower()
    try:
        difficulty = Difficulty(difficulty_str)
    except ValueError:
        raise ValidationError(
            f"Invalid difficulty '{difficulty_str}'. "
            f"Use one of: {', '.join(d.value for d in Difficulty)}"
        )

    ctype_str = (form.get("content_type") or "notes").lower()
    try:
        content_type = ContentType(ctype_str)
    except ValueError:
        raise ValidationError(
            f"Invalid content_type '{ctype_str}'. "
            f"Use one of: {', '.join(c.value for c in ContentType)}"
        )

    force_ocr = str(form.get("force_ocr", "")).lower() in {"1", "true", "yes", "on"}

    tags_raw = form.get("tags") or ""
    tags = [t.strip() for t in tags_raw.split(",") if t.strip()]

    result = _pipeline.ingest(
        location,
        subject=form["subject"],
        unit=form["unit"],
        topic=form["topic"],
        subtopic=form["subtopic"],
        difficulty=difficulty,
        tags=tags,
        mimetype=mimetype,
        content_type=content_type,
        force_ocr=force_ocr,
    )

    # Index newly-created notes into FAISS
    chunks_added = 0
    if not result.duplicate and result.note_ids:
        with get_session() as s:
            notes = get_notes_by_ids(s, result.note_ids)
            chunks_added = _rag.build_vector_index(notes)

    return {
        "source_id": result.source_id,
        "title": result.title,
        "source_type": result.source_type,
        "note_count": len(result.note_ids),
        "chunks_indexed": chunks_added,
        "duplicate": result.duplicate,
    }


@bp.post("")
def upload_file():
    """Upload and process a PDF / DOCX / OneNote-JSON file."""
    if "file" not in request.files:
        raise ValidationError("Missing 'file' in multipart form")

    file = request.files["file"]
    if not file or not file.filename:
        raise ValidationError("Empty filename")

    filename = secure_filename(file.filename)
    ext = os.path.splitext(filename)[1].lower()
    if ext not in _ALLOWED_EXT:
        raise ValidationError(
            f"Unsupported file type '{ext}'. Allowed: {sorted(_ALLOWED_EXT)}"
        )

    # Save to a temp file first, then ingestion pipeline copies to raw_files
    raw_dir = settings.resolve(settings.raw_files_dir)
    raw_dir.mkdir(parents=True, exist_ok=True)
    target = raw_dir / filename
    file.save(target)

    payload = _ingest_and_index(str(target), request.form.to_dict(), file.mimetype)
    return jsonify(payload), 201


@bp.post("/url")
def upload_url():
    """Ingest a webpage by URL."""
    data = request.get_json(silent=True) or {}
    require(data, "url", "subject", "unit", "topic", "subtopic")
    payload = _ingest_and_index(data["url"], data)
    return jsonify(payload), 201
