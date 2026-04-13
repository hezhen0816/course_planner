from __future__ import annotations

from typing import Any
from urllib.parse import quote

import requests

try:
    from .config import DEFAULT_TIMEOUT, SUPABASE_SERVICE_ROLE_KEY, SUPABASE_URL
    from .schedule import group_schedule_entries
except ImportError:  # pragma: no cover
    from config import DEFAULT_TIMEOUT, SUPABASE_SERVICE_ROLE_KEY, SUPABASE_URL
    from schedule import group_schedule_entries


def _supabase_headers(content_type: bool = False) -> dict[str, str]:
    headers = {
        "apikey": SUPABASE_SERVICE_ROLE_KEY,
        "Authorization": f"Bearer {SUPABASE_SERVICE_ROLE_KEY}",
    }
    if content_type:
        headers["Content-Type"] = "application/json"
        headers["Prefer"] = "resolution=merge-duplicates,return=minimal"
    return headers


def _persist_snapshot(table: str, timestamp_field: str, profile_key: str, school_account: str, payload: dict[str, Any]) -> bool:
    if not SUPABASE_URL or not SUPABASE_SERVICE_ROLE_KEY:
        return False

    endpoint = f"{SUPABASE_URL}/rest/v1/{table}"
    body = {
        "profile_key": profile_key,
        "school_account": school_account,
        "payload": payload,
        timestamp_field: payload[timestamp_field],
    }
    if "student_name" in payload:
        body["student_name"] = payload.get("student_name")

    response = requests.post(endpoint, headers=_supabase_headers(content_type=True), json=body, timeout=DEFAULT_TIMEOUT)
    if response.status_code >= 300:
        raise RuntimeError(f"Supabase 寫入 {table} 失敗：{response.status_code} {response.text}")
    return True


def _load_snapshot(table: str, profile_key: str) -> dict[str, Any] | None:
    if not SUPABASE_URL or not SUPABASE_SERVICE_ROLE_KEY:
        return None

    endpoint = (
        f"{SUPABASE_URL}/rest/v1/{table}"
        f"?profile_key=eq.{quote(profile_key, safe='')}&select=payload"
    )
    response = requests.get(endpoint, headers=_supabase_headers(), timeout=DEFAULT_TIMEOUT)
    if response.status_code >= 300:
        raise RuntimeError(f"Supabase 讀取 {table} 失敗：{response.status_code} {response.text}")
    rows = response.json()
    if not rows:
        return None
    return rows[0]["payload"]


def persist_snapshot(profile_key: str, school_account: str, payload: dict[str, Any]) -> bool:
    return _persist_snapshot("schedule_sync_snapshots", "synced_at", profile_key, school_account, payload)


def load_snapshot(profile_key: str) -> dict[str, Any] | None:
    return _load_snapshot("schedule_sync_snapshots", profile_key)

def ensure_schedule_entry_slot_times(payload: dict[str, Any]) -> dict[str, Any]:
    schedule_entries = payload.get("schedule_entries")
    if not isinstance(schedule_entries, list) or not schedule_entries:
        return payload

    if all(isinstance(entry, dict) and entry.get("slot_times") for entry in schedule_entries):
        return payload

    courses = payload.get("courses")
    slots = payload.get("slots")
    if not isinstance(courses, list) or not isinstance(slots, list):
        return payload

    rebuilt_entries = group_schedule_entries(courses, slots)
    return {
        **payload,
        "schedule_entries": rebuilt_entries,
        "schedule_entry_count": len(rebuilt_entries),
    }



def persist_history_snapshot(profile_key: str, school_account: str, payload: dict[str, Any]) -> bool:
    return _persist_snapshot("history_import_snapshots", "imported_at", profile_key, school_account, payload)


def load_history_snapshot(profile_key: str) -> dict[str, Any] | None:
    return _load_snapshot("history_import_snapshots", profile_key)


def persist_moodle_assignments_snapshot(profile_key: str, school_account: str, payload: dict[str, Any]) -> bool:
    return _persist_snapshot("moodle_assignment_snapshots", "synced_at", profile_key, school_account, payload)


def load_moodle_assignments_snapshot(profile_key: str) -> dict[str, Any] | None:
    return _load_snapshot("moodle_assignment_snapshots", profile_key)
