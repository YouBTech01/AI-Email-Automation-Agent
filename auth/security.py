"""
Security, password hashing, validation, and login rate limiting.
"""
import time
from typing import Dict, Tuple
from werkzeug.security import generate_password_hash, check_password_hash
from config.settings import RATE_LIMIT_LOGIN_ATTEMPTS, RATE_LIMIT_WINDOW_SECONDS

# In-memory tracking for failed login attempts: {ip: [timestamps]}
_failed_attempts: Dict[str, list] = {}

def hash_password(plaintext: str) -> str:
    """Securely hash a password using scrypt/pbkdf2."""
    return generate_password_hash(plaintext, method='scrypt')

def verify_password(plaintext: str, password_hash: str) -> bool:
    """Verify password against hash."""
    if not plaintext or not password_hash:
        return False
    return check_password_hash(password_hash, plaintext)

def validate_password_strength(password: str) -> Tuple[bool, str]:
    """Validate that a new password meets minimum security strength."""
    if len(password) < 8:
        return False, "Password must be at least 8 characters long."
    if not any(c.isupper() for c in password):
        return False, "Password must contain at least one uppercase letter."
    if not any(c.islower() for c in password):
        return False, "Password must contain at least one lowercase letter."
    if not any(c.isdigit() for c in password):
        return False, "Password must contain at least one digit."
    return True, ""

def is_rate_limited(ip: str) -> Tuple[bool, int]:
    """Check if the IP is currently rate-limited due to excessive failed attempts."""
    now = time.time()
    attempts = _failed_attempts.get(ip, [])
    
    # Filter attempts within the rate limit window
    recent = [t for t in attempts if now - t < RATE_LIMIT_WINDOW_SECONDS]
    _failed_attempts[ip] = recent
    
    if len(recent) >= RATE_LIMIT_LOGIN_ATTEMPTS:
        retry_after = int(RATE_LIMIT_WINDOW_SECONDS - (now - recent[0]))
        return True, max(1, retry_after)
    return False, 0

def record_failed_login(ip: str):
    """Record a failed login attempt for the IP."""
    now = time.time()
    attempts = _failed_attempts.get(ip, [])
    attempts.append(now)
    _failed_attempts[ip] = attempts

def clear_failed_logins(ip: str):
    """Reset failed login count upon successful authentication."""
    if ip in _failed_attempts:
        del _failed_attempts[ip]
