# Research Dataset Builder

A platform that enables biomedical researchers to generate structured, analysis-ready datasets from multimodal clinical data sources using natural language queries.

## Features

- Natural language query interface (LLM-powered with demo mode fallback)
- Multi-source data integration (EHR/FHIR, CSV upload, imaging metadata)
- Canonical research schema for data standardization
- Reproducible query generation with complete provenance
- HIPAA-compliant audit logging with integrity checksums
- Multiple export formats (CSV, Parquet, JSON)
- Confidence scoring with clarification requests
- Dataset explorer with pagination and metadata
- JWT authentication with automatic token refresh
- Role-based access control (Admin, Researcher, Data_Analyst, Read_Only)

## Architecture

- **Frontend**: Next.js 16 / React 19, TypeScript, TailwindCSS, TanStack Query
- **Backend**: FastAPI, Python 3.11
- **Databases**: SQLite (metadata) + DuckDB (analytics warehouse)
- **Auth**: JWT (python-jose) + bcrypt password hashing
- **LLM**: OpenAI or Anthropic (optional — demo mode works without API keys)

## Quick Start

### Option 1: Automated Setup

```bash
chmod +x setup.sh
./setup.sh
```

Then follow the printed instructions, or:

```bash
# Terminal 1 — backend
cd backend
python3 -m app.init_db
python3 -m uvicorn app.main:app --reload --port 8000

# Terminal 2 — frontend
cd frontend
npm install
npm run dev -- -p 3001
```

Open **http://localhost:3001** and sign in:

| Username     | Password       | Role       |
|--------------|----------------|------------|
| admin        | admin123       | Admin      |
| researcher   | researcher123  | Researcher |

### Option 2: Docker

```bash
docker-compose up --build
```

Open **http://localhost:3000**

## Project Structure

```
.
├── backend/
│   ├── app/
│   │   ├── main.py              # FastAPI application entry
│   │   ├── config.py            # Settings (pydantic-settings)
│   │   ├── database.py          # SQLite + DuckDB connections
│   │   ├── init_db.py           # DB init + sample data + password migration
│   │   ├── models/              # SQLAlchemy models
│   │   ├── api/routes.py        # All 14 API endpoints
│   │   └── services/            # Core business logic
│   │       ├── auth.py          # JWT + bcrypt authentication
│   │       ├── nl_parser.py     # Natural language → structured intent
│   │       ├── query_planner.py # Intent → optimized query plan
│   │       ├── query_validator.py # Read-only safety checks
│   │       ├── cohort.py        # Patient cohort identification
│   │       ├── dataset_assembly.py # Multi-source dataset assembly
│   │       ├── export_engine.py # CSV/Parquet/JSON export
│   │       ├── query_orchestrator.py # Full pipeline coordinator
│   │       ├── fhir_connector.py # FHIR API integration
│   │       ├── smart_schema_detector.py # Auto schema inference
│   │       ├── schema_mapper.py # Schema transformation
│   │       └── audit_log.py     # HIPAA audit logging
│   ├── requirements.txt
│   ├── Dockerfile
│   └── .env.example
├── frontend/
│   ├── app/                     # Next.js app router (login, dashboard)
│   ├── components/              # React components
│   │   ├── chat-interface.tsx   # NL query input
│   │   ├── dataset-explorer.tsx # Dataset preview + pagination
│   │   ├── dataset-export.tsx   # Export format selection + download
│   │   ├── data-upload.tsx      # CSV/Excel file upload
│   │   └── ...
│   ├── lib/                     # Auth context, API client, types
│   ├── Dockerfile
│   └── .env.local
├── docker-compose.yml
├── setup.sh                     # One-time setup script
└── README.md
```

## API Endpoints

| Method | Endpoint                          | Description                    |
|--------|-----------------------------------|--------------------------------|
| POST   | `/api/auth/login`                 | User login                     |
| POST   | `/api/auth/logout`                | User logout                    |
| POST   | `/api/auth/refresh`               | Refresh access token           |
| GET    | `/api/auth/me`                    | Get current user info          |
| POST   | `/api/query`                      | Submit natural language query   |
| GET    | `/api/datasets`                   | List user's datasets           |
| GET    | `/api/query/{id}/status`          | Check query status             |
| GET    | `/api/dataset/{id}`               | Get dataset (rows + schema)    |
| GET    | `/api/dataset/{id}/files`         | List export files              |
| GET    | `/api/dataset/{id}/download`      | Download export file           |
| POST   | `/api/upload`                     | Upload CSV/Excel data          |
| GET    | `/api/tables`                     | List available tables          |
| POST   | `/api/fhir/ingest`                | Trigger FHIR data ingestion    |
| GET    | `/api/health`                     | Health check                   |

## Sample Queries

- "Find all Parkinson's patients"
- "Parkinson's patients with DBS surgery"
- "Patients over 65 with diabetes, include medication history"
- "Subjects with MRI imaging features"

## Environment Variables

See `backend/.env.example` for all backend settings. Key variables:

- `JWT_SECRET_KEY` — generated automatically by `setup.sh`
- `LLM_PROVIDER` / `OPENAI_API_KEY` / `ANTHROPIC_API_KEY` — optional, demo mode works without
- `CORS_ORIGINS` — allowed frontend origins
- `FHIR_BASE_URL` / `FHIR_AUTH_TOKEN` — optional FHIR integration

## License

MIT
