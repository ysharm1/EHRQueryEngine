"""
API Routes

FastAPI endpoints for the Research Dataset Builder.
Implements Requirements 1.1, 13.1, 10.7, 6.1.
"""

from fastapi import APIRouter, Depends, HTTPException, status, Request, UploadFile, File
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session
from typing import List, Optional
from pydantic import BaseModel
from datetime import datetime
from pathlib import Path
import pandas as pd
import logging

from app.database import get_db
from app.services.auth import AuthService, get_current_user
from app.services.nl_parser import NLParserService
from app.services.query_orchestrator import QueryOrchestrator, QueryRequest, QueryStatus
from app.services.audit_log import AuditLogService
from app.models.user import User
from app.models.metadata import ExportFormat


# Create router
router = APIRouter()


# Request/Response Models
class LoginRequest(BaseModel):
    """Login request model."""
    username: str
    password: str


class UserResponse(BaseModel):
    """User response model."""
    id: str
    username: str
    role: str


class LoginResponse(BaseModel):
    """Login response model."""
    access_token: str
    refresh_token: str
    user: UserResponse


class QuerySubmitRequest(BaseModel):
    """Query submission request model."""
    query_text: str
    data_source_ids: List[str] = ["subjects", "procedures", "observations"]
    output_format: str = "CSV"


class QuerySubmitResponse(BaseModel):
    """Query submission response model."""
    dataset_id: str
    status: str
    row_count: int
    column_count: int
    download_urls: List[str]
    metadata: dict
    error_message: Optional[str] = None


class DatasetMetadataResponse(BaseModel):
    """Dataset metadata response model."""
    dataset_id: str
    created_at: str
    created_by: str
    row_count: int
    column_count: int
    data_sources: List[str]
    export_format: str


class HealthResponse(BaseModel):
    """Health check response model."""
    status: str
    timestamp: str
    version: str


# Authentication Endpoints
@router.post("/auth/login", response_model=LoginResponse)
async def login(
    request: LoginRequest,
    req: Request,
    db: Session = Depends(get_db)
):
    """
    User authentication endpoint.
    
    Implements Requirement 13.1
    """
    audit_service = AuditLogService(db)
    
    # Get client info
    ip_address = req.client.host if req.client else None
    user_agent = req.headers.get("user-agent")
    
    try:
        # Authenticate user
        result = AuthService.authenticate(request.username, request.password, db)
        
        if not result["success"]:
            # Log failed attempt
            audit_service.log_authentication_attempt(
                user_id=None,
                username=request.username,
                success=False,
                ip_address=ip_address,
                user_agent=user_agent,
                error_message="Invalid credentials"
            )
            
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid username or password"
            )
        
        # Log successful authentication
        audit_service.log_authentication_attempt(
            user_id=result["user_id"],
            username=request.username,
            success=True,
            ip_address=ip_address,
            user_agent=user_agent
        )
        
        # Get user details
        user = AuthService.get_user_by_id(db, result["user_id"])
        
        return LoginResponse(
            access_token=result["access_token"],
            refresh_token=result["refresh_token"],
            user=UserResponse(
                id=user.id,
                username=user.username,
                role=result["role"]
            )
        )
    
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Authentication failed: {str(e)}"
        )


