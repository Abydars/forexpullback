import os
import logging
from cryptography.fernet import Fernet

_key = os.environ.get("MT5_SECRET")
if not _key:
    _key = Fernet.generate_key().decode()
    os.environ["MT5_SECRET"] = _key
    logging.warning(f"MT5_SECRET not found in env. Generated new key: {_key}")

fernet = Fernet(_key.encode())

def encrypt(data: str) -> str:
    return fernet.encrypt(data.encode()).decode()

def decrypt(data: str) -> str:
    return fernet.decrypt(data.encode()).decode()
