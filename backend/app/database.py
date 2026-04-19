from sqlalchemy import create_engine
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
import duckdb
from app.config import settings
import os

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
    """Get DuckDB connection for analytics queries."""
    return duckdb.connect(settings.duckdb_path)
