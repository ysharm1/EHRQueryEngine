from sqlalchemy import Column, String, Integer, DateTime, JSON, Text, ForeignKey, Enum as SQLEnum
from sqlalchemy.sql import func
from sqlalchemy.orm import relationship
from app.database import Base
import enum


class ExportFormat(str, enum.Enum):
    """Export format types."""
    CSV = "CSV"
    PARQUET = "Parquet"
    JSON = "JSON"


class DatasetMetadata(Base):
    """
    Dataset metadata model for tracking generated datasets.
    
    Stores information about datasets including row/column counts,
    data sources, and creation details.
    """
    __tablename__ = "dataset_metadata"
    
    dataset_id = Column(String, primary_key=True, index=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    created_by = Column(String, ForeignKey("users.id"), nullable=False, index=True)
    row_count = Column(Integer, nullable=False)
    column_count = Column(Integer, nullable=False)
    data_sources = Column(JSON, nullable=False)  # List of data source names
    export_format = Column(SQLEnum(ExportFormat), nullable=False)
    file_paths = Column(JSON, nullable=False)  # List of generated file paths
    
    # Relationships
    provenance = relationship("QueryProvenance", back_populates="dataset", uselist=False, cascade="all, delete-orphan")


class QueryProvenance(Base):
    """
    Query provenance model for reproducibility.
    
    Stores complete information about how a dataset was generated,
    including the original query, parsed intent, and executed SQL.
    """
    __tablename__ = "query_provenance"
    
    provenance_id = Column(String, primary_key=True, index=True)
    dataset_id = Column(String, ForeignKey("dataset_metadata.dataset_id", ondelete="CASCADE"), nullable=False, unique=True, index=True)
    original_query = Column(Text, nullable=False)  # Natural language query
    parsed_intent = Column(JSON, nullable=False)  # Structured ParsedIntent
    sql_executed = Column(Text, nullable=False)  # Actual SQL query executed
    execution_time = Column(Integer, nullable=False)  # Execution time in milliseconds
    confidence_score = Column(Integer, nullable=True)  # NL parser confidence (0-100)
    
    # Relationship
    dataset = relationship("DatasetMetadata", back_populates="provenance")


class AuditLog(Base):
    """
    Audit log model for HIPAA compliance.
    
    Logs all data access, query submissions, and authentication attempts
    with write-once storage and integrity checksums.
    """
    __tablename__ = "audit_logs"
    
    log_id = Column(String, primary_key=True, index=True)
    timestamp = Column(DateTime(timezone=True), server_default=func.now(), nullable=False, index=True)
    user_id = Column(String, ForeignKey("users.id"), nullable=True, index=True)  # Nullable for failed auth attempts
    action = Column(String, nullable=False, index=True)  # e.g., "query_submit", "dataset_generate", "auth_attempt"
    details = Column(JSON, nullable=False)  # Action-specific details
    ip_address = Column(String, nullable=True)
    user_agent = Column(String, nullable=True)
    status = Column(String, nullable=False)  # "success" or "failure"
    error_message = Column(Text, nullable=True)
    integrity_checksum = Column(String, nullable=False)  # SHA-256 hash for tamper detection
    
    # Note: No update or delete operations allowed on audit logs (write-once)


class SchemaMapping(Base):
    """
    Schema mapping model for data source integration.
    
    Stores mappings between source schemas and canonical schema.
    """
    __tablename__ = "schema_mappings"
    
    mapping_id = Column(String, primary_key=True, index=True)
    source_name = Column(String, nullable=False, index=True)  # e.g., "redcap_study_1", "fhir_epic"
    source_schema = Column(String, nullable=False)
    target_schema = Column(String, nullable=False, default="canonical")
    field_mappings = Column(JSON, nullable=False)  # List of FieldMapping objects
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())
    created_by = Column(String, ForeignKey("users.id"), nullable=False)
