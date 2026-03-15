# Quick Start Guide - Research Dataset Builder

Get the Research Dataset Builder running in 5 minutes!

## Prerequisites

- Python 3.11+
- PostgreSQL 15+ (or use Docker)
- OpenAI or Anthropic API key

## Option 1: Docker (Recommended)

### 1. Configure Environment

```bash
cp backend/.env.example backend/.env
```

Edit `backend/.env` and add your API key:
```
OPENAI_API_KEY=your-key-here
# OR
ANTHROPIC_API_KEY=your-key-here
LLM_PROVIDER=openai  # or anthropic

JWT_SECRET_KEY=your-secret-key-change-this
```

### 2. Start Services

```bash
docker-compose up -d
```

### 3. Initialize Database

```bash
docker-compose exec backend python -m app.init_db
```

### 4. Test the API

```bash
curl http://localhost:8000/api/health
```

You should see: `{"status":"healthy","environment":"development"}`

## Option 2: Local Development

### 1. Install PostgreSQL

Make sure PostgreSQL is running on localhost:5432

### 2. Set Up Python Environment

```bash
cd backend
python -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate
pip install -r requirements.txt
```

### 3. Configure Environment

```bash
cp .env.example .env
```

Edit `.env` with your settings (API keys, database credentials)

### 4. Initialize Database

```bash
python -m app.init_db
```

### 5. Start Server

```bash
uvicorn app.main:app --reload
```

### 6. Test the API

Open http://localhost:8000/docs in your browser

## Using the API

### 1. Login

```bash
curl -X POST http://localhost:8000/api/auth/login \
  -H "Content-Type: application/json" \
  -d '{
    "username": "researcher",
    "password": "password123"
  }'
```

Save the `access_token` from the response.

### 2. Submit a Natural Language Query

```bash
curl -X POST http://localhost:8000/api/query \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer YOUR_ACCESS_TOKEN" \
  -d '{
    "query_text": "Find all Parkinson patients with DBS surgery",
    "output_format": "CSV"
  }'
```

### 3. Get Dataset Metadata

```bash
curl http://localhost:8000/api/dataset/DATASET_ID \
  -H "Authorization: Bearer YOUR_ACCESS_TOKEN"
```

### 4. Download Dataset

```bash
curl http://localhost:8000/api/dataset/DATASET_ID/download \
  -H "Authorization: Bearer YOUR_ACCESS_TOKEN" \
  --output dataset.zip
```

## Sample Queries to Try

1. **Simple cohort query**:
   - "Parkinson's patients"
   - "Patients over 65"
   - "Subjects with diabetes"

2. **With procedures**:
   - "Parkinson's patients with DBS surgery"
   - "Patients with knee replacement"

3. **With variables**:
   - "Diabetes patients, include medication history"
   - "Parkinson's patients with MRI data"

4. **Complex queries**:
   - "Patients over 65 with diabetes and hypertension, include medication history and lab results"
   - "Parkinson's patients with DBS surgery within the last year, include MRI features"

## Default Users

The system comes with two pre-configured users:

| Username   | Password    | Role       |
|------------|-------------|------------|
| admin      | admin123    | Admin      |
| researcher | password123 | Researcher |

## Sample Data

The database is initialized with:
- 5 subjects (patients)
- 3 procedures per subject
- Multiple observations per subject
- Imaging features for some subjects

## API Documentation

Once the server is running, visit:
- **Interactive API Docs**: http://localhost:8000/docs
- **Alternative Docs**: http://localhost:8000/redoc

## Troubleshooting

### Database Connection Error

Make sure PostgreSQL is running:
```bash
# Check if PostgreSQL is running
pg_isready

# Start PostgreSQL (macOS with Homebrew)
brew services start postgresql@15

# Start PostgreSQL (Linux)
sudo systemctl start postgresql
```

### LLM API Error

Make sure your API key is set correctly in `.env`:
```bash
# Check if key is set
grep API_KEY backend/.env
```

### Port Already in Use

If port 8000 is already in use:
```bash
# Use a different port
uvicorn app.main:app --reload --port 8001
```

### Docker Issues

```bash
# View logs
docker-compose logs backend

# Restart services
docker-compose restart

# Rebuild containers
docker-compose up -d --build
```

## Next Steps

1. **Explore the API**: Use the interactive docs at http://localhost:8000/docs
2. **Try different queries**: Test the natural language parser with various queries
3. **Check the data**: Connect to PostgreSQL and explore the canonical schema
4. **Build the frontend**: Implement the React/Next.js UI (see Task 21 in tasks.md)
5. **Run tests**: Implement and run unit tests for core services
6. **Configure security**: Set up encryption and TLS for production

## Getting Help

- **Design Document**: `.kiro/specs/research-dataset-builder/design.md`
- **Requirements**: `.kiro/specs/research-dataset-builder/requirements.md`
- **Implementation Status**: `IMPLEMENTATION_STATUS.md`
- **Full README**: `README.md`

## Production Deployment

Before deploying to production:

1. ✅ Change default passwords
2. ✅ Use strong JWT secret key
3. ✅ Configure TLS/HTTPS
4. ✅ Enable database encryption
5. ✅ Set up proper backup strategy
6. ✅ Configure monitoring and logging
7. ✅ Review and test security settings
8. ✅ Set up rate limiting
9. ✅ Configure CORS properly
10. ✅ Review HIPAA compliance requirements

Happy building! 🚀
