from __future__ import annotations

import backend.gpa as gpa


class _Resp:
    def __init__(self, status_code=200, payload=None, headers=None):
        self.status_code = status_code
        self._payload = payload if payload is not None else {"success": True, "data": {"gpa": 3.5}}
        self.headers = headers or {}

    def json(self):
        return self._payload


def _patch(monkeypatch, responses):
    calls: list[str] = []

    def fake_get(url, headers, timeout, verify):
        course = url.rsplit("/", 1)[-1]
        calls.append(course)
        result = responses(course) if callable(responses) else responses
        if isinstance(result, Exception):
            raise result
        return result

    monkeypatch.setattr(gpa.requests, "get", fake_get)
    return calls


def setup_function() -> None:
    gpa.clear_cache()


def test_second_lookup_of_same_course_is_cached(monkeypatch) -> None:
    calls = _patch(monkeypatch, _Resp())
    assert gpa.fetch_course_gpa("cs1234", "key", False) == (3.5, "found")
    assert gpa.fetch_course_gpa("CS1234", "key", False) == (3.5, "found")
    assert calls == ["CS1234"]


def test_no_data_is_cached_but_errors_are_not(monkeypatch) -> None:
    calls = _patch(monkeypatch, _Resp(status_code=404))
    gpa.fetch_course_gpa("A1", "key", False)
    gpa.fetch_course_gpa("A1", "key", False)
    assert calls == ["A1"]

    gpa.clear_cache()
    calls = _patch(monkeypatch, _Resp(status_code=500))
    assert gpa.fetch_course_gpa("B1", "key", False) == (None, "error")
    assert gpa.fetch_course_gpa("B1", "key", False) == (None, "error")
    assert calls == ["B1", "B1"]


def test_429_pauses_further_requests(monkeypatch) -> None:
    calls = _patch(monkeypatch, _Resp(status_code=429, headers={"Retry-After": "30"}))
    assert gpa.fetch_course_gpa("C1", "key", False) == (None, "rate_limited")
    assert gpa.fetch_course_gpa("C2", "key", False) == (None, "rate_limited")
    assert calls == ["C1"]  # the second one never left the process


def test_batch_dedupes_and_uses_cache(monkeypatch) -> None:
    calls = _patch(monkeypatch, lambda c: _Resp(payload={"success": True, "data": {"gpa": 4.0}}))
    out = gpa.fetch_course_gpas(["X1", "x1", "X2", ""], "key", False)
    assert out == {"X1": (4.0, "found"), "X2": (4.0, "found")}
    assert sorted(calls) == ["X1", "X2"]

    out2 = gpa.fetch_course_gpas(["X1", "X2"], "key", False)
    assert out2 == out
    assert sorted(calls) == ["X1", "X2"]


def test_batch_without_key_reports_not_enabled(monkeypatch) -> None:
    assert gpa.fetch_course_gpas(["X1"], "  ", False) == {"X1": (None, "not_enabled")}
