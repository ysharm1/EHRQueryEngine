# Research Dataset Builder - Backend

Backend API for the Research Dataset Builder platform, enabling biomedical researchers to generate structured datasets from multimodal data sources using natural language queries.

## Features

- **Natural Language Query Processing**: Submit queries in plain English
- **Query Planning & Validation**: Optimized, safe query execution
- **Multi-source Data Integration**: FHIR, REDCap, CSV, imaging data
- **Cohort Identification**: Filter subjects by diagnosis, procedures, demographics
- **Dataset Assembly**: Collect variables with missing value handling
- **Multiple Export Formats**: CSV, Parquet, JSON
- **Audit Logging**: HIPAA-compliant audit trails
- **Authentication & Authorization**: Role-based access control

## Architecture

```
backend/
├── app/
│   ├── api/              # API endpoints
│   ├── models/           # Database models
│   ├── services/         # Business logic services
│   │   ├── auth.py              # Authentication
│   │   ├── nl_parser.py         # Natural language parsing
│   │   ├── query_planner.py    # Query plan generation
│   │   ├── query_validator.py  # Query safety validation
│   │   ├── schema_mapper.py    # Schema transformation
│   │   ├── fhir_connector.py   # FHIR integration
│   │   ├── cohort.py           # Cohort identification
│   │   ├── dataset_assembly.py # Dataset assembly
│   │   ├── export_engine.py    # File export
│   │   ├── query_orchestrator.py # Pipeline coordinator
│   │   ├── audit_log.py        # Audit logging
│   │   └── error_handler.py    # Error handling
│   ├── config.py         # Configuration
│   ├── database.py       # Database setup
│   ├── init_db.py        # Database initialization
│   └── main.py           # FastAPI application
├── requirements.txt      # Python dependencies
└── README.md            # This file
```

## Setup

### Prerequisites

- Python 3.9+
- PostgreSQL 15+
- OpenAI API key (for natural language parsing)

### Installation

1. Create virtual environment:
```bash
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
```

2. Install dependencies:
```bash
pip install -r requirements.txt
```

3. Configure environment variables:
```bash
cp .env.example .env
# Edit .env with your configuration
```

Required environment variables:
- `DATABASE_URL`: PostgreSQL connection string
- `OPENAI_API_KEY`: OpenAI API key for NL parsing
- `SECRET_KEY`: JWT secret key
- `APP_ENV`: Environment (development/production)

4. Initialize database:
```bash
python -m app.init_db
```

This will:
- Create all database tables
- Create indexes for query optimization
- Generate sample data for testing

### Running the Server

Development mode:
```bash
uvicorn app.main:app --reload --port 8000
```

Production mode:
```bash
uvicorn app.main:app --host 0.0.0.0 --port 8000 --workers 4
```

## API Endpoints

### Authentication
- `POST /api/auth/login` - User login
- `POST /api/auth/logout` - User logout
- `POST /api/auth/refresh` - Refresh access token

### Query Processing
- `POST /api/query` - Submit natural language query
- `GET /api/dataset/{id}` - Get dataset metadata
- `GET /api/dataset/{id}/download` - Download dataset files

### FHIR Integration
- `POST /api/fhir/ingest` - Ingest FHIR data

### Health Check
- `GET /api/health` - Service health status

## Sample Usage

### 1. Login
```bash
curl -X POST http://localhost:8000/api/auth/login \
  -H "Content-Type: application/json" \
  -d '{"username": "researcher", "password": "researcher123"}'
```

### 2. Submit Query
```bash
curl -X POST http://localhost:8000/api/query \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer YOUR_TOKEN" \
  -d '{
    "query_text": "Find all Parkinsons patients with DBS surgery",
    "data_source_ids": ["subjects", "procedures"],
    "output_format": "CSV"
  }'
```

### 3. Download Dataset
```bash
curl -X GET http://localhost:8000/api/dataset/{dataset_id}/download \
  -H "Authorization: Bearer YOUR_TOKEN" \
  -o dataset.csv
```

## Sample Data

The database initialization creates sample data including:
- 5 subjects with Parkinson's disease
- 3 DBS procedures
- Multiple observations (vitals)
- 2 MRI imaging studies

Sample users:
- **Admin**: username=`admin`, password=`admin123`
- **Researcher**: username=`researcher`, password=`researcher123`

## Testing

Run tests:
```bash
pytest
```

Run with coverage:
```bash
pytest --cov=app --cov-report=html
```

## Services Overview

### Query Orchestrator
Coordinates the entire query-to-dataset pipeline:
1. Parse natural language query
2. Validate confidence threshold
3. Create query plan
4. Validate query safety
5. Identify cohort
6. Assemble dataset
7. Generate export files

### Natural Language Parser
Uses LLM (OpenAI) to extract:
- Cohort criteria (diagnosis, procedures, demographics)
- Requested variables
- Time ranges
- Confidence scores

### Query Planner
Generates optimized query plans:
- Converts parsed intent to SQL
- Optimizes join order
- Estimates result set size

### Query Validator
Ensures query safety:
- Verifies read-only operations
- Detects recursive queries
- Enforces row count limits
- Validates table references

### Cohort Identifier
Filters subjects by criteria:
- Diagnosis codes (ICD-10, SNOMED)
- Procedure codes (CPT)
- Demographics (age, sex)
- Observations (lab values)

### Dataset Assembly Engine
Assembles analysis-ready datasets:
- Collects variables from multiple sources
- Handles missing values (default, null, mean, exclude)
- Normalizes variable names
- Generates metadata and provenance

### Export Engine
Generates dataset files:
- CSV, Parquet, JSON formats
- Schema definition (JSON)
- Query provenance (SQL)
- Reproducible queries

### FHIR Connector
Integrates with EHR systems:
- Authenticates with FHIR endpoints
- Executes FHIR search queries
- Handles pagination
- Transforms FHIR resources to canonical schema

### Audit Log Service
HIPAA-compliant audit logging:
- Logs all data access
- Logs query submissions
- Logs authentication attempts
- Integrity checksums (SHA-256)
- 7-year retention

## Security

- **Authentication**: JWT tokens with 30-minute timeout
- **Authorization**: Role-based access control (Admin, Researcher, Data_Analyst, Read_Only)
- **Encryption**: TLS for transport, AES-256 for storage
- **Audit Logging**: Comprehensive audit trails
- **Query Validation**: Prevents SQL injection and data modification

## Requirements Implemented

The backend implements all core requirements from the specification:
- Requirements 1.1-1.5: Natural language query processing
- Requirements 2.1-2.5: Query plan generation
- Requirements 3.1-3.7: Query safety validation
- Requirements 4.1-4.7: Cohort identification
- Requirements 5.1-5.7: Schema mapping
- Requirements 6.1-6.8: FHIR integration
- Requirements 7.1-7.7: Dataset assembly
- Requirements 8.1-8.6: Missing value handling
- Requirements 9.1-9.6: Variable name normalization
- Requirements 10.1-10.7: Dataset export
- Requirements 11.1-11.6: Query reproducibility
- Requirements 13.1-13.7: Authentication & authorization
- Requirements 14.1-14.7: Audit logging
- Requirements 16.1-16.7: Error handling
- Requirements 18.1-18.5: Timeout & resource limits
- Requirements 19.1-19.7: Data provenance tracking

## License

Copyright © 2024 Research Dataset Builder
