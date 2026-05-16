"""Website loader using `requests` + BeautifulSoup."""
from __future__ import annotations

from typing import Any
from urllib.parse import urlparse

import requests
from bs4 import BeautifulSoup

from utils.hashing import sha256_text
from utils.logger import get_logger
from utils.text_cleaning import clean_text

from .base import IngestedDocument, IngestedSection

logger = get_logger(__name__)

_HEADERS = {
    "User-Agent": "NotesRAG-Chatbot/1.0 (+https://example.com)"
}


class URLLoader:
    name = "url"

    def supports(self, location: str, mimetype: str | None = None) -> bool:
        parsed = urlparse(location)
        return parsed.scheme in {"http", "https"}

    def load(self, location: str, **_: Any) -> IngestedDocument:
        logger.info(f"Fetching URL: {location}")
        resp = requests.get(location, headers=_HEADERS, timeout=30)
        resp.raise_for_status()
        soup = BeautifulSoup(resp.text, "lxml")

        # Strip nav/aside/script
        for tag in soup(["script", "style", "noscript", "nav", "footer", "aside"]):
            tag.decompose()

        title = (soup.title.string.strip() if soup.title and soup.title.string else location)

        sections: list[IngestedSection] = []
        current = {"heading": "", "level": 0, "buf": []}

        def flush() -> None:
            text = clean_text("\n".join(current["buf"]))
            if text:
                sections.append(
                    IngestedSection(
                        text=text,
                        heading=current["heading"],
                        level=current["level"],
                    )
                )
            current["buf"] = []

        body = soup.body or soup
        for el in body.find_all(["h1", "h2", "h3", "h4", "p", "li"]):
            text = el.get_text(" ", strip=True)
            if not text:
                continue
            if el.name.startswith("h"):
                flush()
                current["heading"] = text
                current["level"] = int(el.name[1])
            else:
                current["buf"].append(text)
        flush()

        full_text = "\n\n".join(s.text for s in sections)
        return IngestedDocument(
            source_type="url",
            title=title,
            location=location,
            checksum=sha256_text(full_text),
            sections=sections,
            metadata={"content_type": resp.headers.get("Content-Type", "")},
        )
