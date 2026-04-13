from __future__ import annotations

import re
from typing import Any

import requests
from bs4 import BeautifulSoup, Tag

try:
    from .config import COURSE_LIST_URL, DEFAULT_TIMEOUT
    from .ntust_common import login, normalize, split_lines, submit_hidden_form
    from .time_utils import now
except ImportError:  # pragma: no cover
    from config import COURSE_LIST_URL, DEFAULT_TIMEOUT
    from ntust_common import login, normalize, split_lines, submit_hidden_form
    from time_utils import now

def locate_course_table(print_area: Tag) -> Tag:
    for table in print_area.find_all("table"):
        header_row = table.find("tr")
        header_text = normalize(header_row.get_text(" ", strip=True) if header_row else "")
        if (
            "課碼" in header_text
            and "課程名稱" in header_text
            and "學分數" in header_text
            and "上課教師" in header_text
        ):
            return table
    raise RuntimeError("找不到課程清單表格。")


def locate_schedule_table(print_area: Tag) -> Tag:
    for table in print_area.find_all("table"):
        header_row = table.find("tr")
        header_text = normalize(header_row.get_text(" ", strip=True) if header_row else "")
        if "節次" in header_text and "星期一" in header_text and "星期日" in header_text:
            return table
    raise RuntimeError("找不到課表表格。")


def parse_course_rows(table: Tag) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for tr in table.find_all("tr")[1:]:
        cells = [normalize(td.get_text(" ", strip=True)) for td in tr.find_all("td")]
        if len(cells) < 6 or not cells[0] or not cells[1]:
            continue
        rows.append(
            {
                "course_code": cells[0],
                "course_name": cells[1],
                "credits": float(cells[2]) if re.fullmatch(r"\d+(?:\.\d+)?", cells[2]) else cells[2],
                "required_type": cells[3],
                "professor": cells[4],
                "note": cells[5],
            }
        )
    return rows


def weekday_key_from_label(label: str) -> str:
    mapping = {
        "星期一": "monday",
        "星期二": "tuesday",
        "星期三": "wednesday",
        "星期四": "thursday",
        "星期五": "friday",
        "星期六": "saturday",
        "星期日": "sunday",
    }
    return mapping.get(label, "monday")


def parse_schedule_rows(table: Tag) -> list[dict[str, Any]]:
    tr_rows = table.find_all("tr")
    if len(tr_rows) < 2:
        return []

    header_cells = [normalize(cell.get_text(" ", strip=True)) for cell in tr_rows[0].find_all(["th", "td"])]
    weekdays = header_cells[2:]
    slot_rows: list[dict[str, Any]] = []

    for tr in tr_rows[1:]:
        cells = [split_lines(td.get_text("\n", strip=True)) for td in tr.find_all("td")]
        if len(cells) < 2 + len(weekdays):
            continue

        period = " ".join(cells[0])
        time_text = " ".join(cells[1])
        for index, weekday in enumerate(weekdays):
            lines = cells[index + 2]
            if not lines:
                continue
            slot_rows.append(
                {
                    "weekday_key": weekday_key_from_label(weekday),
                    "weekday_label": weekday,
                    "period": period,
                    "time": time_text,
                    "course_name": " / ".join(lines[:-1]) if len(lines) > 1 else lines[0],
                    "location": lines[-1] if len(lines) > 1 else "",
                    "raw": " | ".join(lines),
                }
            )
    return slot_rows


def parse_course_list(html: str) -> dict[str, Any]:
    soup = BeautifulSoup(html, "html.parser")
    print_area = soup.select_one("#PrintArea")
    if not isinstance(print_area, Tag):
        raise RuntimeError("找不到 #PrintArea。")

    total_credits_text = ""
    for element in print_area.find_all(True):
        text = normalize(element.get_text(" ", strip=True))
        if text.startswith("總學分數:"):
            total_credits_text = text
            break

    course_rows = parse_course_rows(locate_course_table(print_area))
    slot_rows = parse_schedule_rows(locate_schedule_table(print_area))

    return {
        "page_title": normalize(soup.title.get_text(" ", strip=True) if soup.title else ""),
        "total_credits_text": total_credits_text,
        "courses": course_rows,
        "slots": slot_rows,
    }


