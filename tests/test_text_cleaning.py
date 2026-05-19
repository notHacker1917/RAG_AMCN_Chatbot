from utils.text_cleaning import clean_text


def test_collapses_whitespace_and_newlines():
    raw = "Hello   world\n\n\n\nNext   line\x00 with control"
    out = clean_text(raw)
    assert "  " not in out
    assert "\x00" not in out
    assert "Hello world" in out
