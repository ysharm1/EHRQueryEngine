#!/bin/bash
echo "Starting EHR Data Extraction System..."
echo

# Check if Python is installed
if ! command -v python3 &> /dev/null; then
    echo "Python 3 is not installed. Please install Python 3.8+"
    exit 1
fi

# Check if in the right directory
if [ ! -f "backend/requirements.txt" ]; then
    echo "Please run this script from the EHRData directory"
    exit 1
fi

# Install dependencies
echo "Installing dependencies..."
cd backend
pip3 install -r requirements.txt
if [ $? -ne 0 ]; then
    echo "Failed to install dependencies"
    exit 1
fi

# Initialize database
echo "Initializing database..."
python3 -m app.init_db
if [ $? -ne 0 ]; then
    echo "Failed to initialize database"
    exit 1
fi

# Start services
echo "Starting services..."
echo "1. PDF Watcher Service (monitors folders for new PDFs)"
echo "2. API Server (localhost:8000)"
echo "3. Frontend Dashboard (localhost:3000)"
echo

# Start PDF watcher in background
python3 -m app.services.pdf_watcher &
WATCHER_PID=$!

# Start API server in background
uvicorn app.main:app --host 0.0.0.0 --port 8000 &
API_PID=$!

echo
echo "Services started!"
echo "- PDF Watcher PID: $WATCHER_PID"
echo "- API Server PID: $API_PID"
echo "- API Server: http://localhost:8000"
echo "- API Docs: http://localhost:8000/docs"
echo
echo "Press Ctrl+C to stop all services"

# Function to cleanup on exit
cleanup() {
    echo "Stopping services..."
    kill $WATCHER_PID 2>/dev/null
    kill $API_PID 2>/dev/null
    exit 0
}

trap cleanup SIGINT SIGTERM

# Wait for user to press Ctrl+C
wait