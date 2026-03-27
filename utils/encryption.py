import os
import base64
from cryptography.fernet import Fernet, InvalidToken

# ─────────────────────────────────────────────
# FIELD-LEVEL ENCRYPTION FOR SENSITIVE KYC DATA
# ─────────────────────────────────────────────
# Uses Fernet symmetric encryption (AES-128-CBC + HMAC-SHA256)
# Key is stored in environment variable KYC_ENCRYPTION_KEY
# Never stored in code or committed to git

def _get_cipher():
    key = os.environ.get('KYC_ENCRYPTION_KEY')
    if not key:
        raise RuntimeError(
            'KYC_ENCRYPTION_KEY environment variable is not set. '
            'Generate one with: python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"'
        )
    return Fernet(key.encode())


def encrypt_field(value: str) -> str:
    """
    Encrypt a string field.
    Returns base64-encoded encrypted string.
    Returns empty string if value is empty.
    """
    if not value:
        return ''
    try:
        cipher    = _get_cipher()
        encrypted = cipher.encrypt(value.encode('utf-8'))
        return encrypted.decode('utf-8')
    except Exception as e:
        print(f"Encryption error: {e}")
        raise


def decrypt_field(value: str) -> str:
    """
    Decrypt an encrypted field.
    Returns original string.
    Returns empty string if value is empty.
    Returns value as-is if it cannot be decrypted
    (handles legacy unencrypted data gracefully).
    """
    if not value:
        return ''
    try:
        cipher    = _get_cipher()
        decrypted = cipher.decrypt(value.encode('utf-8'))
        return decrypted.decode('utf-8')
    except InvalidToken:
        # Value is not encrypted (legacy data) — return as-is
        print(f"Warning: field appears unencrypted, returning raw value")
        return value
    except Exception as e:
        print(f"Decryption error: {e}")
        return value


def is_encrypted(value: str) -> bool:
    """Check if a value looks like a Fernet token."""
    if not value:
        return False
    try:
        # Fernet tokens are base64 and start with 'gAAA'
        return value.startswith('gAAA') and len(value) > 50
    except Exception:
        return False