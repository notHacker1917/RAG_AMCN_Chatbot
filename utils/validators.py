"""Lightweight request validators used by the Flask API."""
from __future__ import annotations

from typing import Any, Mapping


class ValidationError(ValueError):
    """Raised when a request payload fails validation."""


def require(payload: Mapping[str, Any], *keys: str) -> None:
    """Raise ValidationError if any required key is missing/empty."""
    missing = [k for k in keys if k not in payload or payload[k] in (None, "")]
    if missing:
        raise ValidationError(f"Missing required field(s): {', '.join(missing)}")


def ensure_str(value: Any, field: str, max_len: int = 4000) -> str:
    if not isinstance(value, str):
        raise ValidationError(f"'{field}' must be a string")
    if len(value) > max_len:
        raise ValidationError(f"'{field}' exceeds max length {max_len}")
    return value


def ensure_int(value: Any, field: str, lo: int | None = None, hi: int | None = None) -> int:
    try:
        v = int(value)
    except (TypeError, ValueError):
        raise ValidationError(f"'{field}' must be an integer")
    if lo is not None and v < lo:
        raise ValidationError(f"'{field}' must be >= {lo}")
    if hi is not None and v > hi:
        raise ValidationError(f"'{field}' must be <= {hi}")
    return v
