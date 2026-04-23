import os
from cryptography.fernet import Fernet

def get_cipher():
    secret = os.environ.get("MT5_SECRET")
    if not secret:
        if os.path.exists(".mt5_secret"):
            with open(".mt5_secret", "r") as f:
                secret = f.read().strip()
        else:
            secret = Fernet.generate_key().decode()
            with open(".mt5_secret", "w") as f:
                f.write(secret)
            print(f"Generated new MT5_SECRET and saved to .mt5_secret: {secret}")
    return Fernet(secret.encode())

def encrypt_password(password: str) -> str:
    return get_cipher().encrypt(password.encode()).decode()

def decrypt_password(encrypted: str) -> str:
    return get_cipher().decrypt(encrypted.encode()).decode()
