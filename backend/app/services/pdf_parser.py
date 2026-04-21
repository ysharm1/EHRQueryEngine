"""
PDF Parser Service
Extracts text from PDF files using pdfplumber (digital) or Tesseract OCR (scanned).
"""

import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)

MIN_TEXT_LENGTH = 50  # chars below which we consider a PDF "scanned"


@dataclass
class ParsedPDF:
    raw_text: str
    page_count: int
    is_scanned: bool
    extraction_method: str  # "pdfplumber" | "ocr" | "failed"
    error: Optional[str] = None


@dataclass
class PageText:
    page_number: int  # 1-indexed
    text: str
    char_count: int


@dataclass
class ParsedPDFWithPages(ParsedPDF):
    pages: list[PageText] = field(default_factory=list)


class PDFParser:
    """
    Extracts raw text from PDF files.
    - Digital PDFs: pdfplumber
    - Scanned PDFs: pdf2image + pytesseract OCR
    """

    def __init__(self, ocr_enabled: bool = True, max_pages: int = 200) -> None:
        self.ocr_enabled = ocr_enabled
        self.max_pages = max_pages

    def extract_text(self, file_path: str) -> ParsedPDFWithPages:
        """Main entry point. Returns a ParsedPDFWithPages with per-page text and metadata.

        Backward compatible — raw_text is still available as a concatenated string.
        """
        path = Path(file_path)
        if not path.exists():
            return ParsedPDFWithPages(
                raw_text="", page_count=0, is_scanned=False,
                extraction_method="failed", error=f"File not found: {file_path}",
                pages=[],
            )

        try:
            result = self._extract_with_pdfplumber(file_path)
            if len(result.raw_text.strip()) >= MIN_TEXT_LENGTH:
                return result
            # Text too short — likely scanned
            if self.ocr_enabled:
                logger.info("PDF appears scanned, attempting OCR: %s", file_path)
                ocr_result = self._extract_with_ocr(file_path, result.page_count)
                return ocr_result
            return result
        except Exception as exc:
            logger.exception("PDF extraction failed for %s", file_path)
            return ParsedPDFWithPages(
                raw_text="", page_count=0, is_scanned=False,
                extraction_method="failed", error=str(exc),
                pages=[],
            )

    def is_scanned(self, file_path: str) -> bool:
        """Quick check: returns True if the PDF has no extractable text."""
        result = self._extract_with_pdfplumber(file_path)
        return len(result.raw_text.strip()) < MIN_TEXT_LENGTH

    # ------------------------------------------------------------------
    # Internal methods
    # ------------------------------------------------------------------

    def _extract_with_pdfplumber(self, file_path: str) -> ParsedPDFWithPages:
        import pdfplumber  # lazy import

        pages_text: list[str] = []
        page_objects: list[PageText] = []
        page_count = 0
        try:
            with pdfplumber.open(file_path) as pdf:
                page_count = len(pdf.pages)
                for i, page in enumerate(pdf.pages[: self.max_pages]):
                    try:
                        text = page.extract_text() or ""
                    except Exception as exc:
                        logger.warning("Failed to extract page %d: %s", i, exc)
                        text = ""
                    pages_text.append(text)
                    page_objects.append(PageText(
                        page_number=i + 1,
                        text=text,
                        char_count=len(text),
                    ))
        except Exception as exc:
            # Password-protected or corrupt
            logger.warning("pdfplumber failed for %s: %s", file_path, exc)
            return ParsedPDFWithPages(
                raw_text="", page_count=0, is_scanned=False,
                extraction_method="failed", error=str(exc),
                pages=[],
            )

        raw_text = "\n".join(pages_text)
        return ParsedPDFWithPages(
            raw_text=raw_text,
            page_count=page_count,
            is_scanned=len(raw_text.strip()) < MIN_TEXT_LENGTH,
            extraction_method="pdfplumber",
            pages=page_objects,
        )

    def _extract_with_ocr(self, file_path: str, page_count: int) -> ParsedPDFWithPages:
        try:
            from pdf2image import convert_from_path  # lazy import
            import pytesseract  # lazy import
        except ImportError as exc:
            logger.warning("OCR dependencies not installed: %s", exc)
            return ParsedPDFWithPages(
                raw_text="", page_count=page_count, is_scanned=True,
                extraction_method="failed",
                error="OCR dependencies not installed (pdf2image, pytesseract)",
                pages=[],
            )

        pages_text: list[str] = []
        page_objects: list[PageText] = []
        images = []
        try:
            images = convert_from_path(file_path, last_page=self.max_pages)
            for i, img in enumerate(images):
                try:
                    text = pytesseract.image_to_string(img)
                except Exception as exc:
                    logger.warning("OCR failed on page %d: %s", i, exc)
                    text = ""
                pages_text.append(text)
                page_objects.append(PageText(
                    page_number=i + 1,
                    text=text,
                    char_count=len(text),
                ))
        except Exception as exc:
            logger.exception("pdf2image conversion failed for %s", file_path)
            return ParsedPDFWithPages(
                raw_text="", page_count=page_count, is_scanned=True,
                extraction_method="failed", error=str(exc),
                pages=[],
            )

        return ParsedPDFWithPages(
            raw_text="\n".join(pages_text),
            page_count=len(images),
            is_scanned=True,
            extraction_method="ocr",
            pages=page_objects,
        )
