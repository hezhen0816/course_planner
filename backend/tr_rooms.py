from __future__ import annotations

import re
from datetime import datetime, timedelta
from typing import Any

import requests

try:
    from .config import CLASS_PERIODS, DAY_CODES, DAY_NAMES, DEFAULT_TIMEOUT, QUERY_COURSE_API_URL, SEMESTERS_INFO_URL, TAIPEI
    from .models import TRRoomMeeting
    from .ntust_common import normalize
    from .time_utils import now
except ImportError:  # pragma: no cover
    from config import CLASS_PERIODS, DAY_CODES, DAY_NAMES, DEFAULT_TIMEOUT, QUERY_COURSE_API_URL, SEMESTERS_INFO_URL, TAIPEI
    from models import TRRoomMeeting
    from ntust_common import normalize
    from time_utils import now

ROOM_RE = re.compile(r"\bTR-\d+(?:-\d+)?\b", re.IGNORECASE)
_tr_course_cache: dict[str, tuple[datetime, list[dict[str, Any]]]] = {}

def query_course_payload(semester: str) -> dict[str, Any]:
    return {
        "Semester": semester,
        "CourseNo": "",
        "CourseName": "",
        "CourseTeacher": "",
        "Dimension": "",
        "CourseNotes": "",
        "CampusNotes": "Main_Campus",
        "ForeignLanguage": 0,
        "OnlyIntensive": 0,
        "OnlyGeneral": 0,
        "OnleyNTUST": 1,
        "OnlyMaster": 0,
        "OnlyUnderGraduate": 0,
        "OnlyNode": 0,
        "Language": "zh",
    }


def fetch_current_query_semester(verify_ssl: bool) -> str:
    response = requests.get(
        SEMESTERS_INFO_URL,
        headers={"Accept": "application/json", "User-Agent": "Mozilla/5.0"},
        timeout=DEFAULT_TIMEOUT,
        verify=verify_ssl,
    )
    response.raise_for_status()
    semesters = response.json()
    for item in semesters:
        if item.get("CurrentSemester") and item.get("Static") is False:
            return str(item["Semester"])
    if semesters:
        return str(semesters[0]["Semester"])
    raise RuntimeError("課程查詢系統沒有回傳可用學期。")


def fetch_query_courses(semester: str, refresh: bool, verify_ssl: bool) -> list[dict[str, Any]]:
    cached = _tr_course_cache.get(semester)
    if cached and not refresh:
        cached_at, courses = cached
        if (now() - cached_at).total_seconds() < 1800:
            return courses

    response = requests.post(
        QUERY_COURSE_API_URL,
        json=query_course_payload(semester),
        headers={
            "Accept": "application/json",
            "Content-Type": "application/json; charset=utf-8",
            "Origin": "https://querycourse.ntust.edu.tw",
            "Referer": "https://querycourse.ntust.edu.tw/querycourse/",
            "User-Agent": "Mozilla/5.0",
        },
        timeout=DEFAULT_TIMEOUT,
        verify=verify_ssl,
    )
    response.raise_for_status()
    courses = response.json()
    if not isinstance(courses, list):
        raise RuntimeError("課程查詢系統回傳格式不是課程清單。")

    _tr_course_cache[semester] = (now(), courses)
    return courses


def normalize_room_code(room: str | None) -> str | None:
    normalized = normalize(room).upper()
    return normalized or None


def split_tr_rooms(classroom_text: str | None) -> list[str]:
    if not classroom_text:
        return []
    return [match.group(0).upper() for match in ROOM_RE.finditer(classroom_text)]


def split_course_nodes(node_text: str | None) -> list[str]:
    if not node_text:
        return []
    return [part.strip().upper() for part in re.split(r"[,、\s]+", node_text) if part.strip()]


def build_tr_meetings(courses: list[dict[str, Any]]) -> list[TRRoomMeeting]:
    meetings: list[TRRoomMeeting] = []
    for course in courses:
        rooms = split_tr_rooms(str(course.get("ClassRoomNo") or ""))
        nodes = split_course_nodes(str(course.get("Node") or ""))
        if not rooms or not nodes:
            continue

        if len(rooms) == len(nodes):
            pairs = zip(rooms, nodes, strict=False)
        else:
            pairs = ((room, node) for room in sorted(set(rooms), key=room_sort_key) for node in nodes)

        for room, node in pairs:
            meetings.append(
                TRRoomMeeting(
                    room=room,
                    node=node,
                    course_no=str(course.get("CourseNo") or ""),
                    course_name=str(course.get("CourseName") or ""),
                    teacher=str(course.get("CourseTeacher") or ""),
                )
            )
    return meetings


def room_sort_key(room: str) -> tuple[int, str]:
    numbers = re.findall(r"\d+", room)
    first = int(numbers[0]) if numbers else 0
    return first, room


def node_from_datetime(moment: datetime) -> str | None:
    local_moment = moment.astimezone(TAIPEI)
    day_code = DAY_CODES[local_moment.weekday()]
    local_time = local_moment.time()
    for period, start, end in CLASS_PERIODS:
        if start <= local_time <= end:
            return f"{day_code}{period}"
    return None


def next_node_from_datetime(moment: datetime) -> str:
    local_moment = moment.astimezone(TAIPEI)
    day_code = DAY_CODES[local_moment.weekday()]
    local_time = local_moment.time()

    for index, (period, start, end) in enumerate(CLASS_PERIODS):
        if local_time < start:
            return f"{day_code}{period}"
        if start <= local_time <= end:
            if index + 1 < len(CLASS_PERIODS):
                next_period = CLASS_PERIODS[index + 1][0]
                return f"{day_code}{next_period}"
            break

    next_day = local_moment + timedelta(days=1)
    next_day_code = DAY_CODES[next_day.weekday()]
    first_period = CLASS_PERIODS[0][0]
    return f"{next_day_code}{first_period}"


def label_for_node(node: str | None, moment: datetime) -> str:
    if node is None:
        return "目前不是正式節次"
    day_name = DAY_NAMES.get(node[0], "未知星期")
    return f"{day_name} 第 {node[1:]} 節（{node}）"


def occupied_meetings(meetings: list[TRRoomMeeting], node: str | None) -> dict[str, list[TRRoomMeeting]]:
    if node is None:
        return {}

    occupied: dict[str, list[TRRoomMeeting]] = {}
    for meeting in meetings:
        if meeting.node == node:
            occupied.setdefault(meeting.room, []).append(meeting)
    return occupied

