"""
Batch-ingest a folder of PDFs into NotesRAG.

Usage
-----
    # ingest every PDF in a folder, auto-detecting content type from filename
    python -m scripts.batch_ingest --path "/path/to/pdfs" \
        --subject "Operating Systems" --unit "Core Concepts"

    # explicit content type for the whole batch
    python -m scripts.batch_ingest --path ./study_pdfs \
        --subject OS --unit Processes --topic Scheduling --subtopic RR \
        --content-type qna

Filename-based content-type inference
-------------------------------------
    *handwritten*, *scan*           → handwritten   (forces OCR)
    *quiz*                          → quiz
    *exam*, *midterm*, *final*      → exam
    *qna*, *q&a*, *qanda*, *questions*, *answer*  → qna
    everything else                 → notes (auto-upgraded to qna if patterns detected)

Each file's *Topic* defaults to its filename stem unless `--topic` is
supplied. Each file's *Subtopic* defaults to the first section header
found in the doc, or the filename if none.

Already-ingested files (matched by SHA-256 checksum) are skipped.
"""
from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path
from typing import List

from config import settings
from data_ingestion import IngestionPipeline
from database.models import ContentType, Difficulty
from database.repository import get_notes_by_ids
from database.session import get_session, init_db
from rag_pipeline import RAGPipeline
from utils.logger import get_logger

logger = get_logger("batch_ingest")


_FILENAME_HINTS: list[tuple[str, ContentType]] = [
    ("handwritten", ContentType.HANDWRITTEN),
    ("hand-written", ContentType.HANDWRITTEN),
    ("scan", ContentType.HANDWRITTEN),
    ("quiz", ContentType.QUIZ),
    ("exam", ContentType.EXAM),
    ("midterm", ContentType.EXAM),
    ("final-paper", ContentType.EXAM),
    ("question-paper", ContentType.EXAM),
    ("qna", ContentType.QNA),
    ("q&a", ContentType.QNA),
    ("qanda", ContentType.QNA),
    ("questions", ContentType.QNA),
    ("answer", ContentType.QNA),
]


def infer_content_type(filename: str) -> ContentType:
    """Heuristic mapping from a filename to a ContentType."""
    name = filename.lower()
    for needle, ctype in _FILENAME_HINTS:
        if needle in name:
            return ctype
    return ContentType.NOTES


def find_pdfs(root: Path, recursive: bool) -> List[Path]:
    if root.is_file() and root.suffix.lower() == ".pdf":
        return [root]
    pattern = "**/*.pdf" if recursive else "*.pdf"
    return sorted([p for p in root.glob(pattern) if p.is_file()])


def parse_args() -> argparse.Namespace:
    ap = argparse.ArgumentParser(
        description="Batch-ingest PDFs into NotesRAG.",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    ap.add_argument("--path", required=True, help="File or folder containing PDFs.")
    ap.add_argument("--subject", required=True, help="Subject name (created if missing).")
    ap.add_argument("--unit", required=True, help="Unit / chapter name.")
    ap.add_argument(
        "--topic",
        default=None,
        help="Topic name. Defaults to the filename stem of each PDF.",
    )
    ap.add_argument(
        "--subtopic",
        default=None,
        help="Subtopic. Defaults to 'general' or to the file's content type.",
    )
    ap.add_argument(
        "--content-type",
        choices=[c.value for c in ContentType] + ["auto"],
        default="auto",
        help="Force a content type or 'auto' to infer from filename.",
    )
    ap.add_argument(
        "--difficulty",
        choices=[d.value for d in Difficulty],
        default=Difficulty.MEDIUM.value,
    )
    ap.add_argument("--tags", default="", help="Comma-separated tag list.")
    ap.add_argument(
        "--recursive",
        action="store_true",
        help="Recurse into subfolders.",
    )
    ap.add_argument(
        "--force-ocr",
        action="store_true",
        help="Force OCR on every page of every PDF.",
    )
    ap.add_argument(
        "--no-index",
        action="store_true",
        help="Skip building the FAISS index (DB-only ingest).",
    )
    ap.add_argument(
        "--dry-run",
        action="store_true",
        help="Show what would happen without writing anything.",
    )
    return ap.parse_args()


def main() -> int:
    args = parse_args()
    root = Path(args.path).expanduser().resolve()
    if not root.exists():
        logger.error(f"Path not found: {root}")
        return 2

    pdfs = find_pdfs(root, recursive=args.recursive)
    if not pdfs:
        logger.error(f"No PDFs found under {root}")
        return 1

    tags = [t.strip() for t in args.tags.split(",") if t.strip()]

    print(f"\nFound {len(pdfs)} PDF(s) under {root}")
    print("-" * 64)
    print(f"{'#':>3}  {'Type':12} {'File'}")
    for i, pdf in enumerate(pdfs, 1):
        ctype = (
            ContentType(args.content_type) if args.content_type != "auto"
            else infer_content_type(pdf.name)
        )
        print(f"{i:>3}  {ctype.value:12} {pdf.relative_to(root) if pdf.parent != root.parent else pdf.name}")
    print("-" * 64)

    if args.dry_run:
        print("\n(dry-run — nothing was written)")
        return 0

    init_db()
    pipeline = IngestionPipeline()
    rag = RAGPipeline() if not args.no_index else None

    summary = {"ok": 0, "dup": 0, "fail": 0, "chunks": 0}
    for i, pdf in enumerate(pdfs, 1):
        ctype = (
            ContentType(args.content_type) if args.content_type != "auto"
            else infer_content_type(pdf.name)
        )
        topic = args.topic or pdf.stem.replace("_", " ").replace("-", " ").title()
        subtopic = args.subtopic or ctype.value.title()

        logger.info(f"[{i}/{len(pdfs)}] {pdf.name}  ({ctype.value})")
        try:
            result = pipeline.ingest(
                str(pdf),
                subject=args.subject,
                unit=args.unit,
                topic=topic,
                subtopic=subtopic,
                difficulty=Difficulty(args.difficulty),
                tags=tags + [f"type:{ctype.value}"],
                content_type=ctype,
                force_ocr=args.force_ocr,
            )
        except Exception as e:
            logger.exception(f"  failed: {e}")
            summary["fail"] += 1
            continue

        if result.duplicate:
            print(f"  ↻ duplicate (source_id={result.source_id}) — skipped indexing")
            summary["dup"] += 1
            continue

        summary["ok"] += 1
        print(f"  ✓ {len(result.note_ids)} notes created (source_id={result.source_id})")

        if rag is not None and result.note_ids:
            with get_session() as s:
                notes = get_notes_by_ids(s, result.note_ids)
                added = rag.build_vector_index(notes)
            summary["chunks"] += added
            print(f"  ⇢ indexed {added} chunks (FAISS total={rag.store.size})")

    print("\nDone.")
    print(f"  ingested:   {summary['ok']}")
    print(f"  duplicates: {summary['dup']}")
    print(f"  failed:     {summary['fail']}")
    print(f"  chunks:     {summary['chunks']}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
