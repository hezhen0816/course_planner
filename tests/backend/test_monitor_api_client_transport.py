from __future__ import annotations

import requests

from backend.monitor import api_client as mod


def _api() -> mod.NTUSTCourseAPI:
    api = mod.NTUSTCourseAPI.__new__(mod.NTUSTCourseAPI)
    api.verify_ssl = False
    api.session = requests.Session()
    api.last_request_latency_ms = None
    api.last_search_failed = False
    api._get_proxy_info_for_logging = lambda: ("直接連接", "")
    return api


def test_search_delegates_to_tr_rooms_with_session_and_timeout(monkeypatch) -> None:
    seen: dict = {}

    def fake_fetch(semester, **kw):
        seen.update(semester=semester, **kw)
        return [{"CourseNo": "CS1234"}]

    monkeypatch.setattr(mod, "fetch_query_courses_filtered", fake_fetch)
    api = _api()
    assert api.search_courses(semester="1141", course_no="CS1234") == [{"CourseNo": "CS1234"}]
    assert seen["session"] is api.session
    assert seen["timeout"] == mod.NTUSTCourseAPI.SEARCH_TIMEOUT
    assert seen["verify_ssl"] is False and seen["course_no"] == "CS1234"
    assert api.last_search_failed is False
    assert api.last_request_latency_ms is not None


def test_transport_error_sets_failed_flag_and_returns_empty(monkeypatch) -> None:
    def boom(*a, **kw):
        raise requests.exceptions.HTTPError("500")

    monkeypatch.setattr(mod, "fetch_query_courses_filtered", boom)
    api = _api()
    assert api.search_courses(semester="1141", course_no="X") == []
    assert api.last_search_failed is True


def test_network_disconnect_is_reraised(monkeypatch) -> None:
    def boom(*a, **kw):
        raise requests.exceptions.ConnectionError("offline")

    monkeypatch.setattr(mod, "fetch_query_courses_filtered", boom)
    monkeypatch.setattr(mod, "_is_network_disconnected", lambda e: True)
    api = _api()
    try:
        api.search_courses(semester="1141", course_no="X")
    except requests.exceptions.ConnectionError:
        pass
    else:
        raise AssertionError("disconnect must propagate")
