from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from typing import Any

import requests

try:
    from .config import DEFAULT_TIMEOUT, SUPABASE_URL
    from .credentials import (
        CredentialStoreError,
        decrypt_sensitive_value,
        encrypt_sensitive_value,
        _service_role_headers,
    )
except ImportError:  # pragma: no cover
    from config import DEFAULT_TIMEOUT, SUPABASE_URL
    from credentials import (
        CredentialStoreError,
        decrypt_sensitive_value,
        encrypt_sensitive_value,
        _service_role_headers,
    )


OFFICIAL_SESSION_TTL_SECONDS = 25 * 60


def session_state_from_requests_session(session: "requests.Session", *, is_logged_in: bool = True) -> dict[str, Any]:
    """Serialise a requests.Session cookie jar into the school_sessions state format."""
    cookies: list[dict[str, Any]] = []
    for cookie in session.cookies:
        cookies.append(
            {
                "name": cookie.name,
                "value": cookie.value,
                "domain": cookie.domain,
                "path": cookie.path,
                "expires": cookie.expires,
                "secure": cookie.secure,
                "rest": dict(getattr(cookie, "_rest", {}) or {}),
            }
        )
    return {
        "cookies": cookies,
        "is_logged_in": is_logged_in,
        "saved_at": datetime.now(timezone.utc).isoformat(),
    }


def official_session_expires_at() -> datetime:
    return datetime.now(timezone.utc) + timedelta(seconds=OFFICIAL_SESSION_TTL_SECONDS)


def encrypt_school_session_state(session_state: dict[str, Any]) -> str:
    raw = json.dumps(session_state, ensure_ascii=True, separators=(",", ":"))
    return encrypt_sensitive_value(raw)


def decrypt_school_session_state(ciphertext: str) -> dict[str, Any]:
    try:
        payload = json.loads(decrypt_sensitive_value(ciphertext))
    except json.JSONDecodeError as exc:
        raise CredentialStoreError("已保存的官方選課 session 格式無法解析，請重新同步。") from exc
    if not isinstance(payload, dict):
        raise CredentialStoreError("已保存的官方選課 session 格式錯誤，請重新同步。")
    return payload


def _rpc_url(name: str) -> str:
    return f"{SUPABASE_URL}/rest/v1/rpc/{name}"


def _post_rpc(name: str, payload: dict[str, Any]) -> requests.Response:
    response = requests.post(
        _rpc_url(name),
        headers=_service_role_headers(json_body=True),
        json=payload,
        timeout=DEFAULT_TIMEOUT,
    )
    response.raise_for_status()
    return response


def load_school_session_state(user_id: str, username: str) -> dict[str, Any] | None:
    if not username.strip():
        return None
    response = _post_rpc(
        "get_school_session",
        {"p_user_id": user_id, "p_school_account": username.strip()},
    )
    rows = response.json()
    if not rows:
        return None
    row = rows[0] if isinstance(rows, list) else rows
    if not isinstance(row, dict):
        return None
    ciphertext = str(row.get("session_ciphertext") or "")
    if not ciphertext:
        return None
    return {
        "school_account": str(row.get("school_account") or username),
        "session_state": decrypt_school_session_state(ciphertext),
        "expires_at": row.get("expires_at"),
        "last_keep_alive_at": row.get("last_keep_alive_at"),
    }


def save_school_session_state(
    user_id: str,
    username: str,
    session_state: dict[str, Any],
    *,
    expires_at: datetime | None = None,
    last_keep_alive_at: datetime | None = None,
) -> None:
    if not username.strip():
        return
    _post_rpc(
        "upsert_school_session",
        {
            "p_user_id": user_id,
            "p_school_account": username.strip(),
            "p_session_ciphertext": encrypt_school_session_state(session_state),
            "p_expires_at": (expires_at or official_session_expires_at()).isoformat(),
            "p_last_keep_alive_at": (last_keep_alive_at or datetime.now(timezone.utc)).isoformat(),
        },
    )


def delete_school_session(user_id: str, username: str | None = None) -> None:
    _post_rpc(
        "delete_school_session",
        {"p_user_id": user_id, "p_school_account": username.strip() if username else None},
    )
