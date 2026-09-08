from __future__ import annotations

import base64
import json
import time

import pytest

from backend import credentials


class _Resp:
    def __init__(self, payload, status_code=200):
        self._payload = payload
        self.status_code = status_code

    def raise_for_status(self):
        return None

    def json(self):
        return self._payload


def _jwt(exp: float | None) -> str:
    body = {"sub": "u"} if exp is None else {"sub": "u", "exp": exp}
    seg = base64.urlsafe_b64encode(json.dumps(body).encode()).decode().rstrip("=")
    return f"hdr.{seg}.sig"


@pytest.fixture
def auth(monkeypatch):
    calls: list[str] = []
    monkeypatch.setattr(credentials, "SUPABASE_URL", "https://example.supabase.co")
    monkeypatch.setattr(credentials, "SUPABASE_ANON_KEY", "anon-key")
    monkeypatch.setattr(credentials.requests, "get", lambda url, headers, timeout: calls.append(headers["Authorization"]) or _Resp({"id": "user-1"}))
    return calls


def test_second_lookup_within_ttl_is_served_from_cache(auth) -> None:
    assert credentials.resolve_user_id("tok-a") == "user-1"
    assert credentials.resolve_user_id("tok-a") == "user-1"
    assert auth == ["Bearer tok-a"]


def test_different_tokens_are_cached_separately(auth) -> None:
    credentials.resolve_user_id("tok-a")
    credentials.resolve_user_id("tok-b")
    assert auth == ["Bearer tok-a", "Bearer tok-b"]


def test_cache_expires_after_ttl(auth, monkeypatch) -> None:
    credentials.resolve_user_id("tok-a")
    real_time = time.time
    monkeypatch.setattr(credentials.time, "time", lambda: real_time() + credentials.USER_ID_CACHE_TTL_SECONDS + 1)
    credentials.resolve_user_id("tok-a")
    assert len(auth) == 2


def test_cache_never_outlives_jwt_exp(auth) -> None:
    token = _jwt(time.time() + 2)  # expires in 2s, well under the 60s TTL
    credentials.resolve_user_id(token)
    entry = credentials._user_id_cache[credentials._cache_key(token)]
    assert entry[1] <= time.time() + 2.5


def test_already_expired_jwt_is_not_cached(auth) -> None:
    token = _jwt(time.time() - 10)
    credentials.resolve_user_id(token)
    assert credentials._cache_key(token) not in credentials._user_id_cache


def test_failures_are_not_cached(monkeypatch) -> None:
    monkeypatch.setattr(credentials, "SUPABASE_URL", "https://example.supabase.co")
    monkeypatch.setattr(credentials, "SUPABASE_ANON_KEY", "anon-key")
    monkeypatch.setattr(credentials.requests, "get", lambda url, headers, timeout: _Resp({}, status_code=401))
    with pytest.raises(credentials.CredentialStoreError):
        credentials.resolve_user_id("bad")
    assert credentials._user_id_cache == {}
