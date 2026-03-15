# Testing Guide - Research Dataset Builder

Complete testing guide for end-to-end, integration, security, and performance testing.

## Prerequisites

- Backend running at http://localhost:8000
- Frontend running at http://localhost:3000
- PostgreSQL database initialized
- Sample data loaded
- Test user accounts created

## Quick Test Setup

```bash
# 1. Start backend
cd backend
python -m app.init_db  # Initialize database with sample data
uvicorn app.main:app --reload

# 2. Start frontend (in another terminal)
cd frontend
npm run dev

# 3. Access application
# Open http://localhost:3000 in your browser
```

## Test Accounts

| Username   | Password    | Role       | Purpose                    |
|------------|-------------|------------|----------------------------|
| admin      | admin123    | Admin      | Full system access         |
| researcher | password123 | Researcher | Query and dataset creation |

## Task 24.1: End-to-End Integration Tests

### Test 1: Complete Query Flow (NL Query → Dataset Export)

**Steps:**
1. Login as researcher
2. Navigate to dashboard
3. Enter query: "Find all Parkinson's patients with DBS surgery"
4. Submit query
5. Verify parsed intent displays
6. Verify confidence score ≥ 70%
7. Wait for dataset generation
8. Verify dataset explorer shows data
9. Select CSV export format
10. Click export button
11. Download dataset files

**Expected Results:**
- ✅ Login successful, redirected to dashboard
- ✅ Query submitted without errors
- ✅ Parsed intent shows diagnosis and procedure filters
- ✅ Confidence score displayed (green if ≥70%)
- ✅ Dataset generated successfully
- ✅ Dataset preview shows rows and columns
- ✅ Metadata displays correctly (row count, column count, sources)
- ✅ Export generates files (data.csv, schema.json, query_logic.sql)
- ✅ Files download successfully

**Test Script:**
```bash
# Automated test using curl
curl -X POST http://localhost:8000/api/auth/login \
  -H "Content-Type: application/json" \
  -d '{"username": "researcher", "password": "password123"}' \
  | jq -r '.access_token' > token.txt

TOKEN=$(cat token.txt)

curl -X POST http://localhost:8000/api/query \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "query_text": "Find all Parkinsons patients with DBS surgery",
    "data_source_ids": ["clinical_db"],
    "output_format": "CSV"
  }' | jq

# Check dataset
DATASET_ID=$(curl -X POST http://localhost:8000/api/query \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"query_text": "Parkinsons patients", "data_source_ids": ["clinical_db"], "output_format": "CSV"}' \
  | jq -r '.dataset_id')

curl http://localhost:8000/api/dataset/$DATASET_ID \
  -H "Authorization: Bearer $TOKEN" | jq
```

### Test 2: FHIR Data Ingestion → Query → Export

**Steps:**
1. Configure FHIR endpoint (if available)
2. Trigger FHIR data ingestion
3. Wait for ingestion to complete
4. Submit query using FHIR data
5. Verify dataset includes FHIR-sourced data
6. Export and verify provenance

**Expected Results:**
- ✅ FHIR ingestion starts successfully
- ✅ Data transformed to canonical schema
- ✅ Query includes FHIR data
- ✅ Provenance tracks FHIR source

**Test Script:**
```bash
curl -X POST http://localhost:8000/api/fhir/ingest \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "fhir_base_url": "https://fhir.example.com",
    "resource_types": ["Patient", "Condition", "Procedure"]
  }' | jq
```

### Test 3: Multi-Source Dataset Assembly

**Steps:**
1. Submit query requiring multiple data sources
2. Example: "Patients with diabetes, include MRI features and medication history"
3. Verify data from subjects, observations, imaging, procedures
4. Check schema includes columns from all sources
5. Verify referential integrity

**Expected Results:**
- ✅ Query parses multiple variable sources
- ✅ Dataset includes data from all sources
- ✅ Foreign keys maintained correctly
- ✅ No orphaned records

### Test 4: Authentication and Authorization Enforcement

**Steps:**
1. Attempt to access /dashboard without login → redirected to /login
2. Login with invalid credentials → error message
3. Login with valid credentials → access granted
4. Access protected endpoint without token → 401 error
5. Access endpoint with expired token → token refresh
6. Logout → token cleared, redirected to login

**Expected Results:**
- ✅ Protected routes require authentication
- ✅ Invalid credentials rejected
- ✅ Valid credentials accepted
- ✅ Token refresh works automatically
- ✅ Logout clears session

