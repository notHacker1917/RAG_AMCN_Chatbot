"""Flask application factory and blueprint registration."""
from __future__ import annotations

from flask import Flask, jsonify
from flask_cors import CORS

from api.blueprints.health import bp as health_bp
from api.blueprints.notes_browse import bp as browse_bp
from api.blueprints.query import bp as query_bp
from api.blueprints.search import bp as search_bp
from api.blueprints.upload import bp as upload_bp
from api.errors import register_error_handlers
from config import settings
from utils.logger import get_logger

logger = get_logger(__name__)


def create_app() -> Flask:
    """Application factory."""
    app = Flask(__name__)
    app.config.update(
        SECRET_KEY=settings.api_secret_key,
        MAX_CONTENT_LENGTH=settings.max_upload_mb * 1024 * 1024,
        JSON_SORT_KEYS=False,
    )
    CORS(app, resources={r"/*": {"origins": "*"}})

    # Blueprints
    app.register_blueprint(health_bp)
    app.register_blueprint(upload_bp, url_prefix="/upload")
    app.register_blueprint(query_bp, url_prefix="/query")
    app.register_blueprint(browse_bp)
    app.register_blueprint(search_bp, url_prefix="/search")

    register_error_handlers(app)

    @app.route("/")
    def index():
        return jsonify(
            {
                "name": "NotesRAG-Chatbot",
                "version": "1.0.0",
                "endpoints": [
                    "GET  /health",
                    "POST /upload",
                    "POST /upload/url",
                    "POST /query",
                    "GET  /subjects",
                    "GET  /units",
                    "GET  /topics",
                    "GET  /search",
                ],
            }
        )

    logger.info("Flask app created.")
    return app


__all__ = ["create_app"]
