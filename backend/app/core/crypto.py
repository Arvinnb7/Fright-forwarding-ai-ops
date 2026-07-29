"""Encryption for secrets stored at rest (mailbox credentials).

The product holds customers' mailbox passwords, so they must never sit in the
database in plaintext: a DB dump, a backup file, or a support engineer reading a
row must not expose a customer's email account.

Key material comes from ``MAILBOX_ENCRYPTION_KEY`` when set (recommended, and
rotatable independently). Otherwise it is derived deterministically from
``SECRET_KEY`` so a default deployment is still encrypted rather than plaintext.

⚠️ Rotating the key that encrypted existing rows makes them undecryptable — the
affected mailboxes simply need their password re-entered.
"""
from __future__ import annotations

import base64
import hashlib
from functools import lru_cache

from cryptography.fernet import Fernet, InvalidToken

from app.core.config import settings


class SecretDecryptionError(RuntimeError):
    """Raised when a stored secret cannot be decrypted with the current key."""


@lru_cache
def _fernet() -> Fernet:
    configured = (settings.mailbox_encryption_key or "").strip()
    if configured:
        key = configured.encode()
        # Accept either a ready Fernet key or arbitrary text we normalise.
        try:
            Fernet(key)
            return Fernet(key)
        except Exception:
            digest = hashlib.sha256(key).digest()
            return Fernet(base64.urlsafe_b64encode(digest))
    digest = hashlib.sha256(f"mailbox:{settings.secret_key}".encode()).digest()
    return Fernet(base64.urlsafe_b64encode(digest))


def encrypt_secret(plaintext: str) -> str:
    return _fernet().encrypt(plaintext.encode()).decode()


def decrypt_secret(ciphertext: str) -> str:
    try:
        return _fernet().decrypt(ciphertext.encode()).decode()
    except InvalidToken as exc:
        raise SecretDecryptionError(
            "Stored credential could not be decrypted — the encryption key "
            "changed. Re-enter the mailbox password."
        ) from exc
