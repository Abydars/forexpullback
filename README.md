# Forex Pullback Trading System

A production-grade MT5 trading system with a FastAPI backend and a React/Vite frontend.

## Architecture

```text
┌────────────────────────────────────────────────────────────┐
│                    Web UI (React + Vite)                   │
│  Dashboard · Trades · PnL · Signals · Config · MT5 Modal   │
└──────────────────┬─────────────────────────────────────────┘
                   │ REST + WebSocket
┌──────────────────▼─────────────────────────────────────────┐
│                   FastAPI Backend                          │
│  ┌─────────────┬──────────────┬──────────────────────────┐ │
│  │  API Layer  │  WS Manager  │  Background Scheduler    │ │
│  └─────────────┴──────────────┴──────────────────────────┘ │
│  ┌─────────────────────────────────────────────────────┐   │
│  │          Core Engine (asyncio loop)                 │   │
│  │  Scanner → Signal Engine → Order Manager → Monitor  │   │
│  └─────────────────────────────────────────────────────┘   │
│  ┌─────────────────────────────────────────────────────┐   │
│  │   MT5 Client · Symbol Resolver · Session Manager    │   │
│  └─────────────────────────────────────────────────────┘   │
│  ┌─────────────────────────────────────────────────────┐   │
│  │          SQLite (config, trades, signals)           │   │
│  └─────────────────────────────────────────────────────┘   │
└──────────────────┬─────────────────────────────────────────┘
                   │ MT5 Python API (polling)
            ┌──────▼──────┐
            │ MT5 Terminal│  ← Exness (or any broker)
            └─────────────┘
```

## Setup

1. **Backend**:
   - `python3 -m venv venv`
   - `source venv/bin/activate`
   - `pip install -r requirements.txt`

2. **Frontend**:
   - `cd frontend`
   - `npm install`

3. **Run**:
   - `./run.sh`

## Environment Variables
- `MT5_SECRET`: Used to encrypt MT5 passwords in the local SQLite database. Will be generated automatically if missing.
