#!/bin/bash
# =============================================================================
# Healthcare API - Local Development Runner
# =============================================================================

set -e

# Colors for output
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m' # No Color

# Get script directory
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

echo -e "${GREEN}Healthcare Finance Analytics API${NC}"
echo "=================================="

# Check if .env exists
if [ ! -f ".env" ]; then
    echo -e "${YELLOW}Warning: .env file not found${NC}"
    echo "Copy .env.example to .env and fill in your credentials:"
    echo "  cp .env.example .env"
    echo ""
fi

# Check for virtual environment
if [ -d "venv" ]; then
    echo "Activating virtual environment..."
    source venv/bin/activate
elif [ -d ".venv" ]; then
    echo "Activating virtual environment..."
    source .venv/bin/activate
else
    echo -e "${YELLOW}No virtual environment found.${NC}"
    echo "Create one with:"
    echo "  python -m venv venv"
    echo "  source venv/bin/activate"
    echo "  pip install -r requirements.txt"
    echo ""
    echo "Continuing without virtual environment..."
fi

# Check if dependencies are installed
if ! python -c "import fastapi" 2>/dev/null; then
    echo -e "${RED}FastAPI not installed.${NC}"
    echo "Install dependencies with:"
    echo "  pip install -r requirements.txt"
    exit 1
fi

# Add parent Agentic_view folder to path for workflow imports
# Structure: Agentic_view/healthcare-api/ (this script is inside healthcare-api)
export PYTHONPATH="${SCRIPT_DIR}:${SCRIPT_DIR}/..:${PYTHONPATH}"

echo ""
echo "Starting server..."
echo "  - API Docs: http://localhost:8000/docs"
echo "  - Health:   http://localhost:8000/health"
echo "  - WebSocket: ws://localhost:8000/ws/chat"
echo ""

# Run the server
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
