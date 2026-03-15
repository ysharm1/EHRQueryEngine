# How to Launch Your Research Dataset Builder

## Understanding the Architecture (Simple Version)

### What You Have Now (Development)
```
Your Computer:
┌─────────────────────────────────────────┐
│  You open: http://localhost:3001       │  ← Browser (what you see)
│  ↓ sends requests to ↓                 │
│  Backend: localhost:8000                │  ← Python server (running in terminal)
│  ↓ reads from ↓                         │
│  Databases: ./data/                     │  ← Files on your computer
│    - metadata.db                        │
│    - warehouse.duckdb                   │
└─────────────────────────────────────────┘
```

### What You'll Have (Production)
```
Cloud Server (AWS/Azure/GCP):
┌─────────────────────────────────────────┐
│  Backend Server (running 24/7)         │
│  ↓                                      │
│  Databases (on server)                  │
│    - PostgreSQL                         │
│    - DuckDB                             │
│  ↓ (optional)                           │
│  Hospital EHR System                    │
└─────────────────────────────────────────┘
         ↑
         │ Internet
         │
Users' Computers:
┌─────────────────────────────────────────┐
│  Browser: https://your-domain.com       │  ← Just the website
└─────────────────────────────────────────┘
```

**Key Point**: The database is NEVER in a browser tab. It runs on a server, and your backend connects to it automatically.

---

## The 3 Paths to Launch

### Path 1: Quick Demo (What You Have Now)
**Time**: Already done!  
**Cost**: Free  
**Use for**: Showing to colleagues, testing

**How it works:**
1. You run the servers on your computer
2. You open localhost:3001 in your browser
3. You demo the system
4. When you close your computer, it stops working

**Limitations:**
- Only works on your computer
- No one else can access it
- Data is local only

---

### Path 2: Cloud Deployment (Recommended)
**Time**: 1-2 days  
**Cost**: $100-200/month  
**Use for**: Production use, multiple users

