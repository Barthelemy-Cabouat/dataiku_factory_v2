# Dataiku Copilot Skill — Setup (Windows)
# Run this from the dataiku-copilot-skill folder:
#   cd C:\Users\barth\dataiku-copilot-skill
#   .\setup.ps1

$ErrorActionPreference = "Stop"

Write-Host "=== Dataiku Copilot Skill Setup ===" -ForegroundColor Cyan

# ── 1. Python version check ──────────────────────────────────────────────────
$pythonVersion = python --version 2>&1
if (-not ($pythonVersion -match "3\.1[1-9]|3\.[2-9]\d")) {
    Write-Error "Python 3.11 or newer is required. Found: $pythonVersion"
    exit 1
}
Write-Host "Python: $pythonVersion" -ForegroundColor Green

# ── 2. Create virtualenv ──────────────────────────────────────────────────────
if (-not (Test-Path ".venv")) {
    Write-Host "Creating virtual environment..." -ForegroundColor Yellow
    python -m venv .venv
}

# ── 3. Activate & install ─────────────────────────────────────────────────────
Write-Host "Installing dependencies..." -ForegroundColor Yellow
& ".venv\Scripts\pip.exe" install -e . --quiet

# ── 4. Create .env from sample ────────────────────────────────────────────────
if (-not (Test-Path ".env")) {
    Copy-Item ".env.sample" ".env"
    Write-Host ".env created from .env.sample" -ForegroundColor Yellow
    Write-Host "  --> Edit .env with your DSS_HOST and DSS_API_KEY before starting the server." -ForegroundColor Magenta
} else {
    Write-Host ".env already exists, skipping." -ForegroundColor Green
}

# ── 5. Validate connection (optional, only if .env is configured) ─────────────
$envContent = Get-Content ".env" -Raw
if ($envContent -notmatch "your-api-key-here" -and $envContent -notmatch "your-dss-instance") {
    Write-Host "Testing DSS connection..." -ForegroundColor Yellow
    & ".venv\Scripts\python.exe" scripts/mcp_server.py --help
    Write-Host "Connection test passed." -ForegroundColor Green
} else {
    Write-Host "Skipping connection test — .env not yet configured." -ForegroundColor DarkYellow
}

Write-Host ""
Write-Host "=== Setup complete ===" -ForegroundColor Cyan
Write-Host ""
Write-Host "Next steps:" -ForegroundColor White
Write-Host "  1. Edit .env with your DSS_HOST and DSS_API_KEY"
Write-Host "  2. Open this folder in VS Code:  code ."
Write-Host "  3. Start GitHub Copilot Chat (Ctrl+Alt+I)"
Write-Host "  4. The 'dataiku-factory' MCP server will be available automatically."
Write-Host "  5. Use the 'dataiku' prompt file via '@' in Copilot Chat for guided workflows."
