@echo off
setlocal

rem ============================================================
rem  AI Social Listening - Streamlit Web UI launcher (cmd)
rem  Always runs with the project-local virtual env (.venv),
rem  so PhoBERT (transformers/torch) resolves inside the project.
rem  Project root is derived from this file's location (%~dp0),
rem  no hardcoded path is assumed.
rem ============================================================

set "PROJECT_ROOT=%~dp0"
set "VENV_PYTHON=%PROJECT_ROOT%.venv\Scripts\python.exe"

if not exist "%VENV_PYTHON%" (
    echo [ERROR] Virtual environment not found: %VENV_PYTHON%
    echo.
    echo Create it first, then install dependencies:
    echo   python -m venv .venv
    echo   .venv\Scripts\pip install -r requirements.txt
    exit /b 1
)

echo [INFO] Using Python: %VENV_PYTHON%

"%VENV_PYTHON%" -c "import transformers, torch, streamlit" 2>nul
if errorlevel 1 (
    echo [ERROR] Missing packages in .venv ^(transformers/torch/streamlit^).
    echo.
    echo Install dependencies:
    echo   .venv\Scripts\pip install -r requirements.txt
    exit /b 1
)

echo [INFO] Starting Streamlit from the project virtual environment...
cd /d "%PROJECT_ROOT%"
"%VENV_PYTHON%" -m streamlit run web_app.py %*
endlocal