**Test Script:**
```bash
# Test without auth
curl http://localhost:8000/api/dataset/test-id
# Expected: 401 Unauthorized

# Test with auth
curl http://localhost:8000/api/dataset/test-id \
  -H "Authorization: Bearer $TOKEN"
# Expected: 200 OK or 404 Not Found
```

### Test 5: Error Handling and Recovery

**Steps:**
1. Submit invalid query (gibberish)
2. Submit query with low confidence
3. Trigger database connection error (stop PostgreSQL)
4. Trigger timeout (very complex query)
5. Submit query with invalid data source

**Expected Results:**
- ✅ Invalid query returns error message
- ✅ Low confidence triggers clarification request
- ✅ Database error triggers retry logic
- ✅ Timeout cancels query with message
- ✅ Invalid data source returns error

## Task 24.2: Security and Compliance Verification

### Test 1: Data Encryption at Rest and in Transit

**Verification Steps:**
1. Check PostgreSQL SSL configuration
2. Verify TLS enabled for API (HTTPS)
3. Check DuckDB encryption enabled
4. Verify file storage encryption

**Commands:**
```bash
# Check PostgreSQL SSL
psql "postgresql://user:pass@localhost:5432/research_dataset_builder?sslmode=require"

# Check API TLS
curl -v https://localhost:8000/api/health

# Check environment variables
grep ENCRYPTION backend/.env
```

**Expected Results:**
- ✅ PostgreSQL accepts SSL connections only
- ✅ API serves over HTTPS
- ✅ DuckDB encryption enabled
- ✅ File encryption configured

### Test 2: Audit Logging for All Operations

**Verification Steps:**
1. Perform various operations (login, query, export)
2. Query audit_logs table
3. Verify all operations logged
4. Check integrity checksums
5. Verify 7-year retention policy configured

**SQL Query:**
```sql
SELECT * FROM audit_logs 
ORDER BY timestamp DESC 
LIMIT 10;

-- Verify integrity
SELECT log_id, action, integrity_checksum 
FROM audit_logs 
WHERE user_id = 'test-user-id';
```

**Expected Results:**
- ✅ All operations logged with timestamp
- ✅ User ID captured for all actions
- ✅ Integrity checksums present
- ✅ No gaps in log sequence

### Test 3: RBAC Enforcement

**Verification Steps:**
1. Login as Read_Only user
2. Attempt to create dataset → should fail
3. Login as Researcher
4. Create dataset → should succeed
5. Login as Admin
6. Access admin endpoints → should succeed

**Expected Results:**
- ✅ Read_Only cannot create datasets
- ✅ Researcher can create datasets
- ✅ Admin has full access
- ✅ 403 Forbidden for unauthorized actions

### Test 4: Session Timeout Behavior

**Verification Steps:**
1. Login and get token
2. Wait 30 minutes (or adjust timeout for testing)
3. Attempt API call
4. Verify session expired message
5. Verify redirect to login

**Test Script:**
```bash
# Set short timeout for testing (in backend config)
JWT_ACCESS_TOKEN_EXPIRE_MINUTES=1

# Login
TOKEN=$(curl -X POST http://localhost:8000/api/auth/login \
  -H "Content-Type: application/json" \
  -d '{"username": "researcher", "password": "password123"}' \
  | jq -r '.access_token')

# Wait 2 minutes
sleep 120

# Try to use expired token
curl http://localhost:8000/api/dataset/test \
  -H "Authorization: Bearer $TOKEN"
# Expected: 401 Unauthorized
```

**Expected Results:**
- ✅ Token expires after configured time
- ✅ Expired token rejected
- ✅ User prompted to re-authenticate

## Task 24.3: Performance Testing

### Test 1: Query Execution Time (Target: 95% under 30 seconds)

**Test Queries:**
1. Simple query: "Parkinson's patients" (expected: <5s)
2. Medium query: "Patients with diabetes and hypertension" (expected: <15s)
3. Complex query: "Patients over 65 with multiple conditions and MRI data" (expected: <30s)

**Test Script:**
```bash
# Measure query time
time curl -X POST http://localhost:8000/api/query \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "query_text": "Parkinsons patients with DBS surgery",
    "data_source_ids": ["clinical_db"],
    "output_format": "CSV"
  }'
```

**Expected Results:**
- ✅ Simple queries: <5 seconds
- ✅ Medium queries: <15 seconds
- ✅ Complex queries: <30 seconds
- ✅ 95% of queries under 30 seconds

### Test 2: FHIR Ingestion Rate (Target: 10,000 resources/minute)

**Test Steps:**
1. Prepare 10,000 FHIR resources
2. Trigger ingestion
3. Measure time to completion
4. Calculate resources per minute

