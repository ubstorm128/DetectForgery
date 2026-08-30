@echo off
echo Starting Veristamp Screening API...
cd backend
..\.venv\Scripts\python.exe -m uvicorn main:app --reload
pause
