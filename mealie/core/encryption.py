import base64
import hashlib

from cryptography.fernet import Fernet, InvalidToken

from mealie.core.config import get_app_settings
from mealie.core.root_logger import get_logger

logger = get_logger("core.encryption")

ENCRYPTED_PREFIX = "enc:"


def _get_fernet() -> Fernet:
    secret = get_app_settings().SECRET or "default-insecure-secret-key-12345"
    key = base64.urlsafe_b64encode(hashlib.sha256(secret.encode("utf-8")).digest())
    return Fernet(key)


def encrypt_secret(value: str | None) -> str | None:
    """Encrypts a plaintext secret string using Fernet, prefixing with 'enc:'."""
    if value is None:
        return None
    if not value or value.startswith(ENCRYPTED_PREFIX):
        return value

    try:
        fernet = _get_fernet()
        token = fernet.encrypt(value.encode("utf-8")).decode("utf-8")
        return f"{ENCRYPTED_PREFIX}{token}"
    except Exception as e:
        logger.error(f"Failed to encrypt secret: {e}")
        return value


def decrypt_secret(value: str | None) -> str | None:
    """Decrypts an 'enc:' prefixed secret string. Returns unencrypted strings as-is for backward compatibility."""
    if value is None:
        return None
    if not value or not value.startswith(ENCRYPTED_PREFIX):
        return value

    token = value[len(ENCRYPTED_PREFIX) :]
    try:
        fernet = _get_fernet()
        return fernet.decrypt(token.encode("utf-8")).decode("utf-8")
    except InvalidToken:
        logger.warning("Failed to decrypt secret: invalid token or secret key mismatch")
        return value
    except Exception as e:
        logger.error(f"Failed to decrypt secret: {e}")
        return value
