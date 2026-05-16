"""
PDF loader with Tesseract OCR fallback for scanned / handwritten PDFs.

Behaviour
---------
* For each page we first try `pdfplumber.extract_text()` (or PyMuPDF
  as a fallback).
* If `content_type == "handwritten"` we skip straight to OCR.
* If a page produces a suspiciously small amount of text (likely a
  scanned image) AND `ocr_when_empty=True`, we render the page via
  PyMuPDF and OCR it with `pytesseract`.
* OCR is optional — if `pytesseract` isn't installed (or the
  `tesseract` binary is missing) we log a warning and return the
  empty/extracted text unchanged.
"""
from __future__ import annotations

import os
from typing import Any, List, Optional

from utils.hashing import sha256_file
from utils.logger import get_logger
from utils.text_cleaning import clean_text

from .base import IngestedDocument, IngestedSection

logger = get_logger(__name__)

# Pages with fewer than this many non-whitespace chars get OCR'd
_OCR_TRIGGER_CHARS = 40


def _try_ocr_page(pdf_path: str, page_index_0: int, dpi: int = 300) -> str:
    """Render a single page with PyMuPDF and OCR it via pytesseract."""
    try:
        import fitz  # PyMuPDF
        import pytesseract  # type: ignore
        from PIL import Image  # noqa: F401  (PIL is pulled in by pytesseract)
    except ImportError as e:
        logger.warning(
            f"OCR unavailable ({e}). "
            f"Install with `pip install pytesseract pillow` and ensure "
            f"the `tesseract` binary is on PATH."
        )
        return ""

    try:
        doc = fitz.open(pdf_path)
        page = doc.load_page(page_index_0)
        pix = page.get_pixmap(dpi=dpi, alpha=False)
        img_bytes = pix.tobytes("png")
        from io import BytesIO
        from PIL import Image as PILImage

        img = PILImage.open(BytesIO(img_bytes))
        text = pytesseract.image_to_string(img, lang=os.getenv("TESSERACT_LANG", "eng"))
        doc.close()
        return text or ""
    except Exception as e:  # pragma: no cover
        logger.warning(f"OCR failed on page {page_index_0 + 1}: {e}")
        return ""


def _extract_with_pdfplumber(path: str) -> tuple[List[str], dict]:
    import pdfplumber  # type: ignore

    pages: list[str] = []
    with pdfplumber.open(path) as pdf:
        meta = pdf.metadata or {}
        for page in pdf.pages:
            pages.append(page.extract_text() or "")
    return pages, dict(meta)


def _extract_with_pymupdf(path: str) -> tuple[List[str], dict]:
    import fitz  # type: ignore

    pages: list[str] = []
    doc = fitz.open(path)
    meta = dict(doc.metadata or {})
    for page in doc:
        pages.append(page.get_text() or "")
    doc.close()
    return pages, meta


class PDFLoader:
    name = "pdf"

    def __init__(self, *, ocr_when_empty: bool = True) -> None:
        self.ocr_when_empty = ocr_when_empty

    def supports(self, location: str, mimetype: str | None = None) -> bool:
        return location.lower().endswith(".pdf") or mimetype == "application/pdf"

    def load(
        self,
        location: str,
        *,
        content_type: str | None = None,
        force_ocr: bool | None = None,
        **_: Any,
    ) -> IngestedDocument:
        """
        Extract text page-by-page; OCR scanned/handwritten pages.

        Parameters
        ----------
        content_type
            Optional hint ("handwritten" → always OCR).
        force_ocr
            Explicit override; if `True`, every page is OCR'd.
        """
        force_ocr = bool(force_ocr) or (content_type == "handwritten")

        # 1. Try PyMuPDF first (fast on slide decks), fall back to pdfplumber.
        pages: List[str] = []
        meta: dict = {}
        if not force_ocr:
            try:
                pages, meta = _extract_with_pymupdf(location)
            except Exception as e:
                logger.info(f"PyMuPDF failed ({e}); falling back to pdfplumber.")
                try:
                    pages, meta = _extract_with_pdfplumber(location)
                except Exception as e2:  # pragma: no cover
                    logger.error(f"Both PDF parsers failed: {e2}")
                    pages = []

        # 2. OCR pass for empty / handwritten pages
        ocr_used: list[int] = []
        if force_ocr:
            try:
                import fitz  # type: ignore

                doc = fitz.open(location)
                pages = [""] * doc.page_count
                meta = dict(doc.metadata or {})
                doc.close()
            except Exception:  # pragma: no cover
                pass
            for i in range(len(pages)):
                pages[i] = _try_ocr_page(location, i)
                ocr_used.append(i + 1)
        elif self.ocr_when_empty:
            for i, text in enumerate(pages):
                if len((text or "").strip()) < _OCR_TRIGGER_CHARS:
                    ocr_text = _try_ocr_page(location, i)
                    if ocr_text.strip():
                        pages[i] = ocr_text
                        ocr_used.append(i + 1)

        # 3. Build sections
        sections: list[IngestedSection] = []
        for i, raw in enumerate(pages, start=1):
            cleaned = clean_text(raw)
            if cleaned:
                sections.append(
                    IngestedSection(
                        text=cleaned,
                        heading=f"Page {i}",
                        level=2,
                        page=i,
                        metadata={"ocr": (i in ocr_used)},
                    )
                )

        title = (meta.get("title") or meta.get("Title")
                 or os.path.basename(location))

        out_meta = {
            k: v for k, v in (meta or {}).items()
            if isinstance(v, (str, int)) and k.lower() not in {"raw"}
        }
        if ocr_used:
            out_meta["ocr_pages"] = len(ocr_used)
            out_meta["ocr_page_list"] = ",".join(str(p) for p in ocr_used)

        return IngestedDocument(
            source_type="pdf",
            title=title,
            location=os.path.abspath(location),
            checksum=sha256_file(location),
            sections=sections,
            metadata=out_meta,
        )
