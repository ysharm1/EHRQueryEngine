"""
Audit Log Service

Comprehensive audit logging for HIPAA compliance.
Implements Requirements 14.1-14.7, 19.6.
"""

from typing import Dict, Any, Optional
from sqlalchemy.orm import Session
from datetime import datetime
import hashlib
import json
import uuid
from app.models.metadata import AuditLog


class AuditLogService:
    """
    Audit Log service for HIPAA compliance.
    
    Implements:
    - Requirement 14.1: Log query submissions
    - Requirement 14.2: Log dataset generation
    - Requirement 14.3: Log authentication attempts
    - Requirement 14.4: Log data source access
    - Requirement 14.5: Use write-once storage
    - Requirement 14.6: 7-year retention policy
    - Requirement 14.7: Include integrity checksums
    - Requirement 19.6: Ensure provenance immutability
    """
    
    def __init__(self, db: Session):
        """
        Initialize audit log service.
        
        Args:
            db: Database session
        """
        self.db = db
    
    def log_query_submission(
        self,
        user_id: str,
        query_text: str,
        ip_address: Optional[str] = None,
        user_agent: Optional[str] = None
    ) -> str:
        """
        Log query submission.
        
        Implements Requirement 14.1
        """
        details = {
            "query_text": query_text,
            "action_type": "query_submit"
        }
        
        return self._create_log_entry(
            user_id=user_id,
            action="query_submit",
            details=details,
            status="success",
            ip_address=ip_address,
            user_agent=user_agent
        )
    
    def log_dataset_generation(
        self,
        user_id: str,
        dataset_id: str,
        cohort_size: int,
        variables: list,
        export_format: str,
        data_sources: list,
        ip_address: Optional[str] = None,
        user_agent: Optional[str] = None
    ) -> str:
        """
        Log dataset generation.
        
        Implements Requirements 14.2, 14.4
        """
        details = {
            "dataset_id": dataset_id,
            "cohort_size": cohort_size,
            "variables": variables,
            "export_format": export_format,
            "data_sources": data_sources,
            "action_type": "dataset_generate"
        }
        
        return self._create_log_entry(
            user_id=user_id,
            action="dataset_generate",
            details=details,
            status="success",
            ip_address=ip_address,
            user_agent=user_agent
        )
    
    def log_authentication_attempt(
        self,
        user_id: Optional[str],
        username: str,
        success: bool,
        ip_address: Optional[str] = None,
        user_agent: Optional[str] = None,
        error_message: Optional[str] = None
    ) -> str:
        """
        Log authentication attempt.
        
        Implements Requirement 14.3
        """
        details = {
            "username": username,
            "action_type": "auth_attempt"
        }
        
        return self._create_log_entry(
            user_id=user_id,
            action="auth_attempt",
            details=details,
            status="success" if success else "failure",
            ip_address=ip_address,
            user_agent=user_agent,
            error_message=error_message
        )
    
    def log_data_access(
        self,
        user_id: str,
        data_sources: list,
        access_type: str,
        ip_address: Optional[str] = None,
        user_agent: Optional[str] = None
    ) -> str:
        """
        Log data source access.
        
        Implements Requirement 14.4
        """
        details = {
            "data_sources": data_sources,
            "access_type": access_type,
            "action_type": "data_access"
        }
        
        return self._create_log_entry(
            user_id=user_id,
            action="data_access",
            details=details,
            status="success",
            ip_address=ip_address,
            user_agent=user_agent
        )
    
    def log_data_upload(
        self,
        user_id: str,
        filename: str,
        table_name: str,
        row_count: int,
        column_count: int,
        ip_address: Optional[str] = None,
        user_agent: Optional[str] = None
    ) -> str:
        """
        Log data file upload.
        
        Implements Requirement 14.4
        """
        details = {
            "filename": filename,
            "table_name": table_name,
            "row_count": row_count,
            "column_count": column_count,
            "action_type": "data_upload"
        }
        
        return self._create_log_entry(
            user_id=user_id,
            action="data_upload",
            details=details,
            status="success",
            ip_address=ip_address,
            user_agent=user_agent
        )
    
    def _create_log_entry(
        self,
        user_id: Optional[str],
        action: str,
        details: Dict[str, Any],
        status: str,
        ip_address: Optional[str] = None,
        user_agent: Optional[str] = None,
        error_message: Optional[str] = None
    ) -> str:
        """
        Create audit log entry with integrity checksum.
        
        Implements Requirements 14.5, 14.7
        """
        log_id = str(uuid.uuid4())
        timestamp = datetime.now()
        
        # Generate integrity checksum (Req 14.7)
        checksum = self._generate_checksum(
            log_id=log_id,
            timestamp=timestamp,
            user_id=user_id,
            action=action,
            details=details,
            status=status
        )
        
        # Create audit log entry (Req 14.5 - write-once)
        audit_log = AuditLog(
            log_id=log_id,
            timestamp=timestamp,
            user_id=user_id,
            action=action,
            details=details,
            ip_address=ip_address,
            user_agent=user_agent,
            status=status,
            error_message=error_message,
            integrity_checksum=checksum
        )
        
        self.db.add(audit_log)
        self.db.commit()
        
        return log_id
    
    def _generate_checksum(
        self,
        log_id: str,
        timestamp: datetime,
        user_id: Optional[str],
        action: str,
        details: Dict[str, Any],
        status: str
    ) -> str:
        """
        Generate SHA-256 integrity checksum for audit log entry.
        
        Implements Requirement 14.7
        """
        # Combine all fields into a single string
        data_string = f"{log_id}|{timestamp.isoformat()}|{user_id}|{action}|{json.dumps(details, sort_keys=True)}|{status}"
        
        # Generate SHA-256 hash
        checksum = hashlib.sha256(data_string.encode('utf-8')).hexdigest()
        
        return checksum
    
    def verify_integrity(self, log_id: str) -> bool:
        """
        Verify integrity of an audit log entry.
        
        Args:
            log_id: ID of audit log entry to verify
        
        Returns:
            True if integrity check passes, False otherwise
        
        Implements Requirement 14.7
        """
        # Retrieve log entry
        log_entry = self.db.query(AuditLog).filter(
            AuditLog.log_id == log_id
        ).first()
        
        if not log_entry:
            return False
        
        # Recalculate checksum
        expected_checksum = self._generate_checksum(
            log_id=log_entry.log_id,
            timestamp=log_entry.timestamp,
            user_id=log_entry.user_id,
            action=log_entry.action,
            details=log_entry.details,
            status=log_entry.status
        )
        
        # Compare with stored checksum
        return expected_checksum == log_entry.integrity_checksum
    
    def get_logs(
        self,
        user_id: Optional[str] = None,
        action: Optional[str] = None,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
        limit: int = 100
    ) -> list:
        """
        Retrieve audit logs with optional filters.
        
        Args:
            user_id: Filter by user ID
            action: Filter by action type
            start_date: Filter by start date
            end_date: Filter by end date
            limit: Maximum number of logs to return
        
        Returns:
            List of audit log entries
        """
        query = self.db.query(AuditLog)
        
        if user_id:
            query = query.filter(AuditLog.user_id == user_id)
        
        if action:
            query = query.filter(AuditLog.action == action)
        
        if start_date:
            query = query.filter(AuditLog.timestamp >= start_date)
        
        if end_date:
            query = query.filter(AuditLog.timestamp <= end_date)
        
        # Order by timestamp descending
        query = query.order_by(AuditLog.timestamp.desc())
        
        # Apply limit
        query = query.limit(limit)
        
        return query.all()
