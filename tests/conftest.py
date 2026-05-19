"""Pytest fixtures."""
from __future__ import annotations

import os
import tempfile

import pytest

# Use an in-memory SQLite DB and disable Claude/embedding calls in tests.
os.environ.setdefault("DATABASE_URL", "sqlite:///:memory:")
os.environ.setdefault("ANTHROPIC_API_KEY", "")
os.environ.setdefault("LOG_LEVEL", "WARNING")


@pytest.fixture(scope="session")
def tmp_storage(tmp_path_factory):
    d = tmp_path_factory.mktemp("storage")
    os.environ["RAW_FILES_DIR"] = str(d / "raw_files")
    os.environ["FAISS_INDEX_PATH"] = str(d / "faiss/notes.index")
    os.environ["FAISS_META_PATH"] = str(d / "faiss/notes_meta.pkl")
    return d


@pytest.fixture()
def app(tmp_storage):
    from api import create_app
    from database.session import init_db

    init_db()
    flask_app = create_app()
    flask_app.config.update(TESTING=True)
    return flask_app


@pytest.fixture()
def client(app):
    return app.test_client()
