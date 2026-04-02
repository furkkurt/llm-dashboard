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
if not exist "scripts" mkdir "scripts"

REM Kotlin JVM compiler (kotlinc) — same layout as setup.sh: tools\kotlin\bin\kotlinc.bat
if exist "tools\kotlin\bin\kotlinc.bat" (
    echo Kotlin compiler already present: tools\kotlin
) else (
    echo Installing Kotlin compiler into tools\kotlin ...
    powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0scripts\install-kotlin.ps1"
    if errorlevel 1 (
        echo ERROR: Kotlin install script failed.
        pause
        exit /b 1
    )
)

where java >nul 2>nul
if errorlevel 1 (
    echo WARNING: No java on PATH. Install JDK 17+ ^(or 21 LTS^); kotlinc needs it to compile Kotlin.
)

REM Check for detekt-cli.jar
if not exist "tools\detekt-cli.jar" (
    echo WARNING: Download detekt-cli.jar manually into tools\
    echo (see https://github.com/detekt/detekt/releases)
)

REM --- Flutter / Dart (Windows) ---
REM Analyzer runs pub get / dart analyze. GUI-started Uvicorn may not see User PATH;
REM set FLUTTER_ROOT in local.env so backend finds bin\flutter.bat ^(.env.example^).
set "FOUND_FLUTTER=0"
where flutter >nul 2>nul
if not errorlevel 1 set "FOUND_FLUTTER=1"

if "%FOUND_FLUTTER%"=="0" if defined FLUTTER_ROOT (
    if exist "%FLUTTER_ROOT%\bin\flutter.bat" set "FOUND_FLUTTER=1"
)
if "%FOUND_FLUTTER%"=="0" if defined FLUTTER_ROOT (
    if exist "%FLUTTER_ROOT%\bin\flutter" set "FOUND_FLUTTER=1"
)
if "%FOUND_FLUTTER%"=="0" if defined FLUTTER_HOME (
    if exist "%FLUTTER_HOME%\bin\flutter.bat" set "FOUND_FLUTTER=1"
)
if "%FOUND_FLUTTER%"=="0" if defined FLUTTER_HOME (
    if exist "%FLUTTER_HOME%\bin\flutter" set "FOUND_FLUTTER=1"
)

if "%FOUND_FLUTTER%"=="0" (
    echo WARNING: Flutter SDK not found ^(flutter not on PATH; FLUTTER_ROOT/FLUTTER_HOME missing or invalid^).
    echo   Flutter analysis ^(pub get^) may fail with WinError 2. Fix: add SDK\bin to PATH, or add
    echo   FLUTTER_ROOT=C:\path\to\flutter to local.env ^(see .env.example^).
) else (
    where flutter >nul 2>nul
    if not errorlevel 1 (
        echo Flutter: found on PATH ^(pub get / dart analyze^).
    ) else (
        echo Flutter: FLUTTER_ROOT / FLUTTER_HOME points to a valid SDK ^(recommend local.env for API/Streamlit^).
    )
)

where dart >nul 2>nul
if errorlevel 1 (
    if "%FOUND_FLUTTER%"=="1" echo NOTE: dart not on PATH separately; Flutter-bundled dart is usually enough.
) else (
    echo dart: found on PATH.
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
