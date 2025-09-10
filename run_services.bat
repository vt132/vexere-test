@echo off
setlocal ENABLEDELAYEDEXPANSION

REM Change to the directory of this script (repo root)
cd /d "%~dp0"

REM Activate Conda environment
call conda activate ml-env
if errorlevel 1 (
  echo Failed to activate conda environment 'ml-env'. Ensure Conda is installed and on PATH.
  exit /b 1
)

REM Start LLM service on port 8001
start "LLM Service" cmd /k python -m uvicorn services.llm_service.app.main:app --port 8001 --reload

REM Start Data service on port 8002
start "Data Service" cmd /k python -m uvicorn services.data_service.app.main:app --port 8002 --reload

REM Start User Gateway on port 8000
start "User Gateway" cmd /k python -m uvicorn services.user_gateway.app.main:app --port 8000 --reload

echo Launched LLM (8001), Data (8002), and Gateway (8000) in separate windows.
exit /b 0
