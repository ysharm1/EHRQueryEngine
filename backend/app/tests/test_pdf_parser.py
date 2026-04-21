"""
Tests for the enhanced PDF parser with per-page text extraction.
"""

import pytest
from unittest.mock import patch, MagicMock
from app.services.pdf_parser import (
    PageText,
    ParsedPDF,
    ParsedPDFWithPages,
    PDFParser,
    MIN_TEXT_LENGTH,
)


class TestPageText:
    def test_page_text_creation(self):
        pt = PageText(page_number=1, text="Hello world", char_count=11)
        assert pt.page_number == 1
        assert pt.text == "Hello world"
        assert pt.char_count == 11

    def test_page_text_empty(self):
        pt = PageText(page_number=3, text="", char_count=0)
        assert pt.page_number == 3
        assert pt.text == ""
        assert pt.char_count == 0


class TestParsedPDFWithPages:
    def test_inherits_parsed_pdf(self):
        result = ParsedPDFWithPages(
            raw_text="some text",
            page_count=1,
            is_scanned=False,
            extraction_method="pdfplumber",
            pages=[PageText(page_number=1, text="some text", char_count=9)],
        )
        assert isinstance(result, ParsedPDF)
        assert result.raw_text == "some text"
        assert result.page_count == 1
        assert result.extraction_method == "pdfplumber"
        assert len(result.pages) == 1

    def test_default_pages_empty(self):
        result = ParsedPDFWithPages(
            raw_text="", page_count=0, is_scanned=False,
            extraction_method="failed",
        )
        assert result.pages == []

    def test_backward_compat_raw_text(self):
        pages = [
            PageText(page_number=1, text="Page one", char_count=8),
            PageText(page_number=2, text="Page two", char_count=8),
        ]
        result = ParsedPDFWithPages(
            raw_text="Page one\nPage two",
            page_count=2,
            is_scanned=False,
            extraction_method="pdfplumber",
            pages=pages,
        )
        assert "Page one" in result.raw_text
        assert "Page two" in result.raw_text


class TestPDFParserExtractText:
    def test_file_not_found_returns_parsed_pdf_with_pages(self):
        parser = PDFParser()
        result = parser.extract_text("/nonexistent/file.pdf")
        assert isinstance(result, ParsedPDFWithPages)
        assert result.extraction_method == "failed"
        assert result.pages == []
        assert "File not found" in result.error

    def test_pdfplumber_builds_page_text_objects(self):
        """Test that _extract_with_pdfplumber creates 1-indexed PageText objects."""
        parser = PDFParser(ocr_enabled=False)

        # Create mock pages
        mock_page1 = MagicMock()
        mock_page1.extract_text.return_value = "A" * 60  # above MIN_TEXT_LENGTH
        mock_page2 = MagicMock()
        mock_page2.extract_text.return_value = "B" * 40

        mock_pdf = MagicMock()
        mock_pdf.pages = [mock_page1, mock_page2]
        mock_pdf.__enter__ = MagicMock(return_value=mock_pdf)
        mock_pdf.__exit__ = MagicMock(return_value=False)

        mock_pdfplumber = MagicMock()
        mock_pdfplumber.open.return_value = mock_pdf

        import sys
        sys.modules["pdfplumber"] = mock_pdfplumber
        try:
            result = parser._extract_with_pdfplumber("/fake/file.pdf")
        finally:
            del sys.modules["pdfplumber"]

        assert isinstance(result, ParsedPDFWithPages)
        assert len(result.pages) == 2
        # 1-indexed page numbers
        assert result.pages[0].page_number == 1
        assert result.pages[1].page_number == 2
        assert result.pages[0].text == "A" * 60
        assert result.pages[0].char_count == 60
        assert result.pages[1].text == "B" * 40
        assert result.pages[1].char_count == 40
        # raw_text is still the concatenation
        assert result.raw_text == ("A" * 60) + "\n" + ("B" * 40)

    def test_pdfplumber_failed_page_gets_empty_text(self):
        """When a page extraction fails, PageText should have empty text."""
        parser = PDFParser(ocr_enabled=False)

        mock_page = MagicMock()
        mock_page.extract_text.side_effect = Exception("corrupt page")

        mock_pdf = MagicMock()
        mock_pdf.pages = [mock_page]
        mock_pdf.__enter__ = MagicMock(return_value=mock_pdf)
        mock_pdf.__exit__ = MagicMock(return_value=False)

        mock_pdfplumber = MagicMock()
        mock_pdfplumber.open.return_value = mock_pdf

        import sys
        sys.modules["pdfplumber"] = mock_pdfplumber
        try:
            result = parser._extract_with_pdfplumber("/fake/file.pdf")
        finally:
            del sys.modules["pdfplumber"]

        assert len(result.pages) == 1
        assert result.pages[0].page_number == 1
        assert result.pages[0].text == ""
        assert result.pages[0].char_count == 0

    def test_pdfplumber_corrupt_pdf_returns_empty_pages(self):
        """When pdfplumber.open fails, return empty pages list."""
        parser = PDFParser(ocr_enabled=False)

        mock_pdfplumber = MagicMock()
        mock_pdfplumber.open.side_effect = Exception("corrupt PDF")

        import sys
        sys.modules["pdfplumber"] = mock_pdfplumber
        try:
            result = parser._extract_with_pdfplumber("/fake/file.pdf")
        finally:
            del sys.modules["pdfplumber"]

        assert isinstance(result, ParsedPDFWithPages)
        assert result.pages == []
        assert result.extraction_method == "failed"

    def test_extract_text_returns_parsed_pdf_with_pages_type(self):
        """extract_text always returns ParsedPDFWithPages, even on error."""
        parser = PDFParser()
        result = parser.extract_text("/nonexistent.pdf")
        assert isinstance(result, ParsedPDFWithPages)
        assert hasattr(result, "pages")
        # Still backward compatible as ParsedPDF
        assert isinstance(result, ParsedPDF)
        assert hasattr(result, "raw_text")
