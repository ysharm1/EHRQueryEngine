"""
Property-based tests for PDF Watcher duplicate prevention.

**Validates: Requirements P-2**
P-2: Processing the same PDF file twice MUST NOT create duplicate hash entries.
"""

import os
import tempfile

import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

from app.services.pdf_watcher import FileHashTracker, is_file_ready


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _write_temp_pdf(content: bytes) -> str:
    """Write bytes to a temp file and return its path."""
    fd, path = tempfile.mkstemp(suffix=".pdf")
    try:
        os.write(fd, content)
    finally:
        os.close(fd)
    return path


# ---------------------------------------------------------------------------
# Unit tests
# ---------------------------------------------------------------------------

class TestFileHashTrackerUnit:
    def test_new_file_is_not_duplicate(self, tmp_path):
        path = tmp_path / "a.pdf"
        path.write_bytes(b"unique content abc")
        tracker = FileHashTracker()
        assert tracker.is_duplicate(str(path)) is False

    def test_after_mark_seen_is_duplicate(self, tmp_path):
        path = tmp_path / "b.pdf"
        path.write_bytes(b"some pdf bytes")
        tracker = FileHashTracker()
        tracker.mark_seen(str(path))
        assert tracker.is_duplicate(str(path)) is True

    def test_different_content_not_duplicate(self, tmp_path):
        p1 = tmp_path / "c1.pdf"
        p2 = tmp_path / "c2.pdf"
        p1.write_bytes(b"content one")
        p2.write_bytes(b"content two")
        tracker = FileHashTracker()
        tracker.mark_seen(str(p1))
        assert tracker.is_duplicate(str(p2)) is False

    def test_same_content_different_filename_is_duplicate(self, tmp_path):
        p1 = tmp_path / "d1.pdf"
        p2 = tmp_path / "d2.pdf"
        data = b"identical bytes"
        p1.write_bytes(data)
        p2.write_bytes(data)
        tracker = FileHashTracker()
        tracker.mark_seen(str(p1))
        assert tracker.is_duplicate(str(p2)) is True

    def test_persistence_across_instances(self, tmp_path):
        persist = str(tmp_path / "hashes.json")
        path = tmp_path / "e.pdf"
        path.write_bytes(b"persistent content")

        tracker1 = FileHashTracker(persist_path=persist)
        tracker1.mark_seen(str(path))

        tracker2 = FileHashTracker(persist_path=persist)
        assert tracker2.is_duplicate(str(path)) is True

    def test_reset_clears_hashes(self, tmp_path):
        path = tmp_path / "f.pdf"
        path.write_bytes(b"reset test")
        tracker = FileHashTracker()
        tracker.mark_seen(str(path))
        tracker.reset()
        assert tracker.is_duplicate(str(path)) is False


class TestIsFileReady:
    def test_existing_file_is_ready(self, tmp_path):
        path = tmp_path / "ready.pdf"
        path.write_bytes(b"data")
        assert is_file_ready(str(path)) is True

    def test_nonexistent_file_is_not_ready(self, tmp_path):
        path = str(tmp_path / "missing.pdf")
        assert is_file_ready(path) is False


# ---------------------------------------------------------------------------
# Property-based tests  (P-2)
# ---------------------------------------------------------------------------

class TestDuplicatePreventionProperty:
    """
    **Validates: Requirements P-2**

    Processing the same PDF file twice MUST NOT create duplicate hash entries.
    """

    @given(content=st.binary(min_size=1, max_size=4096))
    @settings(max_examples=100)
    def test_same_content_never_duplicates_hash_set(self, content: bytes):
        """
        For any file content, calling mark_seen twice must not grow the
        internal hash set beyond a single entry for that content.
        """
        path = _write_temp_pdf(content)
        try:
            tracker = FileHashTracker()
            tracker.mark_seen(path)
            size_after_first = len(tracker._seen)

            tracker.mark_seen(path)
            size_after_second = len(tracker._seen)

            assert size_after_second == size_after_first, (
                "Hash set grew after marking the same file a second time"
            )
        finally:
            os.unlink(path)

    @given(content=st.binary(min_size=1, max_size=4096))
    @settings(max_examples=100)
    def test_is_duplicate_true_on_second_call(self, content: bytes):
        """
        For any file content, is_duplicate must return True after the file
        has been marked seen once.
        """
        path = _write_temp_pdf(content)
        try:
            tracker = FileHashTracker()
            assert tracker.is_duplicate(path) is False, "Should not be duplicate before mark_seen"
            tracker.mark_seen(path)
            assert tracker.is_duplicate(path) is True, "Should be duplicate after mark_seen"
        finally:
            os.unlink(path)

    @given(
        content_a=st.binary(min_size=1, max_size=4096),
        content_b=st.binary(min_size=1, max_size=4096),
    )
    @settings(max_examples=100)
    def test_different_content_not_flagged_as_duplicate(
        self, content_a: bytes, content_b: bytes
    ):
        """
        For any two files with different content, marking one seen must not
        cause the other to be flagged as a duplicate.
        """
        if content_a == content_b:
            return  # Skip equal-content pairs — they ARE duplicates by design

        path_a = _write_temp_pdf(content_a)
        path_b = _write_temp_pdf(content_b)
        try:
            tracker = FileHashTracker()
            tracker.mark_seen(path_a)
            assert tracker.is_duplicate(path_b) is False, (
                "Different content incorrectly flagged as duplicate"
            )
        finally:
            os.unlink(path_a)
            os.unlink(path_b)
