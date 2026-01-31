# =============================================================================
# Healthcare API - Local Development Runner (PowerShell)
# =============================================================================

$ErrorActionPreference = "Stop"

# Get script directory
$SCRIPT_DIR = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $SCRIPT_DIR

Write-Host "Healthcare Finance Analytics API" -ForegroundColor Green
Write-Host "=================================="
Write-Host ""

# Check if .env exists
if (-not (Test-Path ".env")) {
    Write-Host "Warning: .env file not found" -ForegroundColor Yellow
    Write-Host "Copy .env.example to .env and fill in your credentials:"
    Write-Host "  Copy-Item .env.example .env"
    Write-Host ""
}

# Skip virtual environment - using system Python with all packages installed
Write-Host "Using system Python (packages already installed)..." -ForegroundColor Cyan

# Check if dependencies are installed
try {
    python -c "import fastapi" 2>$null
    if ($LASTEXITCODE -ne 0) {
        throw
    }
} catch {
    Write-Host "FastAPI not installed." -ForegroundColor Red
    Write-Host "Install dependencies with:"
    Write-Host "  pip install -r requirements.txt"
    exit 1
}

# Add parent Agentic_view folder to path for workflow imports
# Structure: Agentic_view/healthcare-api/ (this script is inside healthcare-api)
$parent = Split-Path -Parent $SCRIPT_DIR
$env:PYTHONPATH = "$SCRIPT_DIR;$parent;$env:PYTHONPATH"

Write-Host ""
Write-Host "Starting server..." -ForegroundColor Green
Write-Host "  - API Docs:  http://localhost:8000/docs"
Write-Host "  - Health:    http://localhost:8000/health"
Write-Host "  - WebSocket: ws://localhost:8000/ws/chat"
Write-Host ""

# Run the server
python -m uvicorn app.main:app --reload --host 0.0.0.0 --port 8000

PS C:\Users\msivaku1\Documents\Agentic_view> cd c:\Users\msivaku1\Documents\Agentic_view\healthcare-api; Get-ExecutionPolicy; powershell -ExecutionPolicy Bypass -File .\run_local.ps1
RemoteSigned
Healthcare Finance Analytics API
==================================

Warning: .env file not found
Copy .env.example to .env and fill in your credentials:
  Copy-Item .env.example .env

Using system Python (packages already installed)...

Starting server...
  - API Docs:  http://localhost:8000/docs
  - Health:    http://localhost:8000/health
  - WebSocket: ws://localhost:8000/ws/chat

INFO:     Will watch for changes in these directories: ['C:\\Users\\msivaku1\\Documents\\Agentic_view\\healthcare-api']
INFO:     Uvicorn running on http://0.0.0.0:8000 (Press CTRL+C to quit)
INFO:     Started reloader process [13348] using WatchFiles
INFO:     Started server process [37872]
INFO:     Waiting for application startup.
Starting Healthcare API...
Storage initialized successfully
INFO:     Application startup complete.
INFO:     127.0.0.1:56829 - "GET /docs HTTP/1.1" 200 OK
INFO:     127.0.0.1:56829 - "GET /openapi.json HTTP/1.1" 200 OK
