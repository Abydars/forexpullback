import os
from cryptography.fernet import Fernet
import logging

def get_cipher():
    secret = os.environ.get("MT5_SECRET")
    if not secret:
        try:
            with open(".mt5_secret", "r") as f:
                secret = f.read().strip()
        except FileNotFoundError:
            secret = Fernet.generate_key().decode()
            with open(".mt5_secret", "w") as f:
                f.write(secret)
            os.environ["MT5_SECRET"] = secret
            logging.info("Generated new MT5_SECRET and saved to .mt5_secret")
    return Fernet(secret.encode())

def encrypt(password: str) -> str:
    return get_cipher().encrypt(password.encode()).decode()

def decrypt(token: str) -> str:
    return get_cipher().decrypt(token.encode()).decode()
