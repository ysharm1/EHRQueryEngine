#!/usr/bin/env python3
"""
Standalone PDF Watcher for hospital laptop deployment.
Runs as a background service that monitors folders and processes PDFs.
"""

import json
import logging
import os
import sys
import time
from pathlib import Path

# Add current directory to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app.services.pdf_watcher import PDFWatcher
from app.services.extraction_manager import ExtractionManager
from app.database import get_duckdb_connection

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

CONFIG_PATH = os.environ.get("EXTRACTION_CONFIG_PATH", "extraction_config.json")

def load_config():
    """Load extraction configuration."""
    if Path(CONFIG_PATH).exists():
        with open(CONFIG_PATH) as f:
            return json.load(f)
    return {
        "watched_folders": [],
        "llm_provider": "openai",
        "ocr_enabled": True,
        "auto_process": True,
        "extraction_hints": {},
        "sync": {"mode": "local_only", "cloud_endpoint": None},
        "retention_days": 90
    }

def main():
    """Main entry point for standalone watcher."""
    print("=" * 60)
    print("EHR PDF Extraction Watcher")
    print("=" * 60)
    
    config = load_config()
    watched_folders = config.get("watched_folders", [])
    
    if not watched_folders:
        print("ERROR: No watched folders configured.")
        print(f"Please edit {CONFIG_PATH} and add at least one folder to watch.")
        print("Example: {\"watched_folders\": [\"C:/Hospital/Exports/\"]}")
        return 1
    
    print(f"Watching {len(watched_folders)} folder(s):")
    for folder in watched_folders:
        print(f"  - {folder}")
    
    print("\nStarting watcher... (Press Ctrl+C to stop)")
    print("-" * 60)
    
    # Get database connection
    conn = get_duckdb_connection()
    
    # Create extraction manager
    manager = ExtractionManager(duckdb_conn=conn)
    
    # Create and start watcher
    watcher = PDFWatcher(
        watched_folders=watched_folders,
        on_new_pdf=lambda file_path: process_pdf(file_path, manager)
    )
    
    try:
        watcher.start()
        
        # Keep running until interrupted
        while True:
            time.sleep(1)
            
    except KeyboardInterrupt:
        print("\nStopping watcher...")
        watcher.stop()
        conn.close()
        print("Watcher stopped.")
        return 0
    except Exception as e:
        logger.error(f"Watcher error: {e}")
        watcher.stop()
        conn.close()
        return 1

def process_pdf(file_path: str, manager):
    """Process a new PDF file."""
    try:
        print(f"\n[+] New PDF detected: {Path(file_path).name}")
        job = manager.process_pdf(file_path)
        print(f"    Job ID: {job.job_id}")
        print(f"    Status: {job.status}")
        
        if job.status == "completed":
            print(f"    Records extracted: {job.records_extracted}")
            print(f"    Confidence: {job.confidence:.1%}")
        elif job.status == "failed":
            print(f"    Error: {job.error_message}")
            
    except Exception as e:
        logger.error(f"Failed to process PDF {file_path}: {e}")

if __name__ == "__main__":
    sys.exit(main())