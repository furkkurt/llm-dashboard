@echo off
REM Start script for LLM Dashboard (Windows version)

REM Change to the directory where the batch file is located
cd /d "%~dp0"

REM Activate virtual environment
if not exist ".venv\Scripts\activate.bat" goto :error_no_venv
call .venv\Scripts\activate.bat

REM Set default environment variables if not defined
if "%API_HOST%"=="" set API_HOST=127.0.0.1
if "%API_PORT%"=="" set API_PORT=8000
if "%STREAMLIT_PORT%"=="" set STREAMLIT_PORT=8501

echo Starting Backend (FastAPI) on %API_HOST%:%API_PORT%...
REM Start uvicorn in the background
start /B uvicorn backend.main:app --host %API_HOST% --port %API_PORT%

echo Starting Frontend (Streamlit) on port %STREAMLIT_PORT%...
REM Run streamlit (this will block the terminal)
streamlit run frontend\app.py --server.port %STREAMLIT_PORT%

echo.
echo Dashboard stopped.
pause
goto :eof

:error_no_venv
echo ERROR: Virtual environment not found. Run setup.bat first.
pause
exit /b 1
