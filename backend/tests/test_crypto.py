"""Mailbox credentials must never be readable from a database dump."""
from __future__ import annotations

import pytest

from app.core.crypto import (
    SecretDecryptionError,
    _fernet,
    decrypt_secret,
    encrypt_secret,
)


def test_round_trip():
    assert decrypt_secret(encrypt_secret("app-password-123")) == "app-password-123"


def test_ciphertext_does_not_contain_the_plaintext():
    ciphertext = encrypt_secret("hunter2-app-password")

    assert "hunter2" not in ciphertext
    assert ciphertext != "hunter2-app-password"


def test_same_plaintext_encrypts_differently_each_time():
    """Fernet includes a random IV, so identical passwords are not linkable."""
    assert encrypt_secret("same") != encrypt_secret("same")


def test_unicode_password_survives():
    secret = "رمز-عبور-١٢٣"

    assert decrypt_secret(encrypt_secret(secret)) == secret


def test_wrong_key_raises_an_actionable_error(monkeypatch):
    ciphertext = encrypt_secret("original")

    from app.core.config import settings

    _fernet.cache_clear()
    monkeypatch.setattr(settings, "mailbox_encryption_key", "a-completely-different-key")
    try:
        with pytest.raises(SecretDecryptionError) as excinfo:
            decrypt_secret(ciphertext)
        assert "Re-enter the mailbox password" in str(excinfo.value)
    finally:
        _fernet.cache_clear()
