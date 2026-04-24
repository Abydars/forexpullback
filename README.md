# Forex Pullback Trading System

A production-grade forex pullback trading system that connects to any MT5 broker (tested on Exness). Features a fully localized backend architecture with no node dependencies, single-file HTML frontend, vanilla JS without any framework, and a dark trading desk aesthetic.

## Architecture
```text
┌─────────────────────────────────────────────────────────┐
│       Browser: index.html (one file, vanilla JS)        │
│  Dashboard · Trades · Signals · Config · MT5 Modal      │
└──────────────────┬──────────────────────────────────────┘
                   │ REST (JSON) + WebSocket
┌──────────────────▼──────────────────────────────────────┐
│                 FastAPI (uvicorn)                       │
│  /api/*  ·  /ws  ·  /  (serves index.html)              │
└──────────────────┬──────────────────────────────────────┘
                   │ direct Python calls
┌──────────────────▼──────────────────────────────────────┐
│                  Core Engine (asyncio)                  │
│  Scanner → Signal Engine → Order Manager → Monitor      │
└──────────────────┬──────────────────────────────────────┘
                   │
┌──────────────────▼──────────────────────────────────────┐
│   MT5 Client · Symbol Resolver · Session Manager        │
│              SQLite (config, trades, signals)           │
└──────────────────┬──────────────────────────────────────┘
                   │ MT5 Python API (polling)
            ┌──────▼──────┐
            │ MT5 Terminal│  ← Exness (or any broker)
            └─────────────┘
```

## Setup & Running

1. **Prerequisites**: Python 3.11+, MT5 terminal installed and running (requires Windows, or wine/crossover on Mac).
2. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```
3. Set the encryption secret (Optional but recommended):
   ```bash
   export MT5_SECRET="your_secret_here"
   ```
4. Start the application:
   ```bash
   python main.py
   ```
5. Access the dashboard: `http://localhost:8771`

## Troubleshooting

- **Symbol not resolved**: Ensure you have successfully connected the MT5 instance to your broker account via the `MT5 LINK` modal. Check your broker's symbol suffix (e.g. `m`, `c`, `.r`) to ensure it's in the known suffixes in `app/mt5_client/symbol_resolver.py`.
- **Connect fails**: Check your credentials. Sometimes Exness Trial servers change IPs; make sure your server string exactly matches what is listed in the terminal.
- **No signals**: The scanner logic relies on overlapping sessions. Make sure you have created at least one active session in the configuration and toggle the Engine to START.
