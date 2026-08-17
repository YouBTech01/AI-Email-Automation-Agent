"""
Encryption at rest utility for sensitive credentials (API keys, OAuth tokens).
Uses Fernet (AES-128-CBC with HMAC-SHA256) for strong authenticated encryption.
"""
import base64
import os
import hashlib
from cryptography.fernet import Fernet
from config.settings import STORAGE_DIR, ENCRYPTION_KEY

KEY_FILE = STORAGE_DIR / 'secret.key'

def _get_or_create_key() -> bytes:
    """Retrieve or generate the persistent encryption key."""
    if ENCRYPTION_KEY:
        # Generate a 32-byte urlsafe base64 key from the configured key string
        digest = hashlib.sha256(ENCRYPTION_KEY.encode('utf-8')).digest()
        return base64.urlsafe_b64encode(digest)
    
    if KEY_FILE.exists():
        with open(KEY_FILE, 'rb') as f:
            return f.read().strip()
    
    # Generate new random Fernet key
    new_key = Fernet.generate_key()
    with open(KEY_FILE, 'wb') as f:
        f.write(new_key)
    try:
        # Set file permissions to readable only by owner where supported
        os.chmod(KEY_FILE, 0o600)
    except Exception:
        pass
    return new_key

def encrypt_value(raw_value: str) -> str:
    """Encrypt a plaintext string to an encrypted base64 token string."""
    if not raw_value:
        return ''
    try:
        f = Fernet(_get_or_create_key())
        encrypted = f.encrypt(raw_value.encode('utf-8'))
        return encrypted.decode('utf-8')
    except Exception as e:
        # Fallback safeguard
        return raw_value

def decrypt_value(encrypted_value: str) -> str:
    """Decrypt an encrypted token string back to plaintext."""
    if not encrypted_value:
        return ''
    try:
        f = Fernet(_get_or_create_key())
        decrypted = f.decrypt(encrypted_value.encode('utf-8'))
        return decrypted.decode('utf-8')
    except Exception:
        # If not encrypted or already plaintext (legacy/migration)
        return encrypted_value
