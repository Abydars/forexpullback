#!/usr/bin/env bash
set -e
echo "Starting Forex Pullback Trading System..."
PYTHONPATH=. ./venv/bin/python -m backend.main
