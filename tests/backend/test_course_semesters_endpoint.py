from __future__ import annotations

from fastapi import FastAPI
from fastapi.testclient import TestClient

from backend.api import courses as courses_api


def _client(monkeypatch, rows, current: str) -> TestClient:
    monkeypatch.setattr(courses_api, "fetch_semesters_info", lambda verify_ssl=True: tuple(rows))
    monkeypatch.setattr(courses_api, "get_default_semester", lambda verify_ssl=True: current)
    app = FastAPI()
    app.include_router(courses_api.create_courses_router(lambda *a, **k: []))
    return TestClient(app)


def test_only_the_real_current_semester_is_marked_current(monkeypatch) -> None:
    # 學校對每個學期都標 CurrentSemester=true / Static=false，照抄會有 25 個 current，
    # 前端只是碰巧靠清單順序取到對的那個。
    rows = [
        {"Semester": "1151", "EngSemester": "2026 Fall", "CurrentSemester": True, "Static": False},
        {"Semester": "1142", "EngSemester": "2026 Spring", "CurrentSemester": True, "Static": False},
        {"Semester": "1141", "EngSemester": "2025 Fall", "CurrentSemester": True, "Static": False},
    ]
    payload = _client(monkeypatch, rows, "1151").get("/api/courses/semesters").json()
    assert [item["semester"] for item in payload if item["current"]] == ["1151"]
    assert len(payload) == 3


def test_entries_without_a_semester_code_are_dropped(monkeypatch) -> None:
    rows = [
        {"Semester": "1151", "EngSemester": "2026 Fall", "CurrentSemester": True, "Static": False},
        {"Semester": "", "EngSemester": "壞資料", "CurrentSemester": True, "Static": False},
    ]
    payload = _client(monkeypatch, rows, "1151").get("/api/courses/semesters").json()
    assert [item["semester"] for item in payload] == ["1151"]
