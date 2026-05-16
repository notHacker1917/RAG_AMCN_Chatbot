"""
OneNote-export loader.

The real Microsoft OneNote APIs require Graph authentication; for
educational purposes we accept JSON exports with the structure:

    {
      "title": "Operating Systems Notebook",
      "sections": [
         {"heading": "Process Mgmt", "level": 1,
          "items": [{"text": "...", "tags": ["scheduling"]}, ...]},
         ...
      ]
    }
"""
from __future__ import annotations

import json
import os
from typing import Any

from utils.hashing import sha256_file
from utils.logger import get_logger
from utils.text_cleaning import clean_text

from .base import IngestedDocument, IngestedSection

logger = get_logger(__name__)


class OneNoteLoader:
    name = "onenote"

    def supports(self, location: str, mimetype: str | None = None) -> bool:
        if location.lower().endswith(".json"):
            return True
        return mimetype == "application/json"

    def load(self, location: str, **_: Any) -> IngestedDocument:
        with open(location, "r", encoding="utf-8") as f:
            data = json.load(f)

        title = data.get("title", os.path.basename(location))
        sections: list[IngestedSection] = []
        for sec in data.get("sections", []):
            heading = sec.get("heading", "")
            level = int(sec.get("level", 1))
            parts: list[str] = []
            tags: list[str] = []
            for item in sec.get("items", []):
                if isinstance(item, str):
                    parts.append(item)
                elif isinstance(item, dict):
                    parts.append(item.get("text", ""))
                    tags.extend(item.get("tags", []) or [])
            text = clean_text("\n".join(parts))
            if text:
                sections.append(
                    IngestedSection(
                        text=text,
                        heading=heading,
                        level=level,
                        metadata={"tags": tags},
                    )
                )

        return IngestedDocument(
            source_type="onenote",
            title=title,
            location=os.path.abspath(location),
            checksum=sha256_file(location),
            sections=sections,
            metadata={"notebook": data.get("notebook", "")},
        )
