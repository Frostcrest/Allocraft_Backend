"""
Token encryption utilities.

Provides symmetric AES-128-CBC encryption via Fernet for sensitive OAuth tokens
stored in the database (Schwab access_token, refresh_token).

Setup
-----
Generate a key once and store it as an environment variable::

    python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"

Then set TOKEN_ENCRYPTION_KEY=<output> in your .env file.

If TOKEN_ENCRYPTION_KEY is not set:
  - In development: a warning is logged and tokens are stored plaintext (no change
    from the old behaviour).
  - In production (ENVIRONMENT=production): the app raises RuntimeError at startup.
"""

import os
import logging
import base64

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Key setup
# ---------------------------------------------------------------------------
_raw_key = os.getenv("TOKEN_ENCRYPTION_KEY", "")
_fernet = None

if _raw_key:
    try:
        from cryptography.fernet import Fernet
        _fernet = Fernet(_raw_key.encode())
        logger.info("Token encryption enabled (Fernet).")
    except Exception as exc:
        logger.error("TOKEN_ENCRYPTION_KEY is set but invalid: %s", exc)
        _fernet = None
else:
    if os.getenv("ENVIRONMENT", "development") == "production":
        raise RuntimeError(
            "TOKEN_ENCRYPTION_KEY must be set in production to protect OAuth tokens at rest. "
            "Generate one with: python -c \"from cryptography.fernet import Fernet; "
            "print(Fernet.generate_key().decode())\""
        )
    logger.warning(
        "TOKEN_ENCRYPTION_KEY not set — Schwab OAuth tokens will be stored in plaintext. "
        "Set this env var before deploying to production."
    )


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def encrypt_token(plaintext: str | None) -> str | None:
    """
    Encrypt a plaintext token string.

    Returns the ciphertext as a UTF-8 string, or ``None`` if *plaintext* is
    ``None`` or empty.  If no encryption key is configured, the plaintext is
    returned unchanged (development fallback with a warning already logged).
    """
    if not plaintext:
        return plaintext
    if _fernet is None:
        return plaintext
    return _fernet.encrypt(plaintext.encode()).decode()


def decrypt_token(ciphertext: str | None) -> str | None:
    """
    Decrypt a ciphertext token string that was produced by :func:`encrypt_token`.

    Returns the plaintext, or ``None`` if *ciphertext* is ``None`` or empty.
    If no encryption key is configured, *ciphertext* is returned unchanged
    (matching the no-encryption development fallback of :func:`encrypt_token`).

    Raises ``ValueError`` on decryption failure (wrong key, corrupted data).
    """
    if not ciphertext:
        return ciphertext
    if _fernet is None:
        return ciphertext
    try:
        return _fernet.decrypt(ciphertext.encode()).decode()
    except Exception as exc:
        raise ValueError(f"Token decryption failed: {exc}") from exc


def is_encryption_enabled() -> bool:
    """Return True if a valid encryption key is configured."""
    return _fernet is not None
