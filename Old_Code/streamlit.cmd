@echo off
setlocal

rem ============================================================
rem  streamlit shim -> forces the project .venv.
rem  Placed in the project root so that, when you type
rem  "streamlit run web_app.py" FROM THE PROJECT ROOT in cmd,
rem  Windows finds THIS file (current dir is searched before
rem  PATH) and routes the call to .venv\Scripts\python.exe.
rem  No hardcoded path is assumed.
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

cd /d "%PROJECT_ROOT%"
"%VENV_PYTHON%" -m streamlit %*
endlocal
