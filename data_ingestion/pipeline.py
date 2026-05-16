"""
Ingestion pipeline orchestrator.

Routes a source (file or URL) through the appropriate loader, persists
the raw file under `storage/raw_files/`, populates the database, and
returns an `IngestionResult` with the IDs needed to drive the RAG
indexer.
"""
from __future__ import annotations

import os
import shutil
from dataclasses import dataclass
from typing import List, Optional
from urllib.parse import urlparse

from config import settings
from database.models import ContentType, Difficulty, SourceType
from database.repository import (
    create_note,
    create_source,
    find_source_by_checksum,
    get_or_create_subject,
    get_or_create_subtopic,
    get_or_create_topic,
    get_or_create_unit,
)
from database.session import get_session
from utils.hashing import sha256_text
from utils.logger import get_logger

from .base import IngestedDocument, Loader
from .docx_loader import DocxLoader
from .onenote_loader import OneNoteLoader
from .pdf_loader import PDFLoader
from .qa_parser import parse_qa_text, looks_like_qa
from .url_loader import URLLoader

logger = get_logger(__name__)


@dataclass
class IngestionResult:
    source_id: int
    note_ids: List[int]
    title: str
    source_type: str
    duplicate: bool = False


class IngestionPipeline:
    """Pluggable ingestion pipeline."""

    def __init__(self, loaders: Optional[List[Loader]] = None) -> None:
        self.loaders: List[Loader] = loaders or [
            PDFLoader(),
            DocxLoader(),
            OneNoteLoader(),
            URLLoader(),
        ]

    # ----------------- public API -----------------
    def ingest(
        self,
        location: str,
        *,
        subject: str,
        unit: str,
        topic: str,
        subtopic: str,
        difficulty: Difficulty = Difficulty.MEDIUM,
        tags: Optional[List[str]] = None,
        mimetype: str | None = None,
        content_type: ContentType = ContentType.NOTES,
        force_ocr: bool = False,
        auto_detect_qa: bool = True,
    ) -> IngestionResult:
        """
        Ingest one location and persist into the database.

        Parameters
        ----------
        content_type
            Semantic kind of the content. PDF loader uses this to
            decide OCR behaviour (handwritten → always OCR).
        force_ocr
            Force OCR on every page of a PDF, regardless of type.
        auto_detect_qa
            If True and `content_type` is `notes`, sniff the
            extracted text for Q→A patterns and upgrade the type
            to `qna` so individual questions are stored as
            structured notes.
        """
        loader = self._pick(location, mimetype)
        logger.info(
            f"Using loader '{loader.name}' for {location!r} "
            f"(content_type={content_type.value})"
        )
        load_kwargs = {}
        if loader.name == "pdf":
            load_kwargs.update(
                content_type=content_type.value,
                force_ocr=force_ocr,
            )
        doc = loader.load(location, **load_kwargs)

        # Auto-detect: scan the first few sections for Q&A patterns
        effective_type = content_type
        if auto_detect_qa and effective_type == ContentType.NOTES and doc.sections:
            preview = "\n".join(s.text for s in doc.sections[:3])
            if looks_like_qa(preview, min_hits=3):
                logger.info("Auto-detected Q&A content; switching content_type to QNA.")
                effective_type = ContentType.QNA

        # Persist raw file when it's a local file
        if not self._is_url(location):
            self._store_raw_file(location)

        with get_session() as s:
            # Deduplicate by checksum
            existing = (
                find_source_by_checksum(s, doc.checksum) if doc.checksum else None
            )
            if existing:
                logger.info(
                    f"Source already ingested (checksum match) — id={existing.id}"
                )
                return IngestionResult(
                    source_id=existing.id,
                    note_ids=[n.id for n in existing.notes],
                    title=existing.title,
                    source_type=existing.source_type.value,
                    duplicate=True,
                )

            src = create_source(
                s,
                source_type=SourceType(doc.source_type),
                title=doc.title,
                location=doc.location,
                checksum=doc.checksum,
                extra=str(doc.metadata) if doc.metadata else None,
            )

            subj_obj = get_or_create_subject(s, subject)
            unit_obj = get_or_create_unit(s, subj_obj, unit)
            topic_obj = get_or_create_topic(s, unit_obj, topic)
            subtopic_obj = get_or_create_subtopic(s, topic_obj, subtopic)

            note_ids: list[int] = []
            structured_types = {ContentType.QNA, ContentType.QUIZ, ContentType.EXAM}
            for section in doc.sections:
                base_tags = (tags or []) + section.metadata.get("tags", [])

                if effective_type in structured_types:
                    parsed = parse_qa_text(section.text)
                    if not parsed:
                        # fall back to plain note
                        note = create_note(
                            s,
                            subtopic=subtopic_obj,
                            title=section.heading or None,
                            content=section.text,
                            source=src,
                            difficulty=difficulty,
                            content_type=effective_type,
                            tag_names=base_tags,
                            content_hash=sha256_text(section.text),
                            token_count=max(1, len(section.text.split())),
                        )
                        note_ids.append(note.id)
                        continue
                    for item in parsed:
                        title = (
                            section.heading or item.section
                            or (f"Q{item.qnum}" if item.qnum else None)
                        )
                        content_for_embed = item.to_section_text()
                        note = create_note(
                            s,
                            subtopic=subtopic_obj,
                            title=title,
                            content=content_for_embed,
                            source=src,
                            difficulty=difficulty,
                            content_type=(
                                effective_type if item.kind == "qa"
                                else ContentType.NOTES
                            ),
                            question=item.question,
                            answer=item.answer,
                            marks=item.marks,
                            tag_names=base_tags + (
                                [f"section:{item.section}"] if item.section else []
                            ),
                            content_hash=sha256_text(content_for_embed),
                            token_count=max(1, len(content_for_embed.split())),
                        )
                        note_ids.append(note.id)
                else:
                    note = create_note(
                        s,
                        subtopic=subtopic_obj,
                        title=section.heading or None,
                        content=section.text,
                        source=src,
                        difficulty=difficulty,
                        content_type=effective_type,
                        tag_names=base_tags,
                        content_hash=sha256_text(section.text),
                        token_count=max(1, len(section.text.split())),
                    )
                    note_ids.append(note.id)

            return IngestionResult(
                source_id=src.id,
                note_ids=note_ids,
                title=doc.title,
                source_type=doc.source_type,
            )

    # ----------------- helpers -----------------
    def _pick(self, location: str, mimetype: str | None) -> Loader:
        for loader in self.loaders:
            if loader.supports(location, mimetype):
                return loader
        raise ValueError(f"No loader supports source: {location!r}")

    @staticmethod
    def _is_url(location: str) -> bool:
        return urlparse(location).scheme in {"http", "https"}

    @staticmethod
    def _store_raw_file(src_path: str) -> str:
        raw_dir = settings.resolve(settings.raw_files_dir)
        raw_dir.mkdir(parents=True, exist_ok=True)
        dst = raw_dir / os.path.basename(src_path)
        if os.path.abspath(src_path) != str(dst):
            try:
                shutil.copy2(src_path, dst)
            except shutil.SameFileError:
                pass
        return str(dst)