def group_schedule_entries(courses: list[dict[str, Any]], slots: list[dict[str, Any]]) -> list[dict[str, Any]]:
    course_index = {course["course_name"]: course for course in courses}
    grouped: dict[tuple[str, str], list[dict[str, Any]]] = {}

    for slot in slots:
        grouped.setdefault((slot["weekday_key"], slot["course_name"]), []).append(slot)

    entries: list[dict[str, Any]] = []
    for (weekday_key, course_name), group in grouped.items():
        ordered = sorted(group, key=lambda item: _time_sort_key(item["time"]))
        first_slot = ordered[0]
        last_slot = ordered[-1]
        course = course_index.get(course_name, {})
        start = _normalize_time_segment(first_slot["time"], True)
        end = _normalize_time_segment(last_slot["time"], False)
        entries.append(
            {
                "weekday_key": weekday_key,
                "weekday_label": first_slot["weekday_label"],
                "title": course_name,
                "time_range": f"{start} - {end}",
                "slot_times": [slot["time"] for slot in ordered],
                "room": first_slot["location"],
                "instructor": str(course.get("professor", "")),
                "accent": accent_from_required_type(str(course.get("required_type", "")), course_name),
            }
        )

    entries.sort(key=lambda item: (weekday_order(item["weekday_key"]), _time_sort_key(item["time_range"])))
    return entries


def _normalize_time_segment(value: str, is_start: bool) -> str:
    pieces = re.split(r"[～-]", value)
    raw = pieces[0] if is_start else pieces[-1]
    raw = normalize(raw).replace(" ", "")
    match = re.fullmatch(r"(\d{1,2}):(\d{2})", raw)
    if not match:
        return raw
    hour = int(match.group(1))
    minute = int(match.group(2))
    return f"{hour:02d}:{minute:02d}"


def _time_sort_key(value: str) -> tuple[int, int]:
    start = _normalize_time_segment(value, True)
    match = re.fullmatch(r"(\d{2}):(\d{2})", start)
    if not match:
        return (99, 99)
    return (int(match.group(1)), int(match.group(2)))


def weekday_order(weekday_key: str) -> int:
    ordered = ["monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday"]
    return ordered.index(weekday_key) if weekday_key in ordered else 99


def accent_from_required_type(required_type: str, course_name: str) -> str:
    if "體育" in course_name:
        return "pe"
    if "英文" in course_name or "英語" in course_name:
        return "english"
    if "通識" in course_name or course_name.startswith("GE"):
        return "genEd"
    if required_type == "必修":
        return "compulsory"
    if required_type == "選修":
        return "elective"
    return "unclassified"


def fetch_schedule(username: str, password: str, verify_ssl: bool) -> dict[str, Any]:
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

    login(session, username, password, verify_ssl)

    page_response = session.get(
        COURSE_LIST_URL,
        timeout=DEFAULT_TIMEOUT,
        allow_redirects=True,
        verify=verify_ssl,
    )
    page_response.raise_for_status()

    if "signin-oidc" in page_response.url:
        page_response = submit_hidden_form(session, page_response, verify_ssl)
        page_response = session.get(
            COURSE_LIST_URL,
            timeout=DEFAULT_TIMEOUT,
            allow_redirects=True,
            verify=verify_ssl,
        )
        page_response.raise_for_status()

    if "login" in page_response.url.lower() or "ssoam" in page_response.url:
        raise RuntimeError(f"無法進入選課清單頁面，目前停在 {page_response.url}")

    extracted = parse_course_list(page_response.text)
    entries = group_schedule_entries(extracted["courses"], extracted["slots"])
    total_credits_match = re.search(r"(\d+(?:\.\d+)?)", extracted["total_credits_text"])
    total_credits = float(total_credits_match.group(1)) if total_credits_match else None

    return {
        "source_url": page_response.url,
        "page_title": extracted["page_title"],
        "total_credits_text": extracted["total_credits_text"],
        "total_credits": total_credits,
        "courses": extracted["courses"],
        "slots": extracted["slots"],
        "schedule_entries": entries,
    }
