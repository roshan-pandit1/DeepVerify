#!/bin/bash
# start.sh — Launch the FastAPI backend
set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

# Check for .env file
if [ ! -f ".env" ]; then
  echo ""
  echo "=========================================================="
  echo "  ERROR: .env file not found in backend/"
  echo "  Copy .env.example to .env and fill in your API keys:"
  echo "    cp .env.example .env"
  echo "=========================================================="
  exit 1
fi

# Check for virtual environment
if [ ! -d "venv" ]; then
  echo "Creating Python virtual environment..."
  python3 -m venv venv
fi

source venv/bin/activate

# Install dependencies if needed
export PYO3_USE_ABI3_FORWARD_COMPATIBILITY=1
pip install -q -r requirements.txt --prefer-binary

# Ensure /tmp/uploads exists
mkdir -p /tmp/uploads

echo ""
echo "=========================================================="
echo "  Starting Video Authenticity Engine (FastAPI)"
echo "  API: http://localhost:8000"
echo "  Docs: http://localhost:8000/docs"
echo "=========================================================="
echo ""

uvicorn main:app \
  --host 0.0.0.0 \
  --port 8000 \
  --reload \
  --log-level info
