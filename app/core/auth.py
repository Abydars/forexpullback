import hmac
import hashlib
import os
import time

# Secret key for signing sessions.
# For a local app, regenerating this on startup invalidates all sessions, which is secure.
SECRET_KEY = os.environ.get("APP_SECRET_KEY", os.urandom(32).hex()).encode()

def hash_password(password: str) -> str:
    """Hashes a password using SHA-256."""
    return hashlib.sha256(password.encode()).hexdigest()

def verify_password(plain: str, hashed: str) -> bool:
    """Verifies a plain password against a hashed one."""
    return hash_password(plain) == hashed

def create_access_token() -> str:
    """Creates a signed session token valid for the current timestamp."""
    timestamp = str(int(time.time()))
    signature = hmac.new(SECRET_KEY, timestamp.encode(), hashlib.sha256).hexdigest()
    return f"{timestamp}.{signature}"

def verify_access_token(token: str) -> bool:
    """Verifies a signed session token."""
    if not token or "." not in token:
        return False
    
    timestamp, signature = token.split(".", 1)
    expected_sig = hmac.new(SECRET_KEY, timestamp.encode(), hashlib.sha256).hexdigest()
    
    # Check if signature matches
    if not hmac.compare_digest(expected_sig, signature):
        return False
        
    # Check if token is expired (e.g., 30 days)
    try:
        ts = int(timestamp)
        if time.time() - ts > 86400 * 30:
            return False
    except ValueError:
        return False
        
    return True
