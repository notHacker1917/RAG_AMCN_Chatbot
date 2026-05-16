"""
Thin HTTP client used by the Streamlit UI to talk to the Flask API.

Keeping this in its own module means the UI components don't import
`requests` directly and we can swap to a mock in tests.
"""
from __future__ import annotations

import os
from typing import Any, Dict, List

import requests

API_BASE_URL = os.getenv("API_BASE_URL", "http://localhost:5000")
TIMEOUT = 60


class APIError(RuntimeError):
    pass


def _check(resp: requests.Response) -> dict:
    try:
        data = resp.json()
    except ValueError:
        data = {"error": "non_json", "message": resp.text[:300]}
    if not resp.ok:
        raise APIError(data.get("message") or f"HTTP {resp.status_code}")
    return data


def ping() -> Dict[str, Any]:
    return _check(requests.get(f"{API_BASE_URL}/health", timeout=TIMEOUT))


def list_subjects() -> List[dict]:
    return _check(requests.get(f"{API_BASE_URL}/subjects", timeout=TIMEOUT))


def list_units(subject_id: int | None = None) -> List[dict]:
    params = {"subject_id": subject_id} if subject_id else {}
    return _check(requests.get(f"{API_BASE_URL}/units", params=params, timeout=TIMEOUT))


def list_topics(unit_id: int | None = None) -> List[dict]:
    params = {"unit_id": unit_id} if unit_id else {}
    return _check(requests.get(f"{API_BASE_URL}/topics", params=params, timeout=TIMEOUT))


def search(q: str, mode: str = "semantic", limit: int = 10) -> dict:
    return _check(
        requests.get(
            f"{API_BASE_URL}/search",
            params={"q": q, "mode": mode, "limit": limit},
            timeout=TIMEOUT,
        )
    )


def ask(
    query: str,
    top_k: int = 5,
    history: List[dict] | None = None,
    use_mpc: bool = False,
) -> dict:
    payload = {
        "query": query,
        "top_k": top_k,
        "history": history or [],
        "use_mpc": use_mpc,
    }
    return _check(
        requests.post(f"{API_BASE_URL}/query", json=payload, timeout=TIMEOUT)
    )


def upload_file(file, meta: dict) -> dict:
    files = {"file": (file.name, file.getvalue(), file.type or "application/octet-stream")}
    return _check(
        requests.post(
            f"{API_BASE_URL}/upload", data=meta, files=files, timeout=TIMEOUT
        )
    )


def upload_url(url: str, meta: dict) -> dict:
    return _check(
        requests.post(
            f"{API_BASE_URL}/upload/url",
            json={"url": url, **meta},
            timeout=TIMEOUT,
        )
    )
