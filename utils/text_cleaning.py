"""
Text cleaning / normalisation helpers used by the ingestion pipeline.
"""
from __future__ import annotations

import re
import unicodedata
from typing import Iterable

_WS_RE = re.compile(r"[ \t ]+")
_MULTI_NL_RE = re.compile(r"\n{3,}")
_CONTROL_RE = re.compile(r"[\x00-\x08\x0b-\x1f\x7f]")


def normalise_unicode(text: str) -> str:
    """Apply NFKC normalisation and strip BOM/zero-width chars."""
    text = unicodedata.normalize("NFKC", text)
    return text.replace("﻿", "").replace("​", "")


def strip_control_chars(text: str) -> str:
    """Remove control characters except newline/tab."""
    return _CONTROL_RE.sub("", text)


def collapse_whitespace(text: str) -> str:
    """Collapse runs of horizontal whitespace and reduce blank lines."""
    lines = []
    for line in text.splitlines():
        line = _WS_RE.sub(" ", line).rstrip()
        lines.append(line)
    cleaned = "\n".join(lines)
    return _MULTI_NL_RE.sub("\n\n", cleaned).strip()


def clean_text(text: str) -> str:
    """Full cleaning pipeline applied to extracted document text."""
    if not text:
        return ""
    text = normalise_unicode(text)
    text = strip_control_chars(text)
    return collapse_whitespace(text)


def join_paragraphs(paragraphs: Iterable[str]) -> str:
    """Join paragraphs while filtering empties."""
    return "\n\n".join(p.strip() for p in paragraphs if p and p.strip())
