@echo off
echo === Setting up your Python environment ===

REM 1. Check if venv exists
IF NOT EXIST "venv" (
    echo [1/3] Creating virtual environment...
    python -m venv venv
) ELSE (
    echo [1/3] Virtual environment already exists.
)

REM 2. Activate environment and install requirements
echo [2/3] Installing requirements...
call venv\Scripts\activate && pip install -r requirements.txt

REM 3. Optional: Launch GUI (you can comment this if not needed)
echo [3/3] Launching GUI...
call venv\Scripts\python.exe gui.py

pause
