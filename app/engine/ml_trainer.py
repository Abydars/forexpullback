import asyncio
import os
import joblib
import pandas as pd
from datetime import datetime
from sqlalchemy import select
from app.db.session import AsyncSessionLocal
from app.db.models import Signal
from app.ws.manager import broadcast
import pytz

try:
    from sklearn.ensemble import RandomForestClassifier
    from sklearn.model_selection import train_test_split
    import numpy as np
except ImportError:
    RandomForestClassifier = None

MODEL_PATH = "data/ml_model.pkl"

async def train_ml_model():
    if not RandomForestClassifier:
        await broadcast({"type": "log.event", "level": "ERROR", "component": "ml", "message": "scikit-learn not installed.", "created_at": datetime.now(pytz.utc).isoformat()})
        return False
        
    await broadcast({"type": "log.event", "level": "INFO", "component": "ml", "message": "Starting ML model training...", "created_at": datetime.now(pytz.utc).isoformat()})
    
    async with AsyncSessionLocal() as db:
        result = await db.execute(select(Signal).where(Signal.result.isnot(None)))
        signals = result.scalars().all()
        
    if len(signals) < 50:
        await broadcast({"type": "log.event", "level": "WARN", "component": "ml", "message": f"Not enough data to train. Have {len(signals)}, need at least 50.", "created_at": datetime.now(pytz.utc).isoformat()})
        return False
        
    # Prepare data
    data = []
    for s in signals:
        if not s.ml_features:
            continue
        row = s.ml_features.copy()
        # label: 1 if TP, 0 if SL
        row['target'] = 1 if 'TP' in s.result.upper() else 0
        data.append(row)
        
    if len(data) < 50:
        await broadcast({"type": "log.event", "level": "WARN", "component": "ml", "message": f"Not enough ML features data to train. Have {len(data)}, need 50.", "created_at": datetime.now(pytz.utc).isoformat()})
        return False
        
    df = pd.DataFrame(data)
    
    # Drop rows with NaN targets
    df.dropna(subset=['target'], inplace=True)
    
    # Extract categorical vs numerical
    y = df['target']
    X = df.drop(columns=['target'])
    
    import zlib
    
    # Handle categoricals deterministically
    for col in X.select_dtypes(include=['object']).columns:
        X[col] = X[col].astype(str).apply(lambda x: zlib.crc32(x.encode('utf-8')))
        
    # Fill any remaining NaNs
    X.fillna(0, inplace=True)
    
    if len(X) < 50:
        return False
        
    # Train
    clf = RandomForestClassifier(n_estimators=100, max_depth=5, random_state=42)
    clf.fit(X, y)
    
    # Evaluate
    score = clf.score(X, y)
    
    # Save model and feature names
    os.makedirs(os.path.dirname(MODEL_PATH), exist_ok=True)
    joblib.dump({"model": clf, "features": list(X.columns)}, MODEL_PATH)
    
    await broadcast({
        "type": "log.event", 
        "level": "INFO", 
        "component": "ml", 
        "message": f"ML model trained successfully on {len(X)} samples. Accuracy on training set: {score*100:.1f}%", 
        "created_at": datetime.now(pytz.utc).isoformat()
    })
    
    return True

_loaded_model = None
_loaded_features = None

def predict_ml_prob(features_dict: dict) -> float:
    """Returns probability (0-100) of hitting TP, or None if no model."""
    global _loaded_model, _loaded_features
    if _loaded_model is None:
        if not os.path.exists(MODEL_PATH):
            return None
        try:
            data = joblib.load(MODEL_PATH)
            _loaded_model = data["model"]
            _loaded_features = data["features"]
        except Exception:
            return None
            
    import pandas as pd
    import zlib
    
    try:
        df = pd.DataFrame([features_dict])
        
        for f in _loaded_features:
            if f not in df.columns:
                df[f] = 0.0
        
        df = df[_loaded_features]
        
        for col in df.select_dtypes(include=['object']).columns:
            df[col] = df[col].astype(str).apply(lambda x: zlib.crc32(x.encode('utf-8')))
            
        df.fillna(0, inplace=True)
        
        prob_1 = _loaded_model.predict_proba(df)[0][1]
        return float(prob_1 * 100)
    except Exception as e:
        print(f"ML Predict error: {e}")
        return None
