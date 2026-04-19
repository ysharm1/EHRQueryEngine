# EHR Query Engine

> Ask your clinical data anything. Get a structured dataset back.

A natural language query engine for biomedical research. Researchers type plain English questions — the system parses intent, queries the database, and returns a downloadable, analysis-ready dataset. No SQL. No data formatting. No waiting.

**Live Demo → [ehrqueryengine-frontend.onrender.com](https://ehrqueryengine-frontend.onrender.com)**

---

## What It Does

```
"Find all Parkinson's patients with DBS surgery"
        ↓
  Parse intent (cohort criteria + variables)
        ↓
  Query database (subjects, procedures, observations)
        ↓
  Return CSV / JSON / Parquet + provenance
```

Researchers go from question to dataset in seconds, not weeks.

---

## Stack

| Layer | Tech |
|---|---|
| Frontend | Next.js 16, React 19, TypeScript, TailwindCSS |
| Backend | FastAPI, Python 3.11 |
| Analytics DB | DuckDB |
| Metadata DB | SQLite |
| NLP | OpenAI / Anthropic (demo mode works without API keys) |
| Deploy | Render.com |

---

## Run Locally

```bash
git clone https://github.com/ysharm1/EHRQueryEngine.git
cd EHRQueryEngine
chmod +x setup.sh && ./setup.sh
```

Then in two terminals:

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

Open **http://localhost:3001** — no login required.

---

## Docker

```bash
docker-compose up --build
```

Open **http://localhost:3000**

---

## Deploy to Render

The repo includes `render.yaml` for one-click deployment:

1. Go to [render.com](https://render.com) → New → Blueprint
2. Connect `ysharm1/EHRQueryEngine`
3. Click Apply

Both services deploy automatically.

---

## API

| Method | Endpoint | Auth | Description |
|---|---|---|---|
| `POST` | `/api/demo/query` | None | **Public** NL query endpoint |
| `POST` | `/api/query` | JWT | Authenticated query |
| `POST` | `/api/upload` | JWT | Upload CSV/Excel data |
| `GET` | `/api/tables` | JWT | List available tables |
| `GET` | `/api/dataset/{id}` | JWT | Get dataset metadata |
| `GET` | `/api/dataset/{id}/download` | JWT | Download files |
| `POST` | `/api/auth/login` | None | Login |
| `GET` | `/api/health` | None | Health check |

Interactive docs: `http://localhost:8000/docs`

---

## Example Queries

- `Find all Parkinson's patients with DBS surgery`
- `Show subjects with diabetes and hypertension`
- `Patients with MRI imaging data`
- `All subjects in the treatment group`
- `Find subjects with observations`

---

## Enable Full NLP (Optional)

By default the system runs in demo mode (pattern matching). To enable real LLM parsing, add to `backend/.env`:

```bash
OPENAI_API_KEY=sk-...
# or
ANTHROPIC_API_KEY=sk-ant-...
LLM_PROVIDER=openai
```

---

## Project Structure

```
EHRQueryEngine/
├── backend/
│   ├── app/
│   │   ├── api/routes.py          # All API endpoints
│   │   ├── services/
│   │   │   ├── nl_parser.py       # NL → structured intent
│   │   │   ├── query_orchestrator.py  # Pipeline coordinator
│   │   │   ├── cohort.py          # Patient cohort filtering
│   │   │   ├── dataset_assembly.py    # Multi-source assembly
│   │   │   ├── export_engine.py   # CSV/Parquet/JSON export
│   │   │   └── audit_log.py       # HIPAA audit logging
│   │   ├── models/                # SQLAlchemy models
│   │   ├── config.py
│   │   ├── database.py
│   │   └── main.py
│   ├── requirements.txt
│   └── Dockerfile
├── frontend/
│   ├── app/
│   │   ├── demo/page.tsx          # Public demo UI
│   │   └── dashboard/page.tsx     # Full dashboard
│   ├── components/
│   │   ├── chat-interface.tsx
│   │   ├── data-upload.tsx
│   │   ├── dataset-explorer.tsx
│   │   └── dataset-export.tsx
│   └── Dockerfile
├── render.yaml                    # One-click Render deployment
├── docker-compose.yml
└── setup.sh
```

---

## License

MIT
