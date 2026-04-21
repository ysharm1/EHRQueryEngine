"""
Database Initialization Script

Creates database tables and indexes for the Research Dataset Builder.
Implements Requirements 17.1, 17.5.
"""

from sqlalchemy import create_engine, Index
from sqlalchemy.orm import sessionmaker
from app.database import Base, engine
from app.models.canonical import Subject, Procedure, Observation, ImagingFeature
from app.models.metadata import DatasetMetadata, QueryProvenance, AuditLog, SchemaMapping
from app.models.user import User
import logging


logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def init_database():
    """
    Initialize database with tables and indexes.
    
    Implements Requirements 17.1, 17.5
    """
    logger.info("Creating database tables...")
    
    # Create all tables
    Base.metadata.create_all(bind=engine)
    
    logger.info("Database tables created successfully")

    # Initialize DuckDB extraction tables
    from app.database import get_duckdb_connection
    from app.services.extraction_schema import init_extraction_tables
    try:
        duckdb_conn = get_duckdb_connection()
        init_extraction_tables(duckdb_conn)

        # Run Clinical Query Intelligence schema migration (idempotent)
        from app.services.schema_migration import run_clinical_schema_migration
        run_clinical_schema_migration(duckdb_conn)

        duckdb_conn.close()
        logger.info("DuckDB extraction tables initialized")
    except Exception as e:
        logger.warning(f"Could not initialize DuckDB extraction tables: {e}")

    # Create additional indexes for query optimization
    logger.info("Creating indexes...")
    
    # Indexes are already defined in the models via index=True
    # Additional composite indexes can be added here if needed
    
    logger.info("Indexes created successfully")
    
    return True


def create_sample_data():
    """
    Create sample users for authentication.
    
    Implements Requirement 23.3
    """
    from sqlalchemy.orm import Session
    from datetime import date, datetime
    import uuid
    
    logger.info("Creating sample users...")
    
    # Create session
    SessionLocal = sessionmaker(bind=engine)
    db = SessionLocal()
    
    try:
        # Create sample users
        from app.services.auth import AuthService
        
        # Check if users already exist
        existing_user = db.query(User).filter(User.username == "admin").first()
        if not existing_user:
            admin_user = User(
                id=str(uuid.uuid4()),
                username="admin",
                email="admin@example.com",
                hashed_password=AuthService.get_password_hash("admin123"),
                role="Admin"
            )
            db.add(admin_user)
            logger.info("Created admin user")
        
        existing_researcher = db.query(User).filter(User.username == "researcher").first()
        if not existing_researcher:
            researcher_user = User(
                id=str(uuid.uuid4()),
                username="researcher",
                email="researcher@example.com",
                hashed_password=AuthService.get_password_hash("researcher123"),
                role="Researcher"
            )
            db.add(researcher_user)
            logger.info("Created researcher user")
        
        db.commit()
        logger.info("Sample users created successfully")
        
    except Exception as e:
        logger.error(f"Error creating sample users: {e}")
        db.rollback()
        raise
    
    finally:
        db.close()


def migrate_passwords():
    """
    Re-hash any legacy SHA-256 passwords to bcrypt.

    SHA-256 hashes are 64 hex chars. bcrypt hashes start with '$2b$'.
    Because we can't reverse the SHA-256 hash to recover the original
    plaintext, any demo user with a legacy hash is deleted and re-created
    with a fresh bcrypt hash from the known default password.
    """
    from app.services.auth import AuthService

    # Map of demo usernames → their known default passwords.
    # Only these accounts are auto-migrated; real users must reset manually.
    DEMO_ACCOUNTS = {
        "admin": "admin123",
        "researcher": "researcher123",
    }

    logger.info("Checking for legacy SHA-256 password hashes...")
    SessionLocal2 = sessionmaker(bind=engine)
    db = SessionLocal2()
    migrated = 0
    try:
        users = db.query(User).all()
        for user in users:
            h = user.hashed_password or ""
            if h.startswith("$2"):
                continue  # already bcrypt — nothing to do

            if user.username in DEMO_ACCOUNTS:
                # Re-hash from the known plaintext password
                user.hashed_password = AuthService.get_password_hash(
                    DEMO_ACCOUNTS[user.username]
                )
                migrated += 1
                logger.info(f"  Re-hashed password for demo user '{user.username}'")
            else:
                logger.warning(
                    f"  User '{user.username}' has a legacy hash but is not a "
                    "known demo account — manual password reset required."
                )

        if migrated:
            db.commit()
            logger.info(f"Migrated {migrated} demo user password(s) to bcrypt.")
        else:
            logger.info("All passwords already use bcrypt.")
    except Exception as e:
        logger.error(f"Password migration error: {e}")
        db.rollback()
    finally:
        db.close()


if __name__ == "__main__":
    logger.info("Initializing Research Dataset Builder database...")

    # Initialize database
    init_database()

    # Create sample data
    create_sample_data()

    # Migrate any legacy SHA-256 hashes to bcrypt
    migrate_passwords()

    logger.info("Database initialization complete!")
