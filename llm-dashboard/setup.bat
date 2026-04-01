@echo off
REM Setup script for LLM Dashboard (Windows version)

REM Check for backend\main.py to ensure we are in the project root
if not exist "backend\main.py" goto :error_not_root

echo Setup directory (project root): "%cd%"

REM Create .venv if it doesn't exist
if exist ".venv" goto :skip_venv
echo Creating virtual environment...
python -m venv .venv
:skip_venv

REM Activate venv and install dependencies
if not exist ".venv\Scripts\activate.bat" goto :error_no_venv
call .venv\Scripts\activate.bat

echo Upgrading pip...
python -m pip install --upgrade pip

echo Installing requirements...
pip install -r requirements.txt

REM Create necessary directories
if not exist "tools" mkdir "tools"
if not exist "results" mkdir "results"
if not exist "results\exports" mkdir "results\exports"
if not exist "results\raw-logs" mkdir "results\raw-logs"
if not exist "temp\runs" mkdir "temp\runs"

REM Check for detekt-cli.jar
if not exist "tools\detekt-cli.jar" (
    echo WARNING: Download detekt-cli.jar manually into tools\
    echo (see https://github.com/detekt/detekt/releases)
)

echo.
echo Setup complete.
echo To activate the environment, run: .venv\Scripts\activate
pause
goto :eof

:error_not_root
echo ERROR: Run setup.bat from the dashboard project root (expected backend\main.py here).
echo Current directory: "%cd%"
pause
exit /b 1

:error_no_venv
echo ERROR: Virtual environment folder found but activation script is missing.
pause
exit /b 1
