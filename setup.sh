#!/usr/bin/env bash
# setup.sh — one-time setup for Research Dataset Builder
# Run this before starting the application for the first time.
set -e

echo "=== Research Dataset Builder — Setup ==="

# ── 1. Backend .env ──────────────────────────────────────────────────────────
BACKEND_ENV="backend/.env"

if [ ! -f "$BACKEND_ENV" ]; then
  echo "[1/4] Creating backend/.env from template..."
  cp backend/.env.example "$BACKEND_ENV"
fi

# Generate a strong JWT secret if the file still has the default placeholder
if grep -q "dev-secret-key-change-in-production" "$BACKEND_ENV"; then
  echo "[2/4] Generating a random JWT_SECRET_KEY..."
  NEW_SECRET=$(python3 -c "import secrets; print(secrets.token_hex(32))")
  # Replace the placeholder on all platforms (BSD sed + GNU sed compatible)
  sed -i.bak "s|JWT_SECRET_KEY=.*|JWT_SECRET_KEY=${NEW_SECRET}|" "$BACKEND_ENV"
  rm -f "${BACKEND_ENV}.bak"
  echo "      JWT_SECRET_KEY updated."
else
  echo "[2/4] JWT_SECRET_KEY already customised — skipping."
fi

# ── 2. Frontend .env.local ───────────────────────────────────────────────────
FRONTEND_ENV="frontend/.env.local"

if [ ! -f "$FRONTEND_ENV" ]; then
  echo "[3/4] Creating frontend/.env.local..."
  cat > "$FRONTEND_ENV" <<'EOF'
NEXT_PUBLIC_API_URL=http://localhost:8000
EOF
  echo "      Created. Edit NEXT_PUBLIC_API_URL if your backend runs elsewhere."
else
  echo "[3/4] frontend/.env.local already exists — skipping."
fi

# ── 3. Python dependencies ───────────────────────────────────────────────────
echo "[4/4] Installing Python dependencies..."
cd backend
if ! python3 -m pip install -r requirements.txt -q; then
  echo "      pip install failed — check your Python environment."
  exit 1
fi
cd ..

echo ""
echo "=== Setup complete ==="
echo ""
echo "Next steps:"
echo "  1. Start the backend:  cd backend && python3 -m uvicorn app.main:app --reload --port 8000"
echo "  2. Init sample data:   cd backend && python3 -m app.init_db"
echo "  3. Start the frontend: cd frontend && npm install && npm run dev -- -p 3001"
echo "  4. Open http://localhost:3001 and sign in as researcher / researcher123"
echo ""
echo "For production deployment see DEPLOYMENT_GUIDE.md"