@router.post("/auth/logout")
async def logout(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    User logout endpoint.
    
    Implements Requirement 13.1
    """
    auth_service = AuthService(db)
    
    # Invalidate token (in a full implementation)
    # For now, just return success
    
    return {"message": "Logged out successfully"}


class RefreshRequest(BaseModel):
    refresh_token: str


@router.post("/auth/refresh")
async def refresh_token(
    request: RefreshRequest,
    db: Session = Depends(get_db)
):
    """
    Token refresh endpoint — validates refresh token and issues a new access token.

    Implements Requirement 13.1
    """
    payload = AuthService.decode_token(request.refresh_token)
    if payload is None or payload.get("type") != "refresh":
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired refresh token"
        )

    user_id = payload.get("sub")
    user = AuthService.get_user_by_id(db, user_id)
    if user is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="User not found")

    new_access_token = AuthService.create_access_token(data={"sub": user.id})
    return {
        "access_token": new_access_token,
        "token_type": "bearer"
    }


@router.get("/auth/me", response_model=UserResponse)
async def get_me(current_user: User = Depends(get_current_user)):
    """Return the currently authenticated user's profile."""
    return UserResponse(
        id=current_user.id,
        username=current_user.username,
        role=current_user.role.value if hasattr(current_user.role, "value") else current_user.role
    )


# Query Endpoints
@router.post("/query", response_model=QuerySubmitResponse)
async def submit_query(
    request: QuerySubmitRequest,
    req: Request,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Submit natural language query for dataset generation.
    
    Implements Requirements 1.1, 2.1, 3.1, 7.1
    """
    # Get client info
    ip_address = req.client.host if req.client else None
    user_agent = req.headers.get("user-agent")
    
    # Initialize services
    nl_parser = NLParserService()
    orchestrator = QueryOrchestrator(db, nl_parser)
    audit_service = AuditLogService(db)
    
    # Log query submission
    audit_service.log_query_submission(
        user_id=current_user.id,
        query_text=request.query_text,
        ip_address=ip_address,
        user_agent=user_agent
    )
    
    try:
        # Convert export format string to enum
        try:
            export_format = ExportFormat(request.output_format)
        except ValueError:
            export_format = ExportFormat.CSV
        
        # Create query request
        query_request = QueryRequest(
            user_id=current_user.id,
            query_text=request.query_text,
            data_source_ids=request.data_source_ids,
            output_format=export_format
        )
        
        # Process query
        response = orchestrator.process_query(query_request)
        
        # Log dataset generation if successful
        if response.status == QueryStatus.COMPLETED:
            audit_service.log_dataset_generation(
                user_id=current_user.id,
                dataset_id=response.dataset_id,
                cohort_size=response.row_count,
                variables=[],  # Would extract from metadata
                export_format=request.output_format,
                data_sources=request.data_source_ids,
                ip_address=ip_address,
                user_agent=user_agent
            )
        
        return QuerySubmitResponse(
            dataset_id=response.dataset_id,
            status=response.status.value,
            row_count=response.row_count,
            column_count=response.column_count,
            download_urls=response.download_urls,
            metadata=response.metadata,
            error_message=response.error_message
        )
    
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Query processing failed: {str(e)}"
        )


@router.get("/datasets")
async def list_datasets(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """List all datasets created by the current user."""
    from app.models.metadata import DatasetMetadata

    datasets = (
        db.query(DatasetMetadata)
        .filter(DatasetMetadata.created_by == current_user.id)
        .order_by(DatasetMetadata.created_at.desc())
        .all()
    )

    return {
        "datasets": [
            {
                "dataset_id": d.dataset_id,
                "created_at": d.created_at.isoformat(),
                "row_count": d.row_count,
                "column_count": d.column_count,
                "data_sources": d.data_sources,
                "export_format": d.export_format.value,
            }
            for d in datasets
        ]
    }


@router.get("/query/{dataset_id}/status")
async def get_query_status(
    dataset_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Return the status of a previously submitted query by dataset ID."""
    from app.models.metadata import DatasetMetadata

    dataset = db.query(DatasetMetadata).filter(
        DatasetMetadata.dataset_id == dataset_id
    ).first()

    if not dataset:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Dataset not found")

    return {
        "dataset_id": dataset_id,
        "status": "Completed",
        "row_count": dataset.row_count,
        "column_count": dataset.column_count,
    }


@router.get("/dataset/{dataset_id}")
async def get_dataset(
    dataset_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Return full dataset: metadata, schema, rows (up to 500), and provenance.

    Implements Requirement 10.7
    """
    from app.models.metadata import DatasetMetadata, QueryProvenance
    import json as _json

    dataset = db.query(DatasetMetadata).filter(
        DatasetMetadata.dataset_id == dataset_id
    ).first()

    if not dataset:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Dataset {dataset_id} not found"
        )

    # Load rows from the CSV data file (first file in file_paths list)
    rows: list = []
    schema_columns: list = []
    data_file = next(
        (p for p in (dataset.file_paths or []) if p.endswith(".csv")),
        None
    )
    if data_file and Path(data_file).exists():
        df = pd.read_csv(data_file, nrows=500)
        rows = df.values.tolist()
        schema_columns = [
            {
                "name": col,
                "data_type": str(df[col].dtype),
                "nullable": bool(df[col].isna().any()),
                "description": "",
            }
            for col in df.columns
        ]

    # Load provenance
    provenance = db.query(QueryProvenance).filter(
        QueryProvenance.dataset_id == dataset_id
    ).first()
    provenance_data = {}
    if provenance:
        provenance_data = {
            "original_query": provenance.original_query,
            "parsed_intent": provenance.parsed_intent,
            "sql_executed": provenance.sql_executed,
            "execution_time": provenance.execution_time / 1000.0,
        }

    return {
        "dataset_id": dataset.dataset_id,
        "rows": rows,
        "schema": {"columns": schema_columns},
        "metadata": {
            "created_at": dataset.created_at.isoformat(),
            "created_by": dataset.created_by,
            "row_count": dataset.row_count,
            "column_count": dataset.column_count,
            "data_sources": dataset.data_sources,
        },
        "query_provenance": provenance_data,
    }


@router.get("/dataset/{dataset_id}/files")
async def list_dataset_files(
    dataset_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """List available download files for a dataset with size info."""
    from app.models.metadata import DatasetMetadata
    import os as _os

    dataset = db.query(DatasetMetadata).filter(
        DatasetMetadata.dataset_id == dataset_id
    ).first()

    if not dataset:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Dataset not found")

    files = []
    for fp in (dataset.file_paths or []):
        p = Path(fp)
        if p.exists():
            files.append({
                "name": p.name,
                "url": f"/api/dataset/{dataset_id}/download?file_name={p.name}",
                "size": _os.path.getsize(fp),
            })

    return {
        "dataset_id": dataset_id,
        "format": dataset.export_format.value,
        "download_urls": [f["url"] for f in files],
        "files": files,
    }


@router.get("/dataset/{dataset_id}/download")
async def download_dataset(
    dataset_id: str,
    file_name: Optional[str] = None,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Download dataset files.
    
    Implements Requirement 10.7
    """
    from app.models.metadata import DatasetMetadata
    
    # Query dataset metadata
    dataset = db.query(DatasetMetadata).filter(
        DatasetMetadata.dataset_id == dataset_id
    ).first()
    
    if not dataset:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Dataset {dataset_id} not found"
        )
    
    # Get file path
    if file_name:
        # Find specific file
        file_path = None
        for path in dataset.file_paths:
            if file_name in path:
                file_path = path
                break
        
        if not file_path:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"File {file_name} not found"
            )
    else:
        # Return first file (data file)
        if not dataset.file_paths:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="No files found for dataset"
            )
        file_path = dataset.file_paths[0]
    
    # Check if file exists
    if not Path(file_path).exists():
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="File not found on disk"
        )
    
    # Return file
    return FileResponse(
        path=file_path,
        filename=Path(file_path).name,
        media_type="application/octet-stream"
    )


