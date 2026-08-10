"""
NotesRAG-Chatbot — Application Entry Point
==========================================

Boots the Flask API server. The Streamlit frontend is launched
separately (`streamlit run frontend/streamlit_app/main.py`).

Usage
-----
    python app.py
    gunicorn -w 4 -b 0.0.0.0:5000 app:app
"""
from __future__ import annotations

import os

from api import create_app
from database.session import init_db
from utils.logger import get_logger

logger = get_logger(__name__)
 
app = create_app()


def _bootstrap() -> None:
    """Run one-time startup tasks (DB creation, directory setup)."""
    logger.info("Bootstrapping NotesRAG-Chatbot …")
    init_db()
    for path in (
        os.getenv("RAW_FILES_DIR", "./storage/raw_files"),
        os.getenv("PROCESSED_DIR", "./storage/processed"),
        os.path.dirname(
            os.getenv("FAISS_INDEX_PATH", "./storage/faiss_index/notes.index")
        ),
        os.getenv("LOG_DIR", "./logs"),
    ):
        os.makedirs(path, exist_ok=True)
    logger.info("Bootstrap complete.")


if __name__ == "__main__":
    _bootstrap()
    host = os.getenv("API_HOST", "0.0.0.0")
    port = int(os.getenv("API_PORT", "5000"))
    debug = os.getenv("FLASK_DEBUG", "0") == "1"
    logger.info(f"Starting Flask API on {host}:{port} (debug={debug})")
    app.run(host=host, port=port, debug=debug)
