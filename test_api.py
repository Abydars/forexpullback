import requests

payload = {
  "max_open_positions": 2,
  "max_per_symbol": 1,
  "max_per_direction": 1,
  "risk_percent": 0.5,
  "reward_ratio": 1.8,
  "signal_threshold": 75,
  "correlation_groups_enabled": True,
  "max_open_per_correlation_group": 1,
  "trailing": True,
  "trailing_start_tp_pct": 0.5,
  "trailing_atr_multiplier": 1.2,
  "enable_dca": False,
  "enable_basket_trailing": False
}

try:
    res = requests.patch("http://localhost:8000/api/config", json=payload)
    print(res.status_code, res.text)
except Exception as e:
    print("Error:", e)
