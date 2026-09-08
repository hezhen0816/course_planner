from __future__ import annotations

import threading
import time
from concurrent.futures import ThreadPoolExecutor
from typing import Any

import requests


GPA_GRADE_API_URL = "https://myntust.com/api/v1/grades"

# The API is documented as 120 requests/minute and has no batch endpoint, so a
# 30-row search would spend 30 calls of that budget every time. GPA per course is
# the same for every user, so cache it process-wide for a day and fetch the
# misses with a small pool.
CACHE_TTL_SECONDS = 24 * 60 * 60
MAX_CACHE_ENTRIES = 5000
MAX_PARALLEL_REQUESTS = 4
REQUEST_TIMEOUT = 10

_cache: dict[str, tuple[float, float | None, str]] = {}
_cache_lock = threading.Lock()
# When the API answers 429 we stop the rest of the batch until this timestamp:
# hammering a rate-limited endpoint is what gets a token blocked.
_rate_limited_until = 0.0


def as_float(value: Any) -> float | None:
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def clear_cache() -> None:
    global _rate_limited_until
    with _cache_lock:
        _cache.clear()
        _rate_limited_until = 0.0


def _cached(course_no: str) -> tuple[float | None, str] | None:
    now = time.time()
    with _cache_lock:
        entry = _cache.get(course_no)
        if entry and entry[0] > now:
            return entry[1], entry[2]
        if entry:
            _cache.pop(course_no, None)
    return None


def _store(course_no: str, gpa: float | None, status: str) -> None:
    # "error" is transient (network, 5xx, rate limit): caching it would hide the
    # real value for a day.
    if status == "error":
        return
    now = time.time()
    with _cache_lock:
        if len(_cache) >= MAX_CACHE_ENTRIES:
            for key in [k for k, (expires, _, _) in _cache.items() if expires <= now]:
                _cache.pop(key, None)
            if len(_cache) >= MAX_CACHE_ENTRIES:
                _cache.clear()
        _cache[course_no] = (now + CACHE_TTL_SECONDS, gpa, status)


def _retry_after_seconds(response: requests.Response) -> float:
    try:
        return max(1.0, min(300.0, float(response.headers.get("Retry-After", "60"))))
    except (TypeError, ValueError):
        return 60.0


def fetch_course_gpa(course_no: str, api_key: str, verify_ssl: bool) -> tuple[float | None, str]:
    """GPA for one course. Statuses: found / no_data / error / not_enabled / rate_limited."""
    global _rate_limited_until

    normalized_course_no = course_no.strip().upper()
    if not normalized_course_no or not api_key.strip():
        return None, "not_enabled"

    hit = _cached(normalized_course_no)
    if hit is not None:
        return hit

    with _cache_lock:
        paused_until = _rate_limited_until
    if paused_until > time.time():
        return None, "rate_limited"

    try:
        response = requests.get(
            f"{GPA_GRADE_API_URL}/{normalized_course_no}",
            headers={
                "Accept": "application/json",
                "Authorization": f"Bearer {api_key.strip()}",
            },
            timeout=REQUEST_TIMEOUT,
            verify=verify_ssl,
        )
        if response.status_code == 429:
            with _cache_lock:
                _rate_limited_until = time.time() + _retry_after_seconds(response)
            return None, "rate_limited"
        if response.status_code == 404:
            _store(normalized_course_no, None, "no_data")
            return None, "no_data"
        if response.status_code >= 400:
            return None, "error"
        payload = response.json()
    except (ValueError, requests.RequestException):
        return None, "error"

    if not isinstance(payload, dict) or payload.get("success") is False:
        _store(normalized_course_no, None, "no_data")
        return None, "no_data"
    data = payload.get("data")
    if not isinstance(data, dict):
        _store(normalized_course_no, None, "no_data")
        return None, "no_data"
    gpa = as_float(data.get("gpa"))
    if gpa is None:
        _store(normalized_course_no, None, "no_data")
        return None, "no_data"
    _store(normalized_course_no, gpa, "found")
    return gpa, "found"


def fetch_course_gpas(
    course_nos: list[str], api_key: str, verify_ssl: bool
) -> dict[str, tuple[float | None, str]]:
    """GPA for many courses: cache hits are free, misses go out a few at a time.

    Deduplicates course codes so repeated sections cost one request, and stops
    early once the API reports a rate limit (remaining codes come back
    "rate_limited" rather than adding to the flood).
    """
    unique = list(dict.fromkeys(c.strip().upper() for c in course_nos if c and c.strip()))
    if not unique or not api_key.strip():
        return {c: (None, "not_enabled") for c in unique}

    results: dict[str, tuple[float | None, str]] = {}
    misses: list[str] = []
    for course_no in unique:
        hit = _cached(course_no)
        if hit is not None:
            results[course_no] = hit
        else:
            misses.append(course_no)

    if misses:
        workers = min(MAX_PARALLEL_REQUESTS, len(misses))
        with ThreadPoolExecutor(max_workers=workers) as pool:
            for course_no, outcome in zip(
                misses, pool.map(lambda c: fetch_course_gpa(c, api_key, verify_ssl), misses)
            ):
                results[course_no] = outcome
    return results
