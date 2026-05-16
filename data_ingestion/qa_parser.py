"""
Question-Answer / Quiz / Exam-paper parser.

Detects common patterns in PDFs containing structured Q&A material:

    Q1. What is paging?
    Ans: Paging splits virtual memory into …

    Question 2: Define context switch                       [5 marks]
    A. The act of saving one process's state …

    1) Explain the Banker's algorithm.   (10)
       Answer: …

It returns a list of `ParsedQA` records carrying `question`, `answer`,
`marks`, `qtype`, and an optional `section` heading. Material that
doesn't match a Q&A pattern is preserved as `prose` blocks.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import List, Optional

# ---- regex catalogue --------------------------------------------------
# Q-line patterns. We deliberately avoid bare "Q " (with no digit and
# no separator) and bare "A " to prevent false positives on prose.
_Q_PATTERNS = [
    # Long forms: "Question 2:" / "Ques 3." / "Question:"
    re.compile(r"^\s*(?:Question|Quiz|Ques)\b[.\):\-]?\s*(\d+)?[.\):\-]?\s*(.+?)\s*$", re.IGNORECASE),
    # "Q1." / "Q.1" / "Q 1:" — requires digit
    re.compile(r"^\s*Q[.\):\-]?\s*(\d+)[.\):\-]?\s*(.+?)\s*$", re.IGNORECASE),
    # "Q:" / "Q." / "Q-" — explicit separator, no digit
    re.compile(r"^\s*Q[.\):\-]+\s*()(.+?)\s*$", re.IGNORECASE),
    # Plain numbered list: "1)" or "1." with required space after
    re.compile(r"^\s*(\d+)\s*[.\)]\s+(.+?)\s*$"),
]
# A-line patterns — single-letter "A" requires an explicit separator.
_A_PATTERNS = [
    re.compile(r"^\s*(?:Answer|Solution)\b[.\):\-]?\s*(.*?)\s*$", re.IGNORECASE),
    re.compile(r"^\s*(?:Ans|Sol)\b[.\):\-]\s*(.*?)\s*$", re.IGNORECASE),
    re.compile(r"^\s*A[.\):\-]\s*(.*?)\s*$"),  # case-sensitive: only "A." not "a."
]
_MARKS_RE = re.compile(
    r"[\[\(\{]?\s*(\d{1,3})\s*(?:marks?|points?|pts?)\b\s*[\]\)\}]?",
    re.IGNORECASE,
)
_SECTION_RE = re.compile(
    r"^\s*(?:Section|Part|Unit|Chapter|Module)\s+([A-Z0-9\-]+)\b.*$",
    re.IGNORECASE,
)


# ---- data types -------------------------------------------------------
@dataclass
class ParsedQA:
    """One parsed item — either a Q&A pair or a prose paragraph."""

    kind: str               # "qa" | "prose"
    question: Optional[str] = None
    answer: Optional[str] = None
    qnum: Optional[int] = None
    marks: Optional[int] = None
    section: Optional[str] = None
    text: Optional[str] = None     # for kind=="prose"

    def to_section_text(self) -> str:
        """Render as a single string for embedding."""
        if self.kind == "qa":
            q = self.question or ""
            a = self.answer or ""
            marks = f" [{self.marks} marks]" if self.marks else ""
            return f"Q{('' if self.qnum is None else f' {self.qnum}')}{marks}: {q}\nA: {a}".strip()
        return self.text or ""


# ---- parser -----------------------------------------------------------
def _strip_marks(text: str) -> tuple[str, Optional[int]]:
    """Extract trailing/inline mark hints from a question stem."""
    m = _MARKS_RE.search(text)
    if not m:
        return text.strip(), None
    cleaned = (_MARKS_RE.sub("", text)).strip(" .,:;")
    try:
        return cleaned, int(m.group(1))
    except ValueError:
        return cleaned, None


def _match_q(line: str) -> Optional[tuple[Optional[int], str]]:
    for pat in _Q_PATTERNS:
        m = pat.match(line)
        if not m:
            continue
        num = int(m.group(1)) if m.group(1) and m.group(1).isdigit() else None
        stem = m.group(2).strip()
        # Reject lines that look like sentences ("1 of 5 students…")
        if num is not None and len(stem.split()) < 2:
            continue
        return num, stem
    return None


def _match_a(line: str) -> Optional[str]:
    for pat in _A_PATTERNS:
        m = pat.match(line)
        if m:
            return (m.group(1) or "").strip()
    return None


def parse_qa_text(text: str) -> List[ParsedQA]:
    """
    Parse a block of text into Q&A and prose units.

    Strategy: scan line-by-line. When we see a Q-line we start a new
    record. Subsequent lines accumulate into the question stem until
    we see an A-line; subsequent lines after that accumulate into
    the answer until the next Q-line / section heading / blank gap.
    """
    items: List[ParsedQA] = []
    current_section: Optional[str] = None
    in_q: Optional[ParsedQA] = None
    mode = "init"   # "init" | "question" | "answer"
    prose_buf: list[str] = []
    blank_run = 0

    def flush_q() -> None:
        nonlocal in_q
        if in_q is not None:
            in_q.question = (in_q.question or "").strip()
            in_q.answer = (in_q.answer or "").strip() or None
            items.append(in_q)
            in_q = None

    def flush_prose() -> None:
        nonlocal prose_buf
        if prose_buf:
            joined = "\n".join(prose_buf).strip()
            if joined:
                items.append(ParsedQA(kind="prose", text=joined, section=current_section))
            prose_buf = []

    for raw in text.splitlines():
        line = raw.rstrip()

        # section/part headings
        sm = _SECTION_RE.match(line)
        if sm:
            flush_q()
            flush_prose()
            current_section = sm.group(0).strip()
            continue

        # blank line — soft boundary; 2 consecutive blanks end an answer.
        if not line.strip():
            blank_run += 1
            if mode == "answer" and in_q is not None:
                if blank_run >= 2:
                    flush_q()
                    mode = "init"
                else:
                    if in_q.answer is not None:
                        in_q.answer += "\n"
            else:
                flush_prose()
            continue
        blank_run = 0

        q = _match_q(line)
        if q is not None:
            # close out anything in progress
            flush_q()
            flush_prose()
            num, stem = q
            stem, marks = _strip_marks(stem)
            in_q = ParsedQA(
                kind="qa",
                qnum=num,
                question=stem,
                answer=None,
                marks=marks,
                section=current_section,
            )
            mode = "question"
            continue

        a = _match_a(line)
        if a is not None and in_q is not None:
            in_q.answer = a
            mode = "answer"
            continue

        # continuation
        if mode == "question" and in_q is not None:
            in_q.question = ((in_q.question or "") + " " + line.strip()).strip()
        elif mode == "answer" and in_q is not None:
            in_q.answer = ((in_q.answer or "") + "\n" + line.strip()).strip()
        else:
            prose_buf.append(line.strip())

    flush_q()
    flush_prose()
    return items


def looks_like_qa(text: str, min_hits: int = 2) -> bool:
    """Cheap heuristic — does this block contain at least `min_hits` Q-style lines?"""
    hits = 0
    for line in text.splitlines():
        if _match_q(line):
            hits += 1
            if hits >= min_hits:
                return True
    return False
