from __future__ import annotations

from backend.monitor import worker as worker_mod


def _monitor(monkeypatch) -> worker_mod.SupabaseMonitor:
    monkeypatch.setattr(worker_mod, "create_client", lambda url, key: object())
    m = worker_mod.SupabaseMonitor("http://supabase.local", "service-key")
    m._updates = []
    m._logs = []
    monkeypatch.setattr(m, "_db_update_with_retry", lambda t, d, c, v: m._updates.append((t, d, v)))
    monkeypatch.setattr(m, "_write_log", lambda msg, level="info", user_id=None: m._logs.append((level, user_id, msg)))
    return m


def _row(semester: str) -> dict:
    return {"id": "row-1", "user_id": "u1", "course_code": "PE112A042", "course_name": "體育(羽球)(上)", "semester": semester}


def test_past_semester_is_expired_and_logged(monkeypatch) -> None:
    m = _monitor(monkeypatch)
    assert m._expire_if_past_semester(_row("1141"), "1151") is True
    assert m._updates == [("monitored_courses", {"status": "expired"}, "row-1")]
    level, user_id, msg = m._logs[0]
    assert level == "warn" and user_id == "u1" and "1141" in msg


def test_current_and_future_semesters_are_kept(monkeypatch) -> None:
    m = _monitor(monkeypatch)
    assert m._expire_if_past_semester(_row("1151"), "1151") is False
    assert m._expire_if_past_semester(_row("1152"), "1151") is False
    assert m._updates == []


def test_summer_term_sorts_between_terms(monkeypatch) -> None:
    m = _monitor(monkeypatch)
    # 114H（114 學年暑期）早於 1151，晚於 1142
    assert m._expire_if_past_semester(_row("114H"), "1151") is True
    m._updates.clear()
    assert m._expire_if_past_semester(_row("114H"), "1142") is False


def test_unknown_current_semester_expires_nothing(monkeypatch) -> None:
    m = _monitor(monkeypatch)
    assert m._expire_if_past_semester(_row("1121"), "") is False
    assert m._expire_if_past_semester({"id": "x", "semester": None}, "1151") is False
    assert m._updates == []


def test_write_failure_keeps_the_course_in_rotation(monkeypatch) -> None:
    m = _monitor(monkeypatch)

    def boom(*a, **kw):
        raise RuntimeError("db down")

    monkeypatch.setattr(m, "_db_update_with_retry", boom)
    # 標記失敗就不要跳過，否則這門課會靜默消失在監控清單裡
    assert m._expire_if_past_semester(_row("1141"), "1151") is False