**Expected Results:**
- ✅ Ingestion rate ≥ 10,000 resources/minute
- ✅ No errors during ingestion
- ✅ All resources transformed correctly

### Test 3: Dataset Assembly Time (Target: 100,000 rows in 2 minutes)

**Test Steps:**
1. Create query that generates 100,000 rows
2. Measure assembly time
3. Verify all rows included
4. Check memory usage

**Expected Results:**
- ✅ Assembly time ≤ 2 minutes
- ✅ All rows included
- ✅ Memory usage reasonable (<4GB)

### Test 4: Concurrent User Load (Target: 1000 concurrent users)

**Load Test Script:**
```bash
# Install Apache Bench
sudo apt-get install apache2-utils

# Run load test
ab -n 1000 -c 100 -H "Authorization: Bearer $TOKEN" \
  http://localhost:8000/api/health

# Or use k6
k6 run load-test.js
```

**k6 Load Test Script (load-test.js):**
```javascript
import http from 'k6/http';
import { check, sleep } from 'k6';

export let options = {
  stages: [
    { duration: '2m', target: 100 },
    { duration: '5m', target: 1000 },
    { duration: '2m', target: 0 },
  ],
};

export default function () {
  let response = http.get('http://localhost:8000/api/health');
  check(response, {
    'status is 200': (r) => r.status === 200,
  });
  sleep(1);
}
```

**Expected Results:**
- ✅ System handles 1000 concurrent users
- ✅ Response time <1s for health check
- ✅ No errors under load
- ✅ CPU usage <80%
- ✅ Memory usage stable

## Task 24.4: Final Checkpoint

### Pre-Deployment Checklist

- [ ] All end-to-end tests pass
- [ ] Security tests pass
- [ ] Performance tests meet targets
- [ ] No critical bugs
- [ ] Documentation complete
- [ ] Environment variables configured
- [ ] Database migrations run
- [ ] Sample data loaded
- [ ] Backup strategy in place
- [ ] Monitoring configured
- [ ] Alerts set up
- [ ] SSL certificates valid
- [ ] CORS configured correctly
- [ ] Rate limiting enabled
- [ ] Audit logging verified

### Test Results Summary

| Test Category | Tests Run | Passed | Failed | Notes |
|---------------|-----------|--------|--------|-------|
| End-to-End    | 5         | -      | -      | -     |
| Security      | 4         | -      | -      | -     |
| Performance   | 4         | -      | -      | -     |
| **Total**     | **13**    | **-**  | **-**  | **-** |

### Known Issues

Document any known issues or limitations:

1. **Issue**: [Description]
   - **Severity**: Critical/High/Medium/Low
   - **Workaround**: [If available]
   - **Fix ETA**: [Date]

### Sign-Off

- [ ] **QA Lead**: _________________ Date: _______
- [ ] **Security Officer**: _________________ Date: _______
- [ ] **Performance Engineer**: _________________ Date: _______
- [ ] **Product Owner**: _________________ Date: _______

## Automated Testing

### Running All Tests

```bash
# Backend tests
cd backend
pytest

# Frontend tests (when implemented)
cd frontend
npm test

# Integration tests
./run_integration_tests.sh

# Performance tests
./run_performance_tests.sh
```

### Continuous Integration

Add to CI/CD pipeline:

```yaml
# .github/workflows/test.yml
name: Test Suite

on: [push, pull_request]

jobs:
  test:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v2
      - name: Set up Python
        uses: actions/setup-python@v2
        with:
          python-version: 3.11
      - name: Install dependencies
        run: |
          cd backend
          pip install -r requirements.txt
      - name: Run tests
        run: |
          cd backend
          pytest
      - name: Run integration tests
        run: ./run_integration_tests.sh
```

## Troubleshooting

### Common Issues

**Issue: Database connection failed**
- Check PostgreSQL is running: `pg_isready`
- Verify credentials in .env
- Check firewall rules

**Issue: Token expired**
- Refresh token or re-login
- Check JWT_ACCESS_TOKEN_EXPIRE_MINUTES setting

**Issue: Query timeout**
- Reduce query complexity
- Add filters to narrow results
- Check database indexes

**Issue: FHIR ingestion failed**
- Verify FHIR endpoint URL
- Check authentication token
- Verify network connectivity

## Next Steps

After all tests pass:

1. Review test results with team
2. Address any failed tests
3. Document known issues
4. Update deployment checklist
5. Proceed with production deployment
6. Set up monitoring and alerts
7. Schedule post-deployment verification

## Support

For testing support:
- **Documentation**: See README.md and IMPLEMENTATION_STATUS.md
- **Issues**: Create GitHub issue with test results
- **Questions**: Contact development team
