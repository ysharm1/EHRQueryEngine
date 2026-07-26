from sqlalchemy import create_engine
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
import duckdb
from app.config import settings
import os
from pathlib import Path

# SQLite for metadata (switch to PostgreSQL for production).
# Store the metadata DB on the SAME persistent volume as the DuckDB warehouse
# so dataset records survive restarts/redeploys. On Render the DuckDB path is
# the persistent disk (e.g. /opt/render/project/data). Fall back to /tmp only
# if the persistent location is not writable.
def _resolve_data_dir() -> str:
    """Return a writable directory for the metadata DB, preferring the
    persistent volume that holds the DuckDB warehouse."""
    candidate = Path(settings.duckdb_path).parent
    try:
        candidate.mkdir(parents=True, exist_ok=True)
        # Verify writability
        test_file = candidate / ".write_test"
        test_file.touch()
        test_file.unlink()
        return str(candidate)
    except (OSError, PermissionError):
        fallback = Path("/tmp/data")
        fallback.mkdir(parents=True, exist_ok=True)
        return str(fallback)


DATA_DIR = _resolve_data_dir()
SQLITE_URL = f"sqlite:///{DATA_DIR}/metadata.db"

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


# Directory for generated query result exports (CSV, etc.). Lives on the
# persistent volume so downloads remain available after restarts.
def get_exports_dir() -> Path:
    exports = Path(DATA_DIR) / "exports"
    try:
        exports.mkdir(parents=True, exist_ok=True)
        return exports
    except (OSError, PermissionError):
        fallback = Path("/tmp/exports")
        fallback.mkdir(parents=True, exist_ok=True)
        return fallback