**How it works:**
1. You upload your code to AWS/Azure/Google Cloud
2. They run it on their servers 24/7
3. You get a URL (e.g., https://research-data.yourcompany.com)
4. Anyone with credentials can access it from anywhere

**Steps:**

#### Step 1: Choose a Cloud Provider
- **AWS** (most popular)
- **Azure** (good for Microsoft shops)
- **Google Cloud** (good for Google shops)

#### Step 2: Deploy Your Application
```bash
# Option A: Use their deployment tools (easiest)
# AWS: Elastic Beanstalk
# Azure: App Service
# Google: Cloud Run

# Option B: Use Docker (more control)
docker build -t research-dataset-builder .
docker push your-registry/research-dataset-builder
```

#### Step 3: Configure Database Connection
Your backend will automatically connect to the cloud database. You just need to set environment variables:

```bash
# In cloud console, set these:
POSTGRES_HOST=your-cloud-db.amazonaws.com
POSTGRES_PASSWORD=secure-password
DUCKDB_PATH=/data/warehouse.duckdb
```

#### Step 4: Get a Domain Name
- Buy a domain (e.g., research-data.com) for $10-15/year
- Or use a subdomain from your organization (e.g., research-data.hospital.edu)

#### Step 5: Enable HTTPS
Cloud providers do this automatically. Just click "Enable SSL" in their console.

---

### Path 3: Hospital Server (Most Control)
**Time**: 1 week  
**Cost**: $3K-7K one-time  
**Use for**: Strict security requirements, on-premises data

**How it works:**
1. Your IT department gives you a server
2. You install your application on it
3. It runs on your hospital network
4. Users access it via hospital network

**Steps:**

#### Step 1: Get a Server
Talk to your IT department:
- "I need a Linux server (Ubuntu 22.04)"
- "8GB RAM, 4 CPU cores, 100GB storage"
- "Access to hospital network"

#### Step 2: Install Your Application
```bash
# SSH into the server
ssh user@your-server

# Copy your code
scp -r /path/to/your/code user@your-server:/app

# Install dependencies
cd /app
pip install -r backend/requirements.txt
npm install --prefix frontend

# Start the application
./launch.sh
```

#### Step 3: Configure Firewall
Your IT department will:
- Open port 443 (HTTPS)
- Set up SSL certificate
- Configure access controls

---

## How Data Gets Into the System

You have 3 options:

### Option 1: Manual Upload (Simplest)
```
Researcher → Uploads CSV file → System imports → Ready to query
```

**How to implement:**
- Add a file upload button to the frontend
- Backend reads the CSV and loads it into DuckDB
- Users can now query that data

**Pros**: Simple, no IT involvement  
**Cons**: Manual work, data can get stale

---

### Option 2: Connect to Hospital Database (Automatic)
```
Your System → Connects to hospital EHR → Syncs data automatically → Ready to query
```

**How it works:**
1. Your IT department gives you database credentials
2. You configure the connection in your backend
3. Your system automatically pulls data every hour/day
4. Users always have fresh data

**Configuration:**
```bash
# In your .env file:
FHIR_BASE_URL=https://fhir.hospital.edu/api/FHIR/R4
FHIR_AUTH_TOKEN=your-token-here

# Or direct database connection:
EHR_DB_HOST=ehr-database.hospital.edu
EHR_DB_USER=readonly_user
EHR_DB_PASSWORD=secure-password
```

**Your backend code (already written!) will:**
```python
# This code is already in fhir_connector.py
connector = FHIRConnector(config)
patients = connector.query_all_pages(query)
canonical_data = connector.transform_to_canonical(patients)
# Save to your database
```

**Pros**: Automatic, always fresh data  
**Cons**: Requires IT department help

---

### Option 3: Hybrid (Best of Both)
```
Automatic sync for main data + Manual upload for special datasets
```

---

## Step-by-Step Launch Plan

### Week 1: Decision & Setup
- [ ] Decide: Cloud or On-Premises?
- [ ] If Cloud: Sign up for AWS/Azure/GCP
- [ ] If On-Premises: Request server from IT
- [ ] Decide: How will data get in? (Upload vs Auto-sync)

### Week 2: Deployment
- [ ] Deploy your application
- [ ] Set up database
- [ ] Configure environment variables
- [ ] Test that it works

### Week 3: Data Connection
- [ ] If Auto-sync: Get credentials from IT
- [ ] Configure FHIR connector or database connection
- [ ] Run initial data load
- [ ] Verify data is accessible

### Week 4: User Setup & Launch
- [ ] Create user accounts
- [ ] Train users (1-hour session)
- [ ] Go live!
- [ ] Monitor for issues

---

## FAQ

### Q: "The database will be in another tab in a browser?"
**A**: No! The database never runs in a browser. It runs on a server. The browser only shows the website interface.

### Q: "How will the website gather data?"
**A**: Your backend server connects to the database automatically using the code that's already written (fhir_connector.py, database.py). Users never see this - it happens behind the scenes.

### Q: "How will users export data?"
**A**: 
1. User types query in browser
2. Browser sends request to backend
3. Backend queries database
4. Backend generates CSV file
5. Backend sends CSV to browser
6. Browser downloads CSV to user's computer

This is already implemented! Try it now at localhost:3001.

### Q: "Do I need to add a HIPAA layer?"
**A**: The HIPAA compliance features are already built into the code. You just need to enable them in production by setting environment variables (see backend/app/security.py).

### Q: "How do I get from localhost to a real URL?"
**A**: Deploy to cloud or on-premises server. They'll give you a URL. That's it!

---

## Next Steps

**Right now, you should:**

1. **Test your current system**
   - Open http://localhost:3001
   - Login with researcher/researcher123
   - Try a query: "Find all Parkinson's patients"
   - Download the CSV
   - Verify it works

2. **Decide on deployment**
   - Cloud (easier, $100-200/month)
   - On-premises (more control, $3K-7K one-time)

3. **Decide on data source**
   - Manual upload (simple)
   - Auto-sync from EHR (better)

4. **Contact me with your decisions**
   - I'll create a detailed deployment plan
   - I'll help you configure everything
   - I'll guide you through launch

---

## Visual: How a Query Works

```
┌─────────────────────────────────────────────────────────────┐
│ Step 1: User types query                                    │
│ Browser: "Find Parkinson's patients with DBS"               │
└────────────────────┬────────────────────────────────────────┘
                     │
                     │ HTTP POST /api/query
                     ↓
┌─────────────────────────────────────────────────────────────┐
│ Step 2: Backend receives request                            │
│ Backend: Parse query → Plan SQL → Validate                  │
└────────────────────┬────────────────────────────────────────┘
                     │
                     │ SQL: SELECT * FROM subjects WHERE...
                     ↓
┌─────────────────────────────────────────────────────────────┐
│ Step 3: Database executes query                             │
│ Database: Returns 142 rows                                  │
└────────────────────┬────────────────────────────────────────┘
                     │
                     │ JSON: {rows: [...], columns: [...]}
                     ↓
┌─────────────────────────────────────────────────────────────┐
│ Step 4: Backend generates files                             │
│ Backend: Create CSV, JSON, schema, provenance               │
└────────────────────┬────────────────────────────────────────┘
                     │
                     │ HTTP Response with download URLs
                     ↓
┌─────────────────────────────────────────────────────────────┐
│ Step 5: User downloads                                       │
│ Browser: Shows preview + download buttons                   │
│ User: Clicks "Download CSV" → Gets file                     │
└─────────────────────────────────────────────────────────────┘
```

**Key Point**: The user only sees Step 1 and Step 5. Everything else happens automatically on the server.

---

## You're Ready!

Your system is fully functional. The code is complete. You just need to:
1. Choose where to deploy it
2. Configure the data connection
3. Launch it

Everything else is already built and working!
