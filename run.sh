#!/usr/bin/env bash
set -e
(cd backend && PYTHONPATH=.. ../venv/bin/python main.py) &
(cd frontend && npm run dev) &
wait
