from __future__ import annotations

from backend.monitor import crypto as crypto_mod
from backend import credentials


def test_crypto_manager_uses_shared_secret_roundtrip(monkeypatch) -> None:
    monkeypatch.setattr(credentials, "SCHOOL_CREDENTIALS_ENCRYPTION_SECRET", "x" * 40)
    cm = crypto_mod.CryptoManager()
    token = cm.encrypt("hunter2")
    assert token != "hunter2"
    assert cm.is_ciphertext(token)
    assert cm.decrypt(token) == "hunter2"
    # same secret as app_private.school_credentials
    assert credentials.decrypt_sensitive_value(token) == "hunter2"


def test_crypto_manager_without_secret_fails_closed(monkeypatch) -> None:
    monkeypatch.setattr(credentials, "SCHOOL_CREDENTIALS_ENCRYPTION_SECRET", "")
    cm = crypto_mod.CryptoManager()
    assert cm.fernet is None
    assert cm.is_ciphertext("anything") is False
    try:
        cm.decrypt("anything")
    except crypto_mod.CryptoError:
        pass
    else:
        raise AssertionError("decrypt must not fail open")
