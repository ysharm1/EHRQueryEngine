#!/bin/bash

# Research Dataset Builder - Launch Script
# This script starts both backend and frontend servers

echo "🚀 Launching Research Dataset Builder..."
echo ""

# Check if backend dependencies are installed
if [ ! -d "backend/data" ]; then
    echo "📦 Initializing database..."
    cd backend
    python3 -m app.init_db
    cd ..
fi

# Start backend in background
echo "🔧 Starting backend server (port 8000)..."
cd backend
python3 -m uvicorn app.main:app --reload --host 0.0.0.0 --port 8000 &
BACKEND_PID=$!
cd ..

# Wait for backend to start
sleep 3

# Start frontend in background
echo "🎨 Starting frontend server (port 3001)..."
cd frontend
npm run dev -- -p 3001 &
FRONTEND_PID=$!
cd ..

# Wait for frontend to start
sleep 3

echo ""
echo "✅ Research Dataset Builder is running!"
echo ""
echo "📍 Frontend: http://localhost:3001"
echo "📍 Backend API: http://localhost:8000"
echo "📍 API Docs: http://localhost:8000/docs"
echo ""
echo "🔑 Login credentials:"
echo "   Username: researcher"
echo "   Password: researcher123"
echo ""
echo "Press Ctrl+C to stop all servers"
echo ""

# Wait for user to stop
wait
