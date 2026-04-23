import logging
from app.db.session import SessionLocal
from app.db.models import SignalRecord
from app.ui.state import state
from app.engine.order_manager import execute_trade

logger = logging.getLogger("signal_engine")

async def process_signal(sig_data: dict):
    # Check max positions
    if len(state.open_positions) >= state.cfg.max_open_positions:
        logger.info("Max open positions reached, ignoring signal.")
        return
        
    # Check if already in same direction for this symbol
    for pos in state.open_positions:
        if pos['symbol'] == sig_data['symbol']:
            pos_dir = 'bullish' if pos['type'] == 0 else 'bearish'
            if pos_dir == sig_data['direction']:
                logger.info(f"Already holding {sig_data['direction']} for {sig_data['symbol']}, ignoring.")
                return

    db = SessionLocal()
    signal = SignalRecord(
        symbol=sig_data['symbol'],
        direction=sig_data['direction'],
        score=sig_data['score'],
        htf_bias=sig_data['htf_bias'],
        entry=sig_data['entry'],
        sl=sig_data['sl'],
        tp=sig_data['tp'],
        reason=sig_data['reason']
    )
    db.add(signal)
    db.commit()
    db.refresh(signal)
    
    state.recent_signals.insert(0, {
        'id': signal.id,
        'symbol': signal.symbol,
        'direction': signal.direction,
        'score': signal.score,
        'created_at': signal.created_at
    })
    state.recent_signals = state.recent_signals[:50]
    
    logger.info(f"Generated signal: {sig_data}")
    
    # Pass to order manager
    await execute_trade(signal, db)
    db.close()
