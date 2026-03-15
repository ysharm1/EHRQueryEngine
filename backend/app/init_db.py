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
    
    # Create additional indexes for query optimization
    logger.info("Creating indexes...")
    
    # Indexes are already defined in the models via index=True
    # Additional composite indexes can be added here if needed
    
    logger.info("Indexes created successfully")
    
    return True


def create_sample_data():
    """
    Create sample data for testing.
    
    Implements Requirement 23.3
    """
    from sqlalchemy.orm import Session
    from datetime import date, datetime
    import uuid
    
    logger.info("Creating sample data...")
    
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
        
        # Create sample subjects
        existing_subjects = db.query(Subject).count()
        if existing_subjects == 0:
            subjects = [
                Subject(
                    subject_id="SUBJ001",
                    date_of_birth=date(1960, 5, 15),
                    sex="M",
                    diagnosis_codes=["G20", "I10"],  # Parkinson's, Hypertension
                    study_group="Treatment",
                    enrollment_date=date(2020, 1, 10)
                ),
                Subject(
                    subject_id="SUBJ002",
                    date_of_birth=date(1955, 8, 22),
                    sex="F",
                    diagnosis_codes=["G20", "E11"],  # Parkinson's, Diabetes
                    study_group="Treatment",
                    enrollment_date=date(2020, 2, 15)
                ),
                Subject(
                    subject_id="SUBJ003",
                    date_of_birth=date(1965, 3, 10),
                    sex="M",
                    diagnosis_codes=["G20"],  # Parkinson's
                    study_group="Control",
                    enrollment_date=date(2020, 3, 20)
                ),
                Subject(
                    subject_id="SUBJ004",
                    date_of_birth=date(1958, 11, 5),
                    sex="F",
                    diagnosis_codes=["G20", "I10", "E11"],  # Parkinson's, Hypertension, Diabetes
                    study_group="Treatment",
                    enrollment_date=date(2020, 4, 12)
                ),
                Subject(
                    subject_id="SUBJ005",
                    date_of_birth=date(1962, 7, 18),
                    sex="M",
                    diagnosis_codes=["G20"],  # Parkinson's
                    study_group="Control",
                    enrollment_date=date(2020, 5, 8)
                )
            ]
            
            for subject in subjects:
                db.add(subject)
            
            logger.info(f"Created {len(subjects)} sample subjects")
        
        # Create sample procedures
        existing_procedures = db.query(Procedure).count()
        if existing_procedures == 0:
            procedures = [
                Procedure(
                    procedure_id="PROC001",
                    subject_id="SUBJ001",
                    procedure_code="61867",  # DBS surgery
                    procedure_name="Deep Brain Stimulation",
                    procedure_date=date(2020, 6, 15),
                    performed_by="Dr. Smith"
                ),
                Procedure(
                    procedure_id="PROC002",
                    subject_id="SUBJ002",
                    procedure_code="61867",  # DBS surgery
                    procedure_name="Deep Brain Stimulation",
                    procedure_date=date(2020, 7, 20),
                    performed_by="Dr. Smith"
                ),
                Procedure(
                    procedure_id="PROC003",
                    subject_id="SUBJ004",
                    procedure_code="61867",  # DBS surgery
                    procedure_name="Deep Brain Stimulation",
                    procedure_date=date(2020, 8, 10),
                    performed_by="Dr. Jones"
                )
            ]
            
            for procedure in procedures:
                db.add(procedure)
            
            logger.info(f"Created {len(procedures)} sample procedures")
        
        # Create sample observations
        existing_observations = db.query(Observation).count()
        if existing_observations == 0:
            observations = [
                Observation(
                    observation_id="OBS001",
                    subject_id="SUBJ001",
                    observation_type="8310-5",  # Body temperature
                    observation_value="98.6",
                    observation_unit="F",
                    observation_date=datetime(2020, 6, 15, 10, 30)
                ),
                Observation(
                    observation_id="OBS002",
                    subject_id="SUBJ001",
                    observation_type="8867-4",  # Heart rate
                    observation_value="72",
                    observation_unit="bpm",
                    observation_date=datetime(2020, 6, 15, 10, 30)
                ),
                Observation(
                    observation_id="OBS003",
                    subject_id="SUBJ002",
                    observation_type="8310-5",  # Body temperature
                    observation_value="98.4",
                    observation_unit="F",
                    observation_date=datetime(2020, 7, 20, 9, 15)
                ),
                Observation(
                    observation_id="OBS004",
                    subject_id="SUBJ002",
                    observation_type="8867-4",  # Heart rate
                    observation_value="68",
                    observation_unit="bpm",
                    observation_date=datetime(2020, 7, 20, 9, 15)
                )
            ]
            
            for observation in observations:
                db.add(observation)
            
            logger.info(f"Created {len(observations)} sample observations")
        
        # Create sample imaging features
        existing_imaging = db.query(ImagingFeature).count()
        if existing_imaging == 0:
            imaging_features = [
                ImagingFeature(
                    imaging_id="IMG001",
                    subject_id="SUBJ001",
                    study_date=date(2020, 6, 10),
                    modality="MRI",
                    features={
                        "brain_volume": 1200.5,
                        "ventricle_volume": 45.2,
                        "hippocampus_volume": 3.8
                    },
                    study_description="Pre-operative MRI"
                ),
                ImagingFeature(
                    imaging_id="IMG002",
                    subject_id="SUBJ002",
                    study_date=date(2020, 7, 15),
                    modality="MRI",
                    features={
                        "brain_volume": 1180.3,
                        "ventricle_volume": 48.5,
                        "hippocampus_volume": 3.6
                    },
                    study_description="Pre-operative MRI"
                )
            ]
            
            for imaging in imaging_features:
                db.add(imaging)
            
            logger.info(f"Created {len(imaging_features)} sample imaging features")
        
        db.commit()
        logger.info("Sample data created successfully")
        
    except Exception as e:
        logger.error(f"Error creating sample data: {e}")
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
