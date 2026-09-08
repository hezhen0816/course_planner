from __future__ import annotations

import time

from backend.monitor import worker as worker_mod
from backend.monitor.enrollment import EnrollmentClient


def _client() -> EnrollmentClient:
    return EnrollmentClient(verify_ssl=False, proxies={})


def test_three_failures_trigger_pause_callback_with_reason() -> None:
    client = _client()
    events: list[tuple] = []
    client.on_login_pause = lambda until, reason: events.append((until, reason))

    client._record_login_result(False, "err 1")
    client._record_login_result(False, "err 2")
    assert events == []
    client._record_login_result(False, "SSO error page")

    assert len(events) == 1
    until, reason = events[0]
    assert reason == "SSO error page"
    assert until > time.time() + EnrollmentClient.LOGIN_FAILURE_COOLDOWN_SECONDS - 5


def test_success_after_pause_emits_clear_event() -> None:
    client = _client()
    events: list[tuple] = []
    client.on_login_pause = lambda until, reason: events.append((until, reason))
    for _ in range(3):
        client._record_login_result(False, "x")
    client._record_login_result(True)

    assert events[-1] == (None, "")
    assert client._login_cooldown_until == 0.0


def test_seed_cooldown_ignores_expired_and_keeps_future() -> None:
    client = _client()
    client.seed_login_cooldown(time.time() - 10)
    assert client._login_cooldown_until == 0.0
    future = time.time() + 300
    client.seed_login_cooldown(future)
    assert client._login_cooldown_until == future


def test_parse_ts_handles_postgrest_iso_and_empty() -> None:
    assert worker_mod._parse_ts(None) is None
    assert worker_mod._parse_ts("not a date") is None
    ts = worker_mod._parse_ts("2026-09-08T01:02:03+00:00")
    assert ts is not None and int(ts) == 1788829323
    assert worker_mod._parse_ts("2026-09-08T01:02:03Z") == ts


def test_set_login_pause_writes_settings_and_log(monkeypatch) -> None:
    monkeypatch.setattr(worker_mod, "create_client", lambda url, key: object())
    monitor = worker_mod.SupabaseMonitor("http://supabase.local", "service-key")
    updates: list[tuple] = []
    logs: list[tuple] = []
    monkeypatch.setattr(monitor, "_db_update_with_retry", lambda t, d, c, v: updates.append((t, d, c, v)))
    monkeypatch.setattr(monitor, "_write_log", lambda msg, level="info", user_id=None: logs.append((level, user_id, msg)))

    monitor._set_login_pause("user-1", time.time() + 900, "bad password")
    assert updates[0][0] == "user_settings" and updates[0][2:] == ("user_id", "user-1")
    assert updates[0][1]["login_pause_reason"] == "bad password"
    assert updates[0][1]["login_paused_until"]
    assert logs[0][0] == "warn" and "暫停自動登入" in logs[0][2]

    monitor._set_login_pause("user-1", None, "")
    assert updates[1][1] == {"login_paused_until": None, "login_pause_reason": None}


def test_lookup_auth_email_uses_auth_admin_and_caches(monkeypatch) -> None:
    class _User:
        email = " who@example.com "

    class _Admin:
        calls = 0

        def get_user_by_id(self, uid):
            _Admin.calls += 1
            return type("Resp", (), {"user": _User()})()

    class _Client:
        auth = type("Auth", (), {"admin": _Admin()})()

    monkeypatch.setattr(worker_mod, "create_client", lambda url, key: _Client())
    monitor = worker_mod.SupabaseMonitor("http://supabase.local", "service-key")

    assert monitor._lookup_auth_email("u1") == "who@example.com"
    assert monitor._lookup_auth_email("u1") == "who@example.com"
    assert _Admin.calls == 1
    assert monitor._lookup_auth_email(None) == ""


def test_cooldown_escalates_15_30_60_and_resets_on_success() -> None:
    client = _client()
    untils: list[float] = []
    client.on_login_pause = lambda until, reason: untils.append(until) if until else None
    for expected_minutes in (15, 30, 60, 60):
        client._login_cooldown_until = 0.0  # simulate the previous cooldown having expired
        for _ in range(3):
            client._record_login_result(False, "x")
        assert abs((untils[-1] - time.time()) - expected_minutes * 60) < 5
    client._record_login_result(True)
    assert client._login_cooldown_streak == 0
    client._login_cooldown_until = 0.0
    for _ in range(3):
        client._record_login_result(False, "x")
    assert abs((untils[-1] - time.time()) - 15 * 60) < 5


def test_keepalive_skips_sso_when_no_course_has_auto_enroll(monkeypatch) -> None:
    from backend.monitor.config import CourseConfig, MonitorConfig
    from backend.monitor.monitor import CourseMonitor

    monitor = CourseMonitor.__new__(CourseMonitor)
    monitor.config = MonitorConfig(courses=[CourseConfig(course_no="A", semester="1141", auto_enroll=False)])
    monitor.last_session_check = 0.0
    monitor.last_session_keepalive = 0.0
    monitor.session_check_interval = 0
    monitor.session_keepalive_interval = 0
    called: list[str] = []
    monkeypatch.setattr(monitor, "_pre_login_if_needed", lambda: called.append("login") or True)
    monitor.enrollment_client = type("C", (), {"is_logged_in": False})()

    monitor._keep_session_alive_locked()
    assert called == []

    monitor.config.courses[0].auto_enroll = True
    monitor._keep_session_alive_locked()
    assert called == ["login"]
