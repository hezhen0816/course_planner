from __future__ import annotations

from functools import lru_cache
from typing import Any

import requests

from .utils import setup_logging, validate_semester

logger = setup_logging()

SEMESTERS_INFO_URL = "https://querycourse.ntust.edu.tw/QueryCourse/api/semestersinfo"
def _guess_semester_from_date() -> str:
    """Last-resort fallback: ROC academic year + term derived from today (Aug–Jan = 1, Feb–Jul = 2)."""
    from datetime import date
    today = date.today()
    roc_year = today.year - 1911 if today.month >= 8 else today.year - 1912
    term = 1 if (today.month >= 8 or today.month <= 1) else 2
    return f"{roc_year}{term}"


DEFAULT_SEMESTER = _guess_semester_from_date()


def _extract_semester(items: Any) -> str:
    if not isinstance(items, list) or not items:
        return ""

    current_candidates = [
        str(item.get("Semester") or "").strip()
        for item in items
        if isinstance(item, dict) and item.get("CurrentSemester") and item.get("Static") is False
    ]
    for semester in current_candidates:
        if validate_semester(semester):
            return semester

    for item in items:
        if not isinstance(item, dict):
            continue
        semester = str(item.get("Semester") or "").strip()
        if validate_semester(semester):
            return semester
    return ""


def _extract_semester_candidates(items: Any) -> list[str]:
    if not isinstance(items, list) or not items:
        return []

    candidates: list[str] = []
    for item in items:
        if not isinstance(item, dict):
            continue
        semester = str(item.get("Semester") or "").strip()
        if validate_semester(semester) and semester not in candidates:
            candidates.append(semester)
    return candidates


@lru_cache(maxsize=1)
def fetch_semesters_info(verify_ssl: bool = True) -> tuple[dict[str, Any], ...]:
    """官方學期清單原始資料。三處（monitor、tr_rooms、api/courses）共用這一支，
    不要各自再打一次 semestersinfo。回 tuple 是為了能放進 lru_cache。"""
    response = requests.get(
        SEMESTERS_INFO_URL,
        headers={"Accept": "application/json", "User-Agent": "Mozilla/5.0"},
        timeout=15,
        verify=verify_ssl,
    )
    response.raise_for_status()
    payload = response.json()
    return tuple(payload) if isinstance(payload, list) else ()


def fetch_current_semester(verify_ssl: bool = True) -> str:
    semester = _extract_semester(list(fetch_semesters_info(verify_ssl=verify_ssl)))
    if semester:
        logger.info(f"已取得官方最新學期: {semester}")
        return semester
    raise RuntimeError("課程查詢系統沒有回傳可用學期。")


def fetch_semester_candidates(verify_ssl: bool = True) -> list[str]:
    candidates = _extract_semester_candidates(list(fetch_semesters_info(verify_ssl=verify_ssl)))
    if candidates:
        logger.info(f"已取得官方學期候選清單: {', '.join(candidates[:5])}")
    return candidates


def get_default_semester(verify_ssl: bool = True) -> str:
    try:
        return fetch_current_semester(verify_ssl=verify_ssl)
    except Exception as exc:
        reason = f"{type(exc).__name__}: {exc}"
        candidates = fetch_semester_candidates(verify_ssl=verify_ssl)
        if candidates:
            logger.warning(f"無法直接取得官方最新學期，改用學期候選清單第一筆 {candidates[0]}（{reason}）")
            return candidates[0]
        logger.warning(f"無法取得官方最新學期，且候選清單為空，改用預設 {DEFAULT_SEMESTER}（{reason}）")
        return DEFAULT_SEMESTER
