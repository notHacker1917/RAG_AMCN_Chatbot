"""Centralised Flask error handlers."""
from __future__ import annotations

from flask import Flask, jsonify
from werkzeug.exceptions import HTTPException

from utils.logger import get_logger
from utils.validators import ValidationError

logger = get_logger(__name__)


def register_error_handlers(app: Flask) -> None:
    """Install JSON-aware error handlers on the Flask app."""

    @app.errorhandler(ValidationError)
    def _validation(err: ValidationError):
        return jsonify({"error": "validation_error", "message": str(err)}), 400

    @app.errorhandler(HTTPException)
    def _http(err: HTTPException):
        return (
            jsonify(
                {
                    "error": err.name.lower().replace(" ", "_"),
                    "message": err.description,
                }
            ),
            err.code or 500,
        )

    @app.errorhandler(Exception)
    def _generic(err: Exception):
        logger.exception(f"Unhandled error: {err}")
        return (
            jsonify({"error": "internal_error", "message": str(err)}),
            500,
        )
