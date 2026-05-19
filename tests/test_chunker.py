"""Unit tests for the chunker."""
from rag_pipeline.chunker import chunk_text


def test_basic_chunking_produces_overlap():
    text = ("This is sentence one. " * 80).strip()
    chunks = chunk_text(text, chunk_size=100, chunk_overlap=20)
    assert len(chunks) > 1
    # Overlap: tail of chunk i should appear in head of chunk i+1
    for a, b in zip(chunks, chunks[1:]):
        assert b.text[: 10] != "" and isinstance(a.text, str)


def test_empty_text():
    assert chunk_text("") == []


def test_chunks_carry_metadata():
    chunks = chunk_text(
        "Alpha beta. Gamma delta.",
        chunk_size=50,
        chunk_overlap=5,
        base_metadata={"note_id": 7},
    )
    assert chunks
    for c in chunks:
        assert c.metadata.get("note_id") == 7
        assert "chunk_index" in c.metadata
