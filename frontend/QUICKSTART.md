# Quick Start Guide

## Prerequisites

1. **Backend API**: Ensure the backend is running at `http://localhost:8000`
2. **Node.js**: Version 18 or higher
3. **npm**: Comes with Node.js

## Setup Steps

### 1. Install Dependencies

```bash
cd frontend
npm install
```

### 2. Configure Environment

Create a `.env.local` file in the frontend directory:

```bash
NEXT_PUBLIC_API_URL=http://localhost:8000
```

### 3. Start Development Server

```bash
npm run dev
```

The application will be available at [http://localhost:3000](http://localhost:3000)

## First Time Usage

### 1. Login

Navigate to `http://localhost:3000` and you'll be redirected to the login page.

**Test Credentials** (if using the backend's test data):
- Username: `researcher1`
- Password: `password123`

### 2. Submit a Query

Once logged in, you'll see the dashboard with a query input area.

**Example Queries**:
```
Find all Parkinson's patients with DBS surgery

Patients with diabetes and hypertension over age 50

Subjects with MRI scans and cognitive test scores

Cancer patients who received chemotherapy in 2023
```

### 3. Review Results

After submitting a query:
1. **Parsed Intent** will show how the system understood your query
2. **Confidence Score** indicates how certain the system is (>70% required)
3. If confidence is low, you'll be asked to clarify

### 4. Explore Dataset

Once the query completes:
- **Overview**: See row count, column count, and data sources
- **Schema**: View column definitions and data types
- **Preview**: Browse the first 20 rows with pagination
- **Provenance**: See the original query and executed SQL

### 5. Export Data

Choose your preferred format:
- **CSV**: For Excel and general use
- **Parquet**: For big data analytics (Spark, Pandas)
- **JSON**: For web applications

Click "Export" and download the generated files.

## Troubleshooting

### Cannot Connect to Backend

**Error**: Network errors or 404 responses

**Solution**:
1. Verify backend is running: `curl http://localhost:8000/api/health`
2. Check `.env.local` has correct `NEXT_PUBLIC_API_URL`
3. Restart the frontend dev server

### Login Fails

**Error**: "Login failed" or 401 Unauthorized

**Solution**:
1. Verify credentials are correct
2. Check backend logs for authentication errors
3. Ensure backend database has user records

### Session Expires Quickly

**Behavior**: Logged out after a few minutes

**Explanation**: Session timeout is set to 30 minutes of inactivity. Any mouse movement, keyboard input, or scrolling resets the timer.

### Query Returns Low Confidence

**Behavior**: Asked to clarify query

**Solution**:
1. Be more specific in your query
2. Use medical terminology (ICD-10 codes, procedure names)
3. Include specific criteria (age ranges, date ranges)

**Example**:
- ❌ "Find patients with brain problems"
- ✅ "Find patients with Parkinson's disease (G20) who had DBS surgery"

### Dataset Preview Shows "NULL"

**Behavior**: Some cells show "NULL" instead of values

**Explanation**: This indicates missing data in the source. The system handles missing values according to the configured strategy (UseNull, UseDefault, UseMean, or Exclude).

## Development Tips

### Hot Reload

The development server supports hot reload. Changes to components will automatically refresh the browser.

### TypeScript Errors

Run type checking:
```bash
npm run build
```

This will show any TypeScript errors before deployment.

### Linting

Check code style:
```bash
npm run lint
```

### Clear Cache

If you encounter strange behavior:
```bash
rm -rf .next
npm run dev
```

## API Endpoints Reference

| Endpoint | Method | Purpose |
|----------|--------|---------|
| `/api/auth/login` | POST | User login |
| `/api/auth/logout` | POST | User logout |
| `/api/auth/me` | GET | Get current user |
| `/api/query` | POST | Submit NL query |
| `/api/dataset/{id}` | GET | Get dataset details |
| `/api/dataset/{id}/download` | GET | Download dataset |

## Next Steps

1. **Explore Sample Queries**: Try different types of queries to understand the system
2. **Review Provenance**: Check the executed SQL to understand how queries are translated
3. **Export Formats**: Try different export formats to see which works best for your workflow
4. **Read Documentation**: See `README.md` for detailed component documentation

## Getting Help

- Check backend logs for API errors
- Review browser console for frontend errors
- Verify network requests in browser DevTools
- Ensure all environment variables are set correctly

## Production Deployment

For production deployment:

1. Build the application:
```bash
npm run build
```

2. Start production server:
```bash
npm run start
```

3. Or deploy to Vercel/Netlify:
```bash
# Vercel
vercel deploy

# Netlify
netlify deploy --prod
```

Make sure to set environment variables in your deployment platform.
