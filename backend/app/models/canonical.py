from sqlalchemy import Column, String, Date, DateTime, ForeignKey, JSON, Float, Enum as SQLEnum
from sqlalchemy.orm import relationship
from app.database import Base
import enum


class Sex(str, enum.Enum):
    """Sex enum for subjects."""
    MALE = "M"
    FEMALE = "F"
    OTHER = "O"


class ImagingModality(str, enum.Enum):
    """Imaging modality types."""
    MRI = "MRI"
    CT = "CT"
    PET = "PET"
    ULTRASOUND = "Ultrasound"
    XRAY = "XRay"


class Subject(Base):
    """
    Canonical subject/patient model.
    
    Validation rules:
    - subject_id must be non-empty
    - sex must be M, F, O, or null
    - diagnosis_codes must be valid ICD-10 or SNOMED codes
    - date_of_birth must be valid ISO 8601 date if present
    - enrollment_date must be after date_of_birth if both present
    """
    __tablename__ = "subjects"
    
    subject_id = Column(String, primary_key=True, index=True)
    date_of_birth = Column(Date, nullable=True)
    sex = Column(SQLEnum(Sex), nullable=True)
    diagnosis_codes = Column(JSON, nullable=False, default=list)  # List of ICD-10/SNOMED codes
    study_group = Column(String, nullable=True)
    enrollment_date = Column(Date, nullable=True)
    
    # Relationships
    procedures = relationship("Procedure", back_populates="subject", cascade="all, delete-orphan")
    observations = relationship("Observation", back_populates="subject", cascade="all, delete-orphan")
    imaging_features = relationship("ImagingFeature", back_populates="subject", cascade="all, delete-orphan")


class Procedure(Base):
    """
    Canonical procedure model.
    
    Validation rules:
    - procedure_id must be unique
    - subject_id must reference valid subject
    - procedure_code must be valid CPT or SNOMED code
    - procedure_date must be valid ISO 8601 date
    - procedure_date must be after subject's date_of_birth
    """
    __tablename__ = "procedures"
    
    procedure_id = Column(String, primary_key=True, index=True)
    subject_id = Column(String, ForeignKey("subjects.subject_id", ondelete="CASCADE"), nullable=False, index=True)
    procedure_code = Column(String, nullable=False, index=True)
    procedure_name = Column(String, nullable=False)
    procedure_date = Column(Date, nullable=False, index=True)
    performed_by = Column(String, nullable=True)
    
    # Relationship
    subject = relationship("Subject", back_populates="procedures")


class Observation(Base):
    """
    Canonical observation model.
    
    Validation rules:
    - observation_id must be unique
    - subject_id must reference valid subject
    - observation_type must be valid LOINC code
    - observation_value must match expected type for observation_type
    - observation_unit required for numeric observations
    - observation_date must be valid ISO 8601 timestamp
    """
    __tablename__ = "observations"
    
    observation_id = Column(String, primary_key=True, index=True)
    subject_id = Column(String, ForeignKey("subjects.subject_id", ondelete="CASCADE"), nullable=False, index=True)
    observation_type = Column(String, nullable=False, index=True)  # LOINC code
    observation_value = Column(String, nullable=False)
    observation_unit = Column(String, nullable=True)
    observation_date = Column(DateTime, nullable=False, index=True)
    
    # Relationship
    subject = relationship("Subject", back_populates="observations")


class ImagingFeature(Base):
    """
    Canonical imaging feature model.
    
    Validation rules:
    - imaging_id must be unique
    - subject_id must reference valid subject
    - study_date must be valid ISO 8601 date
    - modality must be one of supported types
    - features must be non-empty list of name-value pairs
    - feature values must be valid floats
    """
    __tablename__ = "imaging_features"
    
    imaging_id = Column(String, primary_key=True, index=True)
    subject_id = Column(String, ForeignKey("subjects.subject_id", ondelete="CASCADE"), nullable=False, index=True)
    study_date = Column(Date, nullable=False, index=True)
    modality = Column(SQLEnum(ImagingModality), nullable=False)
    features = Column(JSON, nullable=False)  # Dict of feature_name: value pairs
    study_description = Column(String, nullable=True)
    
    # Relationship
    subject = relationship("Subject", back_populates="imaging_features")
