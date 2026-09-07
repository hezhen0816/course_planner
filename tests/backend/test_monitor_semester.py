from __future__ import annotations

from backend.monitor import semester as semester_mod


def test_fetch_current_semester_prefers_official_current_semester(monkeypatch) -> None:
    semester_mod.fetch_current_semester.cache_clear()

    class FakeResponse:
        def raise_for_status(self) -> None:
            return None

        def json(self):
            return [
                {"Semester": "1151", "CurrentSemester": False, "Static": False},
                {"Semester": "1152", "CurrentSemester": True, "Static": False},
            ]

    monkeypatch.setattr(semester_mod.requests, "get", lambda *args, **kwargs: FakeResponse())

    assert semester_mod.fetch_current_semester(verify_ssl=False) == "1152"


def test_get_default_semester_falls_back_to_first_candidate(monkeypatch) -> None:
    semester_mod.fetch_current_semester.cache_clear()
    semester_mod.fetch_semester_candidates.cache_clear()

    def raise_error(*args, **kwargs):
        raise RuntimeError("boom")

    monkeypatch.setattr(semester_mod, "fetch_current_semester", raise_error)
    monkeypatch.setattr(semester_mod, "fetch_semester_candidates", lambda verify_ssl=True: ["1151", "1142"])

    assert semester_mod.get_default_semester(verify_ssl=False) == "1151"
