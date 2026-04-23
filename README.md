# Forex Pullback Trading System

A pure Python 3.11+ automated trading system using MetaTrader5 and NiceGUI.

## Architecture

Single-process application. NiceGUI runs the UI via FastAPI, and the core engine runs as `asyncio` background tasks. All states are reactive via NiceGUI decorators.

## Setup

1. **Install Python 3.11+**
2. **Install requirements**:
   ```bash
   pip install -r requirements.txt
   ```
3. **Environment**:
   Copy `.env.example` to `.env` and configure `MT5_SECRET` or allow the bot to auto-generate a `.mt5_secret` file on first run.
4. **Run**:
   ```bash
   python main.py
   ```
5. **Open Browser**: `http://localhost:8080`

## Features

- **Reactive UI**: Built purely in Python with NiceGUI.
- **Symbol Resolver**: Generalized symbols (`XAUUSD`) automatically resolve to broker specific ones (`XAUUSDm`, etc.).
- **Session Management**: Full timezone aware trading windows (e.g. London, NY).
- **Automated Pullback Strategy**: Multi-timeframe analysis (4H, 15M, 5M).

## Testing

```bash
pytest
```
