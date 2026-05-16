"""
Repository layer — thin CRUD helpers on top of the ORM models.

Keeping the API blueprints free of raw SQLAlchemy queries makes the
codebase easier to test and re-target (e.g. swapping to MongoDB).
"""
from __future__ import annotations

from typing import Iterable, List, Optional, Sequence

from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from database.models import (
    ContentType,
    Difficulty,
    Note,
    Source,
    SourceType,
    Subject,
    Subtopic,
    Tag,
    Topic,
    Unit,
)


# ---------- Hierarchy ----------
def get_or_create_subject(session: Session, name: str, description: str | None = None) -> Subject:
    obj = session.scalar(select(Subject).where(Subject.name == name))
    if obj:
        return obj
    obj = Subject(name=name, description=description)
    session.add(obj)
    session.flush()
    return obj


def get_or_create_unit(session: Session, subject: Subject, name: str) -> Unit:
    obj = session.scalar(
        select(Unit).where(Unit.subject_id == subject.id, Unit.name == name)
    )
    if obj:
        return obj
    obj = Unit(subject_id=subject.id, name=name)
    session.add(obj)
    session.flush()
    return obj


def get_or_create_topic(session: Session, unit: Unit, name: str) -> Topic:
    obj = session.scalar(
        select(Topic).where(Topic.unit_id == unit.id, Topic.name == name)
    )
    if obj:
        return obj
    obj = Topic(unit_id=unit.id, name=name)
    session.add(obj)
    session.flush()
    return obj


def get_or_create_subtopic(session: Session, topic: Topic, name: str) -> Subtopic:
    obj = session.scalar(
        select(Subtopic).where(Subtopic.topic_id == topic.id, Subtopic.name == name)
    )
    if obj:
        return obj
    obj = Subtopic(topic_id=topic.id, name=name)
    session.add(obj)
    session.flush()
    return obj


def get_or_create_tag(session: Session, name: str) -> Tag:
    name = name.strip().lower()
    obj = session.scalar(select(Tag).where(Tag.name == name))
    if obj:
        return obj
    obj = Tag(name=name)
    session.add(obj)
    session.flush()
    return obj


# ---------- Sources ----------
def create_source(
    session: Session,
    *,
    source_type: SourceType,
    title: str,
    location: str,
    checksum: str | None = None,
    extra: str | None = None,
) -> Source:
    obj = Source(
        source_type=source_type,
        title=title,
        location=location,
        checksum=checksum,
        extra=extra,
    )
    session.add(obj)
    session.flush()
    return obj


def find_source_by_checksum(session: Session, checksum: str) -> Optional[Source]:
    return session.scalar(select(Source).where(Source.checksum == checksum))


# ---------- Notes ----------
def create_note(
    session: Session,
    *,
    subtopic: Subtopic,
    content: str,
    title: str | None = None,
    source: Source | None = None,
    difficulty: Difficulty = Difficulty.MEDIUM,
    tag_names: Iterable[str] = (),
    content_hash: str | None = None,
    token_count: int | None = None,
    content_type: "ContentType" = None,
    question: str | None = None,
    answer: str | None = None,
    marks: int | None = None,
) -> Note:
    from database.models import ContentType as _CT
    ctype = content_type or _CT.NOTES
    note = Note(
        subtopic_id=subtopic.id,
        title=title,
        content=content,
        source_id=source.id if source else None,
        difficulty=difficulty,
        content_type=ctype,
        question=question,
        answer=answer,
        marks=marks,
        content_hash=content_hash,
        token_count=token_count,
    )
    session.add(note)
    session.flush()
    for t in tag_names:
        if t:
            note.tags.append(get_or_create_tag(session, t))
    session.flush()
    return note


def get_notes_by_ids(session: Session, ids: Sequence[int]) -> List[Note]:
    if not ids:
        return []
    return list(session.scalars(select(Note).where(Note.id.in_(ids))))


def update_note_embedding_id(session: Session, note_id: int, embedding_id: str) -> None:
    note = session.get(Note, note_id)
    if note:
        note.embedding_id = embedding_id
        session.flush()


# ---------- Browsing ----------
def list_subjects(session: Session) -> List[Subject]:
    return list(session.scalars(select(Subject).order_by(Subject.name)))


def list_units(session: Session, subject_id: int | None = None) -> List[Unit]:
    stmt = select(Unit).order_by(Unit.subject_id, Unit.order_index, Unit.name)
    if subject_id is not None:
        stmt = stmt.where(Unit.subject_id == subject_id)
    return list(session.scalars(stmt))


def list_topics(session: Session, unit_id: int | None = None) -> List[Topic]:
    stmt = select(Topic).order_by(Topic.unit_id, Topic.name)
    if unit_id is not None:
        stmt = stmt.where(Topic.unit_id == unit_id)
    return list(session.scalars(stmt))


def search_notes(session: Session, q: str, limit: int = 50) -> List[Note]:
    """Plain text search fallback (use RAG for semantic)."""
    like = f"%{q.strip()}%"
    stmt = (
        select(Note)
        .where(or_(Note.content.ilike(like), Note.title.ilike(like)))
        .limit(limit)
    )
    return list(session.scalars(stmt))
