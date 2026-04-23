@echo off
echo Starting Forex...
start "Forex Backend" cmd /k "venv\Scripts\python.exe -m backend.main"
start "Forex Frontend" cmd /k "cd frontend && npm run dev"
pause
