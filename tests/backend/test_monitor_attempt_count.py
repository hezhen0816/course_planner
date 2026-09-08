from __future__ import annotations

from backend.monitor import worker as worker_mod
from backend.monitor.config import CourseConfig


def _make_monitor(monkeypatch) -> worker_mod.SupabaseMonitor:
    monkeypatch.setattr(worker_mod, "create_client", lambda url, key: object())
    return worker_mod.SupabaseMonitor("http://supabase.local", "service-key")


def _course(count: int) -> CourseConfig:
    course = CourseConfig(course_no="CS1234", semester="1141", attempt_count=count)
    course.db_id = "row-1"
    return course


def test_sync_prefers_larger_value_when_db_lags_memory(monkeypatch) -> None:
    monitor = _make_monitor(monkeypatch)
    monitor.enrollment_attempts_per_user["u1"] = {"CS1234": 2}

    course = _course(1)
    monitor._sync_attempt_count_from_db("u1", course)

    assert monitor.enrollment_attempts_per_user["u1"]["CS1234"] == 2
    assert course.attempt_count == 2


def test_sync_restores_count_after_restart(monkeypatch) -> None:
    monitor = _make_monitor(monkeypatch)

    course = _course(3)
    monitor._sync_attempt_count_from_db("u1", course)

    assert monitor.enrollment_attempts_per_user["u1"]["CS1234"] == 3


def test_sync_zero_resets_memory_and_limit_notice(monkeypatch) -> None:
    monitor = _make_monitor(monkeypatch)
    monitor.enrollment_attempts_per_user["u1"] = {"CS1234": 3}
    monitor._limit_notified_at[("u1", "CS1234")] = 123.0

    course = _course(0)
    monitor._sync_attempt_count_from_db("u1", course)

    assert monitor.enrollment_attempts_per_user["u1"]["CS1234"] == 0
    assert ("u1", "CS1234") not in monitor._limit_notified_at


def test_persist_writes_attempt_count_to_supabase(monkeypatch) -> None:
    monitor = _make_monitor(monkeypatch)
    calls: list[tuple] = []
    monkeypatch.setattr(
        monitor,
        "_db_update_with_retry",
        lambda table, data, match_col, match_val: calls.append((table, data, match_col, match_val)),
    )

    course = _course(1)
    monitor._persist_attempt_count(course, 2)

    assert course.attempt_count == 2
    assert calls == [("monitored_courses", {"attempt_count": 2}, "id", "row-1")]
