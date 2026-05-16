"""
ORM models for the academic-notes hierarchy.

    Subject
      └── Unit
            └── Topic
                  └── Subtopic
                        └── Note (the actual content chunk + metadata)

Each Note is associated with a Source (file/URL) and a list of Tags.
"""
from __future__ import annotations

import enum
from datetime import datetime
from typing import List, Optional

from sqlalchemy import (
    Column,
    DateTime,
    Enum,
    ForeignKey,
    Index,
    Integer,
    String,
    Table,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from database.session import Base


# ---------- Enums ----------
class Difficulty(str, enum.Enum):
    EASY = "easy"
    MEDIUM = "medium"
    HARD = "hard"


class SourceType(str, enum.Enum):
    PDF = "pdf"
    DOCX = "docx"
    URL = "url"
    ONENOTE = "onenote"
    MANUAL = "manual"


class ContentType(str, enum.Enum):
    """Semantic kind of academic content held in a Note."""
    NOTES = "notes"
    QNA = "qna"
    HANDWRITTEN = "handwritten"
    QUIZ = "quiz"
    EXAM = "exam"


# ---------- Association tables ----------
note_tags = Table(
    "note_tags",
    Base.metadata,
    Column("note_id", ForeignKey("notes.id", ondelete="CASCADE"), primary_key=True),
    Column("tag_id", ForeignKey("tags.id", ondelete="CASCADE"), primary_key=True),
)


# ---------- Hierarchy models ----------
class Subject(Base):
    """Top-level subject (e.g. 'Mathematics', 'Operating Systems')."""

    __tablename__ = "subjects"
    __table_args__ = (Index("ix_subjects_name", "name", unique=True),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)

    units: Mapped[List["Unit"]] = relationship(
        back_populates="subject", cascade="all, delete-orphan", lazy="selectin"
    )

    def __repr__(self) -> str:  # pragma: no cover
        return f"<Subject id={self.id} name={self.name!r}>"


class Unit(Base):
    """A unit/chapter inside a Subject."""

    __tablename__ = "units"
    __table_args__ = (
        UniqueConstraint("subject_id", "name", name="uq_unit_subject_name"),
        Index("ix_units_subject_id", "subject_id"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    subject_id: Mapped[int] = mapped_column(
        ForeignKey("subjects.id", ondelete="CASCADE"), nullable=False
    )
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    order_index: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)

    subject: Mapped[Subject] = relationship(back_populates="units")
    topics: Mapped[List["Topic"]] = relationship(
        back_populates="unit", cascade="all, delete-orphan", lazy="selectin"
    )


class Topic(Base):
    """A topic inside a Unit."""

    __tablename__ = "topics"
    __table_args__ = (
        UniqueConstraint("unit_id", "name", name="uq_topic_unit_name"),
        Index("ix_topics_unit_id", "unit_id"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    unit_id: Mapped[int] = mapped_column(
        ForeignKey("units.id", ondelete="CASCADE"), nullable=False
    )
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    summary: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)

    unit: Mapped[Unit] = relationship(back_populates="topics")
    subtopics: Mapped[List["Subtopic"]] = relationship(
        back_populates="topic", cascade="all, delete-orphan", lazy="selectin"
    )


class Subtopic(Base):
    """A subtopic inside a Topic — actual notes attach here."""

    __tablename__ = "subtopics"
    __table_args__ = (
        UniqueConstraint("topic_id", "name", name="uq_subtopic_topic_name"),
        Index("ix_subtopics_topic_id", "topic_id"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    topic_id: Mapped[int] = mapped_column(
        ForeignKey("topics.id", ondelete="CASCADE"), nullable=False
    )
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    summary: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)

    topic: Mapped[Topic] = relationship(back_populates="subtopics")
    notes: Mapped[List["Note"]] = relationship(
        back_populates="subtopic", cascade="all, delete-orphan", lazy="selectin"
    )


# ---------- Source & Tag ----------
class Source(Base):
    """The original file/URL that produced one or more notes."""

    __tablename__ = "sources"
    __table_args__ = (
        Index("ix_sources_checksum", "checksum"),
        Index("ix_sources_type", "source_type"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    source_type: Mapped[SourceType] = mapped_column(
        Enum(SourceType), nullable=False, default=SourceType.MANUAL
    )
    title: Mapped[str] = mapped_column(String(500), nullable=False)
    location: Mapped[str] = mapped_column(String(1000), nullable=False)
    checksum: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    extra: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)

    notes: Mapped[List["Note"]] = relationship(back_populates="source", lazy="selectin")


class Tag(Base):
    """Free-form tags used for filtering & faceted browsing."""

    __tablename__ = "tags"
    __table_args__ = (Index("ix_tags_name", "name", unique=True),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(100), nullable=False)

    notes: Mapped[List["Note"]] = relationship(
        secondary=note_tags, back_populates="tags", lazy="selectin"
    )


# ---------- The actual note content ----------
class Note(Base):
    """A leaf note containing the actual content to be retrieved."""

    __tablename__ = "notes"
    __table_args__ = (
        Index("ix_notes_subtopic_id", "subtopic_id"),
        Index("ix_notes_source_id", "source_id"),
        Index("ix_notes_difficulty", "difficulty"),
        Index("ix_notes_content_type", "content_type"),
        Index("ix_notes_created_at", "created_at"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    subtopic_id: Mapped[int] = mapped_column(
        ForeignKey("subtopics.id", ondelete="CASCADE"), nullable=False
    )
    source_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("sources.id", ondelete="SET NULL"), nullable=True
    )

    title: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    difficulty: Mapped[Difficulty] = mapped_column(
        Enum(Difficulty), nullable=False, default=Difficulty.MEDIUM
    )
    content_type: Mapped["ContentType"] = mapped_column(
        Enum(ContentType), nullable=False, default=ContentType.NOTES,
        doc="Semantic kind: notes / qna / handwritten / quiz / exam.",
    )

    # Structured Q&A fields (populated when content_type in {qna, quiz, exam})
    question: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    answer: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    marks: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)

    # Vector pipeline bookkeeping
    embedding_id: Mapped[Optional[str]] = mapped_column(String(64), nullable=True, index=True)
    content_hash: Mapped[Optional[str]] = mapped_column(String(64), nullable=True, index=True)
    token_count: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)

    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False
    )

    subtopic: Mapped[Subtopic] = relationship(back_populates="notes")
    source: Mapped[Optional[Source]] = relationship(back_populates="notes")
    tags: Mapped[List[Tag]] = relationship(
        secondary=note_tags, back_populates="notes", lazy="selectin"
    )

    def to_dict(self) -> dict:
        """Lightweight serialiser used by the API."""
        return {
            "id": self.id,
            "title": self.title,
            "content": self.content,
            "difficulty": self.difficulty.value if self.difficulty else None,
            "content_type": self.content_type.value if self.content_type else None,
            "question": self.question,
            "answer": self.answer,
            "marks": self.marks,
            "subtopic_id": self.subtopic_id,
            "source_id": self.source_id,
            "tags": [t.name for t in self.tags],
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }
