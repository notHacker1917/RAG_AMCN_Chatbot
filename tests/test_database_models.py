"""Integration test for the ORM models + repository helpers."""
from database.models import Difficulty, SourceType
from database.repository import (
    create_note,
    create_source,
    get_or_create_subject,
    get_or_create_subtopic,
    get_or_create_topic,
    get_or_create_unit,
)
from database.session import get_session, init_db


def test_full_hierarchy_roundtrip(tmp_storage):
    init_db()
    with get_session() as s:
        subj = get_or_create_subject(s, "Operating Systems")
        unit = get_or_create_unit(s, subj, "Processes")
        topic = get_or_create_topic(s, unit, "Scheduling")
        sub = get_or_create_subtopic(s, topic, "Round Robin")
        src = create_source(
            s,
            source_type=SourceType.MANUAL,
            title="lecture-3.pdf",
            location="/tmp/lecture-3.pdf",
            checksum="abc",
        )
        note = create_note(
            s,
            subtopic=sub,
            content="Round-robin assigns equal time slices…",
            source=src,
            difficulty=Difficulty.MEDIUM,
            tag_names=["scheduling", "cpu"],
        )
        assert note.id is not None
        d = note.to_dict()
        assert d["content"].startswith("Round-robin")
        assert "scheduling" in d["tags"]
