import os
from cryptography.fernet import Fernet

def get_cipher():
    secret = os.environ.get("BOT_SECRET")
    if not secret:
        if os.path.exists(".bot_secret"):
            with open(".bot_secret", "r") as f:
                secret = f.read().strip()
        else:
            secret = Fernet.generate_key().decode()
            with open(".bot_secret", "w") as f:
                f.write(secret)
            print(f"Generated new BOT_SECRET and saved to .bot_secret: {secret}")
    return Fernet(secret.encode())

def encrypt_password(password: str) -> str:
    return get_cipher().encrypt(password.encode()).decode()

def decrypt_password(encrypted: str) -> str:
    return get_cipher().decrypt(encrypted.encode()).decode()
