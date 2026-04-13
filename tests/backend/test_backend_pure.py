from __future__ import annotations

from datetime import datetime
from zoneinfo import ZoneInfo

from backend import moodle, snapshots, tr_rooms
from backend.schedule import group_schedule_entries


def test_group_schedule_entries_orders_slots_and_preserves_metadata() -> None:
    courses = [
        {
            "course_name": "資料結構",
            "required_type": "必修",
            "professor": "王小明",
        }
    ]
    slots = [
        {
            "weekday_key": "monday",
            "weekday_label": "星期一",
            "time": "09:10 - 10:00",
            "course_name": "資料結構",
            "location": "TR-312",
        },
        {
            "weekday_key": "monday",
            "weekday_label": "星期一",
            "time": "08:10 - 09:00",
            "course_name": "資料結構",
            "location": "TR-312",
        },
    ]

    entries = group_schedule_entries(courses, slots)

    assert entries == [
        {
            "weekday_key": "monday",
            "weekday_label": "星期一",
            "title": "資料結構",
            "time_range": "08:10 - 10:00",
            "slot_times": ["08:10 - 09:00", "09:10 - 10:00"],
            "room": "TR-312",
            "instructor": "王小明",
            "accent": "compulsory",
        }
    ]


def test_tr_room_parsing_and_node_selection() -> None:
    meetings = tr_rooms.build_tr_meetings(
        [
            {
                "ClassRoomNo": "TR-213 / TR-514-1",
                "Node": "M1,M2",
                "CourseNo": "CS101",
                "CourseName": "演算法",
                "CourseTeacher": "林老師",
            }
        ]
    )
    moment = datetime(2026, 4, 13, 8, 30, tzinfo=ZoneInfo("Asia/Taipei"))

    assert [meeting.room for meeting in meetings] == ["TR-213", "TR-514-1"]
    assert tr_rooms.node_from_datetime(moment) == "M1"
    assert tr_rooms.next_node_from_datetime(moment) == "M2"
    assert tr_rooms.occupied_meetings(meetings, "M1")["TR-213"][0].course_name == "演算法"


def test_moodle_assignment_filter_keeps_actionable_items_and_sorts() -> None:
    items = [
        {
            "due_at": "2026-04-15T10:00:00+08:00",
            "title": "閱讀公告",
            "course_name": "A",
            "action_label": "",
            "action_url": "",
            "event_url": "/mod/forum/view.php",
            "module_name": "forum",
            "event_type": "due",
        },
        {
            "due_at": "2026-04-14T10:00:00+08:00",
            "title": "小考",
            "course_name": "B",
            "action_label": "",
            "action_url": "/mod/quiz/view.php",
            "event_url": "",
            "module_name": "quiz",
            "event_type": "due",
        },
        {
            "due_at": "2026-04-13T10:00:00+08:00",
            "title": "作業一",
            "course_name": "A",
            "action_label": "繳交作業",
            "action_url": "/mod/assign/view.php",
            "event_url": "",
            "module_name": "assign",
            "event_type": "due",
        },
    ]

    filtered = moodle.filter_moodle_assignment_items(items)

    assert [item["title"] for item in filtered] == ["作業一", "小考"]


def test_supabase_load_snapshot_builds_encoded_query(monkeypatch) -> None:
    seen: dict[str, object] = {}
    monkeypatch.setattr(snapshots, "SUPABASE_URL", "https://example.supabase.co")
    monkeypatch.setattr(snapshots, "SUPABASE_SERVICE_ROLE_KEY", "service-key")

    class Response:
        status_code = 200
        text = "ok"

        @staticmethod
        def json() -> list[dict[str, object]]:
            return [{"payload": {"ok": True}}]

    def fake_get(url: str, **kwargs: object) -> Response:
        seen["url"] = url
        seen["headers"] = kwargs["headers"]
        return Response()

    monkeypatch.setattr(snapshots.requests, "get", fake_get)

    assert snapshots.load_snapshot("abc/123") == {"ok": True}
    assert seen["url"] == (
        "https://example.supabase.co/rest/v1/schedule_sync_snapshots"
        "?profile_key=eq.abc%2F123&select=payload"
    )


def test_supabase_persist_snapshot_reuses_common_writer(monkeypatch) -> None:
    seen: dict[str, object] = {}
    monkeypatch.setattr(snapshots, "SUPABASE_URL", "https://example.supabase.co")
    monkeypatch.setattr(snapshots, "SUPABASE_SERVICE_ROLE_KEY", "service-key")

    class Response:
        status_code = 201
        text = "created"

    def fake_post(url: str, **kwargs: object) -> Response:
        seen["url"] = url
        seen["json"] = kwargs["json"]
        seen["headers"] = kwargs["headers"]
        return Response()

    monkeypatch.setattr(snapshots.requests, "post", fake_post)

    assert snapshots.persist_history_snapshot(
        profile_key="profile",
        school_account="student",
        payload={
            "imported_at": "2026-04-13T10:00:00+08:00",
            "student_name": "測試學生",
            "records": [],
        },
    )
    assert seen["url"] == "https://example.supabase.co/rest/v1/history_import_snapshots"
    assert seen["json"] == {
        "profile_key": "profile",
        "school_account": "student",
        "payload": {
            "imported_at": "2026-04-13T10:00:00+08:00",
            "student_name": "測試學生",
            "records": [],
        },
        "imported_at": "2026-04-13T10:00:00+08:00",
        "student_name": "測試學生",
    }
