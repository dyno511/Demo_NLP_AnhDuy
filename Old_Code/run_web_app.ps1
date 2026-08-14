# ============================================================
#  AI Social Listening - Streamlit Web UI launcher (PowerShell)
#  Always runs with the project-local virtual env (.venv),
#  so PhoBERT (transformers/torch) resolves inside the project.
#  Project root is derived from $PSScriptRoot, no hardcoded path.
# ============================================================

$ErrorActionPreference = "Stop"

$projectRoot = $PSScriptRoot
$venvPython = Join-Path $projectRoot ".venv\Scripts\python.exe"

if (-not (Test-Path -LiteralPath $venvPython)) {
    Write-Host "[ERROR] Virtual environment not found: $venvPython" -ForegroundColor Red
    Write-Host ""
    Write-Host "Create it first, then install dependencies:"
    Write-Host "  python -m venv .venv"
    Write-Host "  .venv\Scripts\pip install -r requirements.txt"
    exit 1
}

Write-Host "[INFO] Using Python: $venvPython"

& $venvPython -c "import transformers, torch, streamlit" 2>$null
if ($LASTEXITCODE -ne 0) {
    Write-Host "[ERROR] Missing packages in .venv (transformers/torch/streamlit)." -ForegroundColor Red
    Write-Host ""
    Write-Host "Install dependencies:"
    Write-Host "  .venv\Scripts\pip install -r requirements.txt"
    exit 1
}

Write-Host "[INFO] Starting Streamlit from the project virtual environment..."
Push-Location $projectRoot
try {
    & $venvPython -m streamlit run web_app.py @args
}
finally {
    Pop-Location
}