# File Upload Endpoint
@router.post("/upload")
async def upload_data(
    file: UploadFile = File(...),
    table_name: Optional[str] = None,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Upload CSV/Excel file and import into DuckDB.
    
    Automatically detects schema and creates table.
    """
    from app.database import get_duckdb_connection
    from app.services.smart_schema_detector import SmartSchemaDetector
    
    audit_service = AuditLogService(db)
    
    try:
        # Read file based on extension
        file_ext = Path(file.filename).suffix.lower()
        
        if file_ext == '.csv':
            df = pd.read_csv(file.file)
        elif file_ext in ['.xlsx', '.xls']:
            df = pd.read_excel(file.file)
        elif file_ext == '.json':
            df = pd.read_json(file.file)
        elif file_ext == '.parquet':
            df = pd.read_parquet(file.file)
        else:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Unsupported file type: {file_ext}. Supported: .csv, .xlsx, .xls, .json, .parquet"
            )
        
        # Auto-generate table name if not provided
        if not table_name:
            table_name = Path(file.filename).stem.lower().replace(' ', '_').replace('-', '_')
            # Ensure valid SQL identifier
            table_name = ''.join(c if c.isalnum() or c == '_' else '_' for c in table_name)
        
        # Detect schema using smart detector
        detector = SmartSchemaDetector()
        detected_schema = detector.detect_schema(df)
        
        # Sanitize DataFrame for DuckDB compatibility
        # Write to temp CSV to avoid pandas dtype issues with DuckDB
        import tempfile, os

        tmp_file = tempfile.NamedTemporaryFile(mode='w', suffix='.csv', delete=False)
        df.to_csv(tmp_file.name, index=False)
        tmp_path = tmp_file.name

        try:
            # Connect to DuckDB
            conn = get_duckdb_connection()

            # Check if table exists
            existing_tables = conn.execute("SHOW TABLES").fetchall()
            table_exists = any(table_name == t[0] for t in existing_tables)

            if table_exists:
                # Drop and recreate to avoid schema mismatch issues
                try:
                    conn.execute(f"DROP TABLE IF EXISTS \"{table_name}\" CASCADE")
                except Exception:
                    table_name = f"{table_name}_{int(datetime.now().timestamp())}"
                conn.execute(f"CREATE TABLE \"{table_name}\" AS SELECT * FROM read_csv_auto('{tmp_path}')")
                action = "replaced"
            else:
                conn.execute(f"CREATE TABLE \"{table_name}\" AS SELECT * FROM read_csv_auto('{tmp_path}')")
                action = "created"

            conn.close()
        finally:
            os.unlink(tmp_path)
        
        # Log upload
        audit_service.log_data_upload(
            user_id=current_user.id,
            filename=file.filename,
            table_name=table_name,
            row_count=len(df),
            column_count=len(df.columns)
        )
        
        return {
            "status": "success",
            "message": f"Table {action} successfully",
            "table_name": table_name,
            "rows_imported": len(df),
            "columns": list(df.columns),
            "detected_schema": detected_schema.to_dict(),
            "sample_data": df.head(5).to_dict(orient='records')
        }
    
    except pd.errors.EmptyDataError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="File is empty"
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Upload failed: {str(e)}"
        )


@router.get("/schema/analyze")
async def analyze_schema(
    current_user: User = Depends(get_current_user)
):
    """
    Analyze database schema and return semantic mappings.
    Shows all tables, columns, and their inferred semantic types.
    """
    from app.database import get_duckdb_connection
    from app.services.dynamic_schema_analyzer import DynamicSchemaAnalyzer
    
    try:
        conn = get_duckdb_connection()
        analyzer = DynamicSchemaAnalyzer(conn)
        summary = analyzer.get_schema_summary()
        conn.close()
        
        return summary
    
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Schema analysis failed: {str(e)}"
        )


@router.get("/schema/map")
async def map_terms_to_columns(
    terms: str,  # Comma-separated list
    current_user: User = Depends(get_current_user)
):
    """
    Map natural language terms to database columns.
    Example: /schema/map?terms=age,diagnosis,gender
    """
    from app.database import get_duckdb_connection
    from app.services.dynamic_schema_analyzer import DynamicSchemaAnalyzer
    
    try:
        conn = get_duckdb_connection()
        analyzer = DynamicSchemaAnalyzer(conn)
        
        term_list = [t.strip() for t in terms.split(",")]
        mappings = analyzer.map_natural_language_to_columns(term_list)
        
        conn.close()
        
        return {
            "terms": term_list,
            "mappings": {
                term: {
                    "table": col.table_name,
                    "column": col.column_name,
                    "type": col.data_type,
                    "semantic_type": col.semantic_type,
                    "confidence": col.confidence
                }
                for term, col in mappings.items()
            }
        }
    
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Term mapping failed: {str(e)}"
        )


@router.get("/tables")
async def list_tables(
    current_user: User = Depends(get_current_user)
):
    """
    List all available tables in DuckDB.
    """
    from app.database import get_duckdb_connection
    
    try:
        conn = get_duckdb_connection()
        
        # Get all tables
        tables = conn.execute("SHOW TABLES").fetchall()
        
        # Get row counts for each table
        table_info = []
        for table in tables:
            table_name = table[0]
            row_count = conn.execute(f"SELECT COUNT(*) FROM {table_name}").fetchone()[0]
            columns = conn.execute(f"DESCRIBE {table_name}").fetchall()
            
            table_info.append({
                "name": table_name,
                "row_count": row_count,
                "columns": [{"name": col[0], "type": col[1]} for col in columns]
            })
        
        conn.close()
        
        return {
            "tables": table_info,
            "total_tables": len(table_info)
        }
    
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to list tables: {str(e)}"
        )


@router.get("/demo/download/{dataset_id}")
async def demo_download(
    dataset_id: str,
    file_name: Optional[str] = None,
    db: Session = Depends(get_db)
):
    """Public download endpoint for demo datasets."""
    from app.models.metadata import DatasetMetadata

    dataset = db.query(DatasetMetadata).filter(
        DatasetMetadata.dataset_id == dataset_id
    ).first()

    if not dataset:
        raise HTTPException(status_code=404, detail="Dataset not found")

    if file_name:
        file_path = next((p for p in dataset.file_paths if file_name in p), None)
    else:
        file_path = dataset.file_paths[0] if dataset.file_paths else None

    if not file_path or not Path(file_path).exists():
        raise HTTPException(status_code=404, detail="File not found")

    return FileResponse(
        path=file_path,
        filename=Path(file_path).name,
        media_type="application/octet-stream"
    )


# Health Check Endpoint
@router.get("/health", response_model=HealthResponse)
async def health_check():
    """Health check endpoint."""
    return HealthResponse(
        status="healthy",
        timestamp=datetime.now().isoformat(),
        version="1.1.0-upload-fix"
    )


# ── Public Dataset Discovery (no auth required) ───────────────────────────────
@router.get("/demo/public-datasets")
async def search_public_datasets(q: str = ""):
    """Search for publicly available datasets matching the query."""
    from app.services.public_dataset_search import search_public_datasets as _search
    results = _search(q)
    return {"query": q, "results": results}


@router.post("/demo/upload")
async def demo_upload(
    file: UploadFile = File(...),
    db: Session = Depends(get_db)
):
    """
    Public upload endpoint — no authentication required.
    Accepts CSV/Excel/JSON files and loads them into DuckDB for querying.
    Streams file to disk to handle large files without loading into memory.
    """
    from app.database import get_duckdb_connection
    from app.services.smart_schema_detector import SmartSchemaDetector
    import tempfile, os, shutil

    tmp_path = None
    try:
        file_ext = Path(file.filename).suffix.lower()

        if file_ext not in ('.csv', '.xlsx', '.xls', '.json'):
            raise HTTPException(
                status_code=400,
                detail=f"Unsupported file type: {file_ext}. Use .csv, .xlsx, .xls, or .json"
            )

        # Stream upload directly to a temp file (avoids loading into memory)
        tmp_file = tempfile.NamedTemporaryFile(mode='wb', suffix=file_ext, delete=False)
        tmp_path = tmp_file.name
        with tmp_file:
            shutil.copyfileobj(file.file, tmp_file)

        file_size = os.path.getsize(tmp_path)
        if file_size == 0:
            raise HTTPException(status_code=400, detail="File is empty")

        # Generate safe table name
        table_name = Path(file.filename).stem.lower()
        table_name = ''.join(c if c.isalnum() or c == '_' else '_' for c in table_name)
        if not table_name or table_name[0].isdigit():
            table_name = f"upload_{table_name}"

        system_tables = {"patients", "vital_signs", "lab_results", "diagnoses",
                        "procedures_extracted", "medications", "clinical_notes",
                        "imaging_reports", "extraction_jobs", "encounters", "data_provenance"}
        if table_name in system_tables:
            table_name = f"uploaded_{table_name}"

        conn = get_duckdb_connection()

        # For CSV, use DuckDB's native loader — handles huge files efficiently
        if file_ext == '.csv':
            existing = [t[0] for t in conn.execute("SHOW TABLES").fetchall()]
            if table_name in existing:
                try:
                    conn.execute(f"DROP TABLE IF EXISTS \"{table_name}\" CASCADE")
                except Exception:
                    table_name = f"{table_name}_{int(datetime.now().timestamp())}"

            # Try read_csv_auto first, fall back to all_varchar on type errors
            try:
                conn.execute(
                    f"CREATE TABLE \"{table_name}\" AS "
                    f"SELECT * FROM read_csv_auto(?, sample_size=10000)",
                    [tmp_path]
                )
            except Exception:
                # Fallback: force all columns to VARCHAR to bypass type inference
                conn.execute(
                    f"CREATE TABLE \"{table_name}\" AS "
                    f"SELECT * FROM read_csv(?, all_varchar=true, header=true)",
                    [tmp_path]
                )
        else:
            # For Excel/JSON, we still need pandas
            if file_ext in ('.xlsx', '.xls'):
                df = pd.read_excel(tmp_path)
            else:  # .json
                df = pd.read_json(tmp_path)

            if df.empty:
                raise HTTPException(status_code=400, detail="File is empty")

            # Write to CSV then use DuckDB's native loader
            csv_tmp = tempfile.NamedTemporaryFile(mode='w', suffix='.csv', delete=False)
            csv_tmp.close()
            df.to_csv(csv_tmp.name, index=False)
            try:
                existing = [t[0] for t in conn.execute("SHOW TABLES").fetchall()]
                if table_name in existing:
                    try:
                        conn.execute(f"DROP TABLE IF EXISTS \"{table_name}\" CASCADE")
                    except Exception:
                        table_name = f"{table_name}_{int(datetime.now().timestamp())}"
                conn.execute(
                    f"CREATE TABLE \"{table_name}\" AS "
                    f"SELECT * FROM read_csv(?, all_varchar=true, header=true)",
                    [csv_tmp.name]
                )
            finally:
                os.unlink(csv_tmp.name)

        # Get row count and columns from DuckDB
        row_count = conn.execute(f"SELECT COUNT(*) FROM \"{table_name}\"").fetchone()[0]
        col_info = conn.execute(f"DESCRIBE \"{table_name}\"").fetchall()
        columns = [c[0] for c in col_info]
        sample_rows = conn.execute(f"SELECT * FROM \"{table_name}\" LIMIT 3").fetchall()
        sample_data = [dict(zip(columns, row)) for row in sample_rows]

        # Build a lightweight schema summary (no pandas needed)
        detected_schema = {
            "row_count": row_count,
            "inferred_subject_id_column": next(
                (c for c in columns if c.lower() in ('subject_id', 'patient_id', 'id', 'mrn')),
                None
            ),
            "columns": [{"name": c[0], "data_type": c[1]} for c in col_info],
        }

        conn.close()

        return {
            "status": "success",
            "table_name": table_name,
            "rows_imported": row_count,
            "columns": columns,
            "sample_data": sample_data,
            "detected_schema": detected_schema,
        }

    except HTTPException:
        raise
    except Exception as e:
        import traceback
        tb = traceback.format_exc()
        logger = logging.getLogger(__name__)
        logger.error(f"Upload failed: {tb}")
        raise HTTPException(status_code=500, detail=f"Upload failed: {str(e)} | Traceback: {tb[-500:]}")
    finally:
        if tmp_path and os.path.exists(tmp_path):
            os.unlink(tmp_path)


# ── Public Demo Endpoint (no auth required) ──────────────────────────────────
@router.post("/demo/query")
async def demo_query(
    request: QuerySubmitRequest,
    db: Session = Depends(get_db)
):
    """
    Public demo endpoint — no authentication required.
    Uses a fixed demo user so anyone can try the NL query engine.
    Falls back to DuckDB-native search against uploaded tables if the
    SQLAlchemy-based cohort pipeline returns no results.
    """
    nl_parser = NLParserService()
    orchestrator = QueryOrchestrator(db, nl_parser)

    try:
        export_format = ExportFormat(request.output_format)
    except ValueError:
        export_format = ExportFormat.CSV

    query_request = QueryRequest(
        user_id="demo-user",
        query_text=request.query_text,
        data_source_ids=request.data_source_ids,
        output_format=export_format,
    )

    response = orchestrator.process_query(query_request)

    # Fallback: if the standard pipeline found nothing, try DuckDB-native
    # search against uploaded tables. This handles the case where users
    # upload CSVs (which go to DuckDB) and query them.
    no_subjects = (
        response.row_count == 0
        and response.status.value in ("Failed",)
        and (response.error_message or "").lower().find("no subjects") >= 0
    ) or (response.row_count == 0 and not response.error_message)

    if no_subjects:
        try:
            fallback = _run_duckdb_fallback(
                nl_parser=nl_parser,
                query_text=request.query_text,
                export_format=export_format,
                user_id="demo-user",
                db=db,
            )
            if fallback is not None:
                return fallback
        except Exception as e:
            logger = logging.getLogger(__name__)
            logger.warning(f"DuckDB fallback failed: {e}")

    # Rewrite download URLs to use the public demo download endpoint
    public_urls = []
    for url in response.download_urls:
        public_url = url.replace(f"/api/dataset/{response.dataset_id}/download", f"/api/demo/download/{response.dataset_id}")
        public_urls.append(public_url)

    return QuerySubmitResponse(
        dataset_id=response.dataset_id,
        status=response.status.value,
        row_count=response.row_count,
        column_count=response.column_count,
        download_urls=public_urls,
        metadata=response.metadata,
        error_message=response.error_message,
    )


def _run_duckdb_fallback(
    nl_parser,
    query_text: str,
    export_format,
    user_id: str,
    db: Session,
) -> Optional[QuerySubmitResponse]:
    """
    Run LLM-powered DuckDB query as a fallback when the standard
    SQLAlchemy pipeline returns no results. Uses GPT to generate SQL
    directly against uploaded tables — handles misspellings, scattered
    data, and complex JOINs automatically.
    """
    from app.database import get_duckdb_connection
    from app.services.llm_sql_generator import generate_sql, execute_generated_sql
    from app.models.metadata import DatasetMetadata as DatasetMetadataModel, QueryProvenance as QueryProvenanceModel
    import uuid as _uuid
    import csv
    import os

    conn = get_duckdb_connection()
    try:
        # Step 1: Have LLM generate SQL from the query
        gen_result = generate_sql(conn, query_text)
        if gen_result.get("error") or not gen_result.get("sql"):
            # If LLM fails, fall back to heuristic search
            from app.services.duckdb_cohort_search import search_duckdb_cohort
            parsed = nl_parser.parse(query_text)
            criteria = parsed.to_dict().get("cohort_criteria", [])
            if not criteria:
                conn.close()
                return None
            result = search_duckdb_cohort(conn, criteria)
            conn.close()
            subjects = result.get("subjects", [])
            if not subjects:
                msg = result.get("message", "No matches in uploaded data")
                return QuerySubmitResponse(
                    dataset_id="",
                    status="Failed",
                    row_count=0,
                    column_count=0,
                    download_urls=[],
                    metadata={"fallback": "heuristic", "message": msg},
                    error_message=msg,
                )
            rows = subjects
            columns = list(subjects[0].keys())
            sql_used = result.get("sql", "")
        else:
            # Step 2: Execute the generated SQL
            sql = gen_result["sql"]
            exec_result = execute_generated_sql(conn, sql)
            conn.close()

            if exec_result.get("error") or exec_result["row_count"] == 0:
                msg = exec_result.get("error") or "No matching data found"
                return QuerySubmitResponse(
                    dataset_id="",
                    status="Failed",
                    row_count=0,
                    column_count=0,
                    download_urls=[],
                    metadata={"fallback": "llm", "sql": sql, "message": msg},
                    error_message=msg,
                )

            rows = exec_result["rows"]
            columns = exec_result["columns"]
            sql_used = sql
    except Exception as e:
        try:
            conn.close()
        except Exception:
            pass
        logger = logging.getLogger(__name__)
        logger.error(f"DuckDB fallback failed: {e}")
        return None

    # Step 3: Write CSV export
    dataset_id = str(_uuid.uuid4())
    export_dir = "/tmp/exports"
    os.makedirs(export_dir, exist_ok=True)
    csv_path = os.path.join(export_dir, f"{dataset_id}_data.csv")

    with open(csv_path, "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=columns)
        writer.writeheader()
        for row in rows:
            writer.writerow({k: ("" if v is None else v) for k, v in row.items()})

    # Step 4: Persist metadata
    parsed = nl_parser.parse(query_text)
    parsed_dict = parsed.to_dict()

    db_meta = DatasetMetadataModel(
        dataset_id=dataset_id,
        created_by=user_id,
        row_count=len(rows),
        column_count=len(columns),
        data_sources=["uploaded"],
        export_format=export_format,
        file_paths=[csv_path],
    )
    db_prov = QueryProvenanceModel(
        provenance_id=str(_uuid.uuid4()),
        dataset_id=dataset_id,
        original_query=query_text,
        parsed_intent=parsed_dict,
        sql_executed=sql_used,
        execution_time=0,
        confidence_score=int((parsed_dict.get("confidence", 0) or 0) * 100),
    )
    db.add(db_meta)
    db.add(db_prov)
    db.commit()

    download_urls = [f"/api/demo/download/{dataset_id}?file_name={os.path.basename(csv_path)}"]

    return QuerySubmitResponse(
        dataset_id=dataset_id,
        status="Completed",
        row_count=len(rows),
        column_count=len(columns),
        download_urls=download_urls,
        metadata={
            "fallback": "llm",
            "sql": sql_used,
        },
        error_message=None,
    )
