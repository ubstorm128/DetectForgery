@echo off
cd /d "%~dp0"
echo Starting Veristamp Screening API...
start http://127.0.0.1:8000/
cd backend
..\.venv\Scripts\python.exe -m uvicorn app.main:app --reload
pause
