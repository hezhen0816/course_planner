from __future__ import annotations

from typing import Any

import requests


GPA_GRADE_API_URL = "https://myntust.com/api/v1/grades"


def as_float(value: Any) -> float | None:
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def fetch_course_gpa(course_no: str, api_key: str, verify_ssl: bool) -> tuple[float | None, str]:
    normalized_course_no = course_no.strip().upper()
    if not normalized_course_no or not api_key.strip():
        return None, "not_enabled"

    try:
        response = requests.get(
            f"{GPA_GRADE_API_URL}/{normalized_course_no}",
            headers={
                "Accept": "application/json",
                "Authorization": f"Bearer {api_key.strip()}",
            },
            timeout=10,
            verify=verify_ssl,
        )
        if response.status_code == 404:
            return None, "no_data"
        if response.status_code >= 400:
            return None, "error"
        payload = response.json()
    except (ValueError, requests.RequestException):
        return None, "error"

    if not isinstance(payload, dict) or payload.get("success") is False:
        return None, "no_data"
    data = payload.get("data")
    if not isinstance(data, dict):
        return None, "no_data"
    gpa = as_float(data.get("gpa"))
    if gpa is None:
        return None, "no_data"
    return gpa, "found"
