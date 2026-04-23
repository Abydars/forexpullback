@echo off
echo Starting Forex Pullback Trading System...

:: Start the FastAPI backend in a new window
start "Forex Backend" cmd /c "cd backend && set PYTHONPATH=.. && ..\venv\Scripts\python.exe main.py"

:: Start the Vite frontend in a new window
start "Forex Frontend" cmd /c "cd frontend && npm run dev"

echo Servers are running in separate windows.
echo Close those windows to stop the servers.
pause
