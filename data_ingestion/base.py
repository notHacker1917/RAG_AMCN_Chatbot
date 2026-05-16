"""Common dataclasses and protocols for ingestion loaders."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Protocol


@dataclass
class IngestedSection:
    """A hierarchically-located block of text extracted from a document."""

    text: str
    heading: str = ""
    level: int = 0           # heading depth (0 = body, 1 = H1, etc.)
    page: int | None = None
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class IngestedDocument:
    """Result of running a single loader on a single source."""

    source_type: str
    title: str
    location: str
    checksum: str | None = None
    sections: List[IngestedSection] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)

    @property
    def text(self) -> str:
        """Concatenated text useful for hashing/preview."""
        out = []
        for s in self.sections:
            if s.heading:
                out.append(("#" * max(s.level, 1)) + " " + s.heading)
            out.append(s.text)
        return "\n\n".join(p for p in out if p)


class Loader(Protocol):
    """Loader interface."""

    name: str

    def supports(self, location: str, mimetype: str | None = None) -> bool: ...

    def load(self, location: str, **kwargs: Any) -> IngestedDocument: ...
