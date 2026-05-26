$ErrorActionPreference = "Stop"

Write-Host "=== Dataiku Factory Setup ===" -ForegroundColor Cyan

$pythonVersion = python --version 2>&1
if (-not ($pythonVersion -match "3\.1[1-9]|3\.[2-9]\d")) {
    Write-Error "Python 3.11 or newer is required. Found: $pythonVersion"
    exit 1
}
Write-Host "Python: $pythonVersion" -ForegroundColor Green

if (-not (Test-Path ".venv")) {
    Write-Host "Creating virtual environment..." -ForegroundColor Yellow
    python -m venv .venv
}

Write-Host "Installing dependencies..." -ForegroundColor Yellow
& ".venv\Scripts\pip.exe" install -e . --quiet

if (-not (Test-Path ".env")) {
    Copy-Item ".env.sample" ".env"
    Write-Host ".env created from .env.sample" -ForegroundColor Yellow
    Write-Host "  --> Edit .env with your DSS_HOST and DSS_API_KEY before starting the server." -ForegroundColor Magenta
} else {
    Write-Host ".env already exists, skipping." -ForegroundColor Green
}

Write-Host ""
Write-Host "Next steps:" -ForegroundColor White
Write-Host "  1. Edit .env with your DSS_HOST and DSS_API_KEY"
Write-Host "  2. Test the server: .\.venv\Scripts\python.exe scripts\mcp_server.py --help"
Write-Host "  3. Register it in Codex with 'codex mcp add dataiku-factory -- <python> <script> --transport stdio'"
Write-Host "  4. Register it in Claude Code if needed with 'claude mcp add ...'"
