from __future__ import annotations

from datetime import datetime
import re
from typing import Any

import requests
from bs4 import BeautifulSoup, Tag

try:
    from .config import DEFAULT_TIMEOUT, MOODLE_DASHBOARD_URL, TAIPEI
    from .ntust_common import login_to_target, normalize, split_lines
    from .time_utils import now
except ImportError:  # pragma: no cover
    from config import DEFAULT_TIMEOUT, MOODLE_DASHBOARD_URL, TAIPEI
    from ntust_common import login_to_target, normalize, split_lines
    from time_utils import now

def extract_moodle_timeline_config(soup: BeautifulSoup) -> dict[str, int | str]:
    timeline = soup.select_one('[data-region="timeline"]')
    if not isinstance(timeline, Tag):
        raise RuntimeError("找不到 Moodle 時間軸區塊。")

    event_container = timeline.select_one('[data-region="event-list-container"]')
    view_dates = timeline.select_one('[data-region="view-dates"]')
    if not isinstance(event_container, Tag) or not isinstance(view_dates, Tag):
        raise RuntimeError("找不到 Moodle 時間軸 API 設定。")

    parsed_days_limit = int(event_container.get("data-days-limit", "7"))
    parsed_limit_num = int(view_dates.get("data-limit", "5")) + 1

    return {
        "filter_label": "往後30天",
        "midnight": int(event_container.get("data-midnight", "0")),
        "days_limit": max(parsed_days_limit, 30),
        "limit_num": min(max(parsed_limit_num, 50), 50),
    }


def fetch_moodle_timeline_items(
    session: requests.Session,
    html: str,
    timeline_config: dict[str, int | str],
    verify_ssl: bool,
) -> list[dict[str, Any]]:
    sesskey_match = re.search(r'"sesskey":"([^"]+)"', html)
    if not sesskey_match:
        raise RuntimeError("找不到 Moodle sesskey。")

    payload = [
        {
            "index": 0,
            "methodname": "core_calendar_get_action_events_by_timesort",
            "args": {
                "limitnum": int(timeline_config["limit_num"]),
                "timesortfrom": int(timeline_config["midnight"]),
                "timesortto": int(timeline_config["midnight"]) + int(timeline_config["days_limit"]) * 86400,
                "limittononsuspendedevents": True,
            },
        }
    ]

    response = session.post(
        (
            "https://moodle2.ntust.edu.tw/lib/ajax/service.php"
            f"?sesskey={sesskey_match.group(1)}&info=core_calendar_get_action_events_by_timesort"
        ),
        json=payload,
        timeout=DEFAULT_TIMEOUT,
        allow_redirects=True,
        verify=verify_ssl,
    )
    response.raise_for_status()

    data = response.json()
    if not data or data[0].get("error"):
        raise RuntimeError(f"Moodle 時間軸 API 回傳錯誤：{data}")

    items: list[dict[str, Any]] = []
    for event in data[0]["data"]["events"]:
        action = event.get("action") or {}
        course = event.get("course") or {}
        items.append(
            {
                "due_at": datetime.fromtimestamp(event["timesort"], TAIPEI).isoformat(),
                "title": normalize(str(event.get("activityname") or event.get("name") or "")),
                "summary": normalize(str(event.get("activitystr") or "")),
                "event_url": normalize(str(event.get("viewurl") or "")),
                "action_label": normalize(str(action.get("name") or "")),
                "action_url": normalize(str(action.get("url") or "")),
                "course_name": normalize(str(course.get("fullnamedisplay") or course.get("fullname") or "")),
                "module_name": normalize(str(event.get("modulename") or "")),
                "event_type": normalize(str(event.get("eventtype") or "")),
                "timesort": event.get("timesort"),
                "overdue": bool(event.get("overdue", False)),
            }
        )

    return items


def filter_moodle_assignment_items(items: list[dict[str, Any]]) -> list[dict[str, Any]]:
    actionable_modules = {"assign", "quiz", "workshop", "url", "page"}
    actionable_event_types = {"due", "expectcompletionon"}

    assignments = [
        item
        for item in items
        if (
            item["action_label"] == "繳交作業"
            or "/mod/assign/" in str(item["event_url"])
            or "/mod/assign/" in str(item["action_url"])
            or (
                str(item.get("module_name", "")).lower() in actionable_modules
                and str(item.get("event_type", "")).lower() in actionable_event_types
                and (item["action_url"] or item["event_url"])
            )
        )
    ]
    assignments.sort(key=lambda item: (item["due_at"], item["course_name"], item["title"]))
    return assignments


def fetch_moodle_assignments(username: str, password: str, verify_ssl: bool) -> dict[str, Any]:
    session = requests.Session()
    session.headers.update(
        {
            "User-Agent": (
                "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/122.0.0.0 Safari/537.36"
            ),
            "Accept-Language": "zh-TW,zh;q=0.9,en;q=0.8",
        }
    )

    page_response = login_to_target(session, username, password, MOODLE_DASHBOARD_URL, verify_ssl)
    soup = BeautifulSoup(page_response.text, "html.parser")
    timeline_config = extract_moodle_timeline_config(soup)
    timeline_items = fetch_moodle_timeline_items(session, page_response.text, timeline_config, verify_ssl)
    assignments = filter_moodle_assignment_items(timeline_items)

    return {
        "source_url": page_response.url,
        "page_title": normalize(soup.title.get_text(" ", strip=True) if soup.title else ""),
        "timeline_filter": str(timeline_config["filter_label"]),
        "items": assignments,
    }
