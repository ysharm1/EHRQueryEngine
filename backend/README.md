# Backend

FastAPI backend for the EHR Query Engine.

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

See main [README.md](../README.md) for full setup instructions.

### Quick Start

```bash
# Install dependencies
pip install -r requirements.txt

# Initialize database
python -m app.init_db

# Run server
uvicorn app.main:app --reload --port 8000
```

## API Endpoints

See main [README.md](../README.md) for full API documentation.

Interactive docs available at: `http://localhost:8000/docs`

## Architecture

See main [README.md](../README.md) for project structure.

### Services

- **Query Orchestrator**: Coordinates query-to-dataset pipeline
- **NL Parser**: Extracts intent from natural language
- **Query Planner**: Generates optimized SQL
- **Query Validator**: Ensures query safety
- **Cohort Identifier**: Filters subjects by criteria
- **Dataset Assembly**: Assembles analysis-ready datasets
- **Export Engine**: Generates CSV/Parquet/JSON files
- **FHIR Connector**: Integrates with EHR systems
- **Audit Log**: HIPAA-compliant logging

## License

MIT
