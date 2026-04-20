"""
PDF Watcher Service
Monitors configurable folders for new PDF files using watchdog.
Includes file hash deduplication and file lock detection.
"""

import hashlib
import json
import logging
import os
import time
from pathlib import Path
from typing import Callable, Dict, Optional, Set

from watchdog.events import FileCreatedEvent, FileMovedEvent, FileSystemEventHandler
from watchdog.observers import Observer

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# File lock detection
# ---------------------------------------------------------------------------

def is_file_ready(file_path: str) -> bool:
    """
    Try to open the file exclusively to check if it is still being written.

    Returns True if the file can be opened (ready to read), False if locked.
    """
    try:
        with open(file_path, "rb") as fh:
            # Attempt a small read to confirm the file is accessible
            fh.read(1)
        return True
    except (IOError, OSError):
        return False


def wait_for_file_ready(file_path: str, timeout: float = 10.0, poll_interval: float = 0.5) -> bool:
    """
    Poll until the file is ready or the timeout expires.

    Returns True if the file became ready within the timeout, False otherwise.
    """
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if is_file_ready(file_path):
            return True
        time.sleep(poll_interval)
    return False


# ---------------------------------------------------------------------------
# File hash deduplication
# ---------------------------------------------------------------------------

class FileHashTracker:
    """
    Tracks SHA-256 hashes of processed files to prevent duplicate processing.

    Hashes are stored in-memory and optionally persisted to a JSON file.
    """

    def __init__(self, persist_path: Optional[str] = None) -> None:
        self._seen: Set[str] = set()
        self._persist_path = persist_path
        if persist_path and os.path.exists(persist_path):
            self._load()

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def is_duplicate(self, file_path: str) -> bool:
        """Return True if this file's content hash has been seen before."""
        file_hash = self._compute_hash(file_path)
        return file_hash in self._seen

    def mark_seen(self, file_path: str) -> str:
        """Record the file's hash as seen. Returns the hash."""
        file_hash = self._compute_hash(file_path)
        self._seen.add(file_hash)
        if self._persist_path:
            self._save()
        return file_hash

    def reset(self) -> None:
        """Clear all tracked hashes (useful for testing)."""
        self._seen.clear()
        if self._persist_path and os.path.exists(self._persist_path):
            os.remove(self._persist_path)

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _compute_hash(file_path: str) -> str:
        sha256 = hashlib.sha256()
        with open(file_path, "rb") as fh:
            for chunk in iter(lambda: fh.read(65536), b""):
                sha256.update(chunk)
        return sha256.hexdigest()

    def _save(self) -> None:
        with open(self._persist_path, "w") as fh:  # type: ignore[arg-type]
            json.dump(list(self._seen), fh)

    def _load(self) -> None:
        with open(self._persist_path, "r") as fh:  # type: ignore[arg-type]
            data = json.load(fh)
        if isinstance(data, list):
            self._seen = set(data)


# ---------------------------------------------------------------------------
# Watchdog event handler
# ---------------------------------------------------------------------------

class _PDFEventHandler(FileSystemEventHandler):
    """Internal watchdog handler that delegates to PDFWatcher."""

    def __init__(self, watcher: "PDFWatcher") -> None:
        super().__init__()
        self._watcher = watcher

    def on_created(self, event: FileCreatedEvent) -> None:  # type: ignore[override]
        if not event.is_directory and event.src_path.lower().endswith(".pdf"):
            self._watcher._handle_new_pdf(event.src_path)

    def on_moved(self, event: FileMovedEvent) -> None:  # type: ignore[override]
        if not event.is_directory and event.dest_path.lower().endswith(".pdf"):
            self._watcher._handle_new_pdf(event.dest_path)


# ---------------------------------------------------------------------------
# PDFWatcher
# ---------------------------------------------------------------------------

class PDFWatcher:
    """
    Monitors one or more folders for new PDF files.

    When a new PDF is detected (created or moved into a watched folder):
      1. Waits up to 10 s for the file to be fully written (lock detection).
      2. Checks for duplicates via SHA-256 hash.
      3. Fires the on_new_pdf callback with the file path.

    Usage::

        def handle(path: str) -> None:
            print("New PDF:", path)

        watcher = PDFWatcher(watched_folders=["/tmp/charts"], on_new_pdf=handle)
        watcher.start()
        # ... later ...
        watcher.stop()
    """

    def __init__(
        self,
        watched_folders: Optional[list] = None,
        on_new_pdf: Optional[Callable[[str], None]] = None,
        hash_persist_path: Optional[str] = None,
    ) -> None:
        self._folders: Dict[str, Observer] = {}
        self._on_new_pdf = on_new_pdf
        self._hash_tracker = FileHashTracker(persist_path=hash_persist_path)
        self._running = False

        for folder in (watched_folders or []):
            self._register_folder(folder)

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def start(self) -> None:
        """Start all folder observers."""
        self._running = True
        for observer in self._folders.values():
            if not observer.is_alive():
                observer.start()
        logger.info("PDFWatcher started, watching %d folder(s)", len(self._folders))

    def stop(self) -> None:
        """Stop all folder observers."""
        self._running = False
        for observer in self._folders.values():
            if observer.is_alive():
                observer.stop()
                observer.join()
        logger.info("PDFWatcher stopped")

    def add_folder(self, path: str) -> None:
        """Add a new folder to watch (hot-add, no restart required)."""
        path = str(Path(path).resolve())
        if path in self._folders:
            logger.debug("Folder already watched: %s", path)
            return
        self._register_folder(path)
        if self._running:
            self._folders[path].start()
        logger.info("Added watched folder: %s", path)

    def remove_folder(self, path: str) -> None:
        """Remove a folder from watching."""
        path = str(Path(path).resolve())
        observer = self._folders.pop(path, None)
        if observer is None:
            logger.debug("Folder not watched: %s", path)
            return
        if observer.is_alive():
            observer.stop()
            observer.join()
        logger.info("Removed watched folder: %s", path)

    @property
    def watched_folders(self) -> list:
        return list(self._folders.keys())

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _register_folder(self, path: str) -> None:
        path = str(Path(path).resolve())
        observer = Observer()
        handler = _PDFEventHandler(self)
        observer.schedule(handler, path, recursive=False)
        self._folders[path] = observer

    def _handle_new_pdf(self, file_path: str) -> None:
        """Called by the event handler for every candidate PDF path."""
        logger.debug("Detected PDF: %s", file_path)

        # Wait for the file to be fully written
        if not wait_for_file_ready(file_path, timeout=10.0, poll_interval=0.5):
            logger.warning("File not ready after 10 s, skipping: %s", file_path)
            return

        # Deduplication check
        if self._hash_tracker.is_duplicate(file_path):
            logger.info("Duplicate PDF skipped: %s", file_path)
            return

        # Mark as seen before firing callback to avoid races
        self._hash_tracker.mark_seen(file_path)

        if self._on_new_pdf:
            try:
                self._on_new_pdf(file_path)
            except Exception:
                logger.exception("Error in on_new_pdf callback for %s", file_path)
