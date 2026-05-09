from sqlalchemy import create_engine
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
import duckdb
from app.config import settings
import os
from pathlib import Path

# Use SQLite for demo (switch to PostgreSQL for production)
# Use /tmp for writable storage on Render free tier
os.makedirs("/tmp/data", exist_ok=True)
SQLITE_URL = "sqlite:////tmp/data/metadata.db"

# SQLite for metadata (use PostgreSQL in production)
engine = create_engine(SQLITE_URL, connect_args={"check_same_thread": False}, pool_pre_ping=True)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()


def get_db():
    """Dependency for getting database session."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


# DuckDB for analytics warehouse
def get_duckdb_connection():
    """Get DuckDB connection for analytics queries.

    Ensures the parent directory exists before opening the database file.
    """
    duckdb_path = settings.duckdb_path
    parent = Path(duckdb_path).parent
    if str(parent) and str(parent) != ".":
        try:
            parent.mkdir(parents=True, exist_ok=True)
        except (OSError, PermissionError):
            # If we can't create the configured path (e.g. read-only disk),
            # fall back to /tmp so the app still runs.
            fallback = "/tmp/warehouse.duckdb"
            os.makedirs("/tmp", exist_ok=True)
            duckdb_path = fallback
    return duckdb.connect(duckdb_path)
