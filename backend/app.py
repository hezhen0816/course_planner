from __future__ import annotations

import os
import re
from datetime import datetime
from typing import Any
from urllib.parse import quote, urljoin
from zoneinfo import ZoneInfo

import requests
import urllib3
from bs4 import BeautifulSoup, Tag
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, ConfigDict, Field


TAIPEI = ZoneInfo("Asia/Taipei")
BASE_URL = "https://courseselection.ntust.edu.tw"
ENTRY_URL = f"{BASE_URL}/"
VERIFY_URL = f"{BASE_URL}/First/A06/A06"
COURSE_LIST_URL = f"{BASE_URL}/ChooseList/D01/D01"
EDU_NEED_URL = "https://stu.ntust.edu.tw/stueduneed/Edu_Need.aspx"
MOODLE_DASHBOARD_URL = "https://moodle2.ntust.edu.tw/my/"
DEFAULT_TIMEOUT = 30
DEFAULT_VERIFY_SSL = os.environ.get("NTUST_VERIFY_SSL", "false").lower() in {"true", "1", "yes"}
SUPABASE_URL = os.environ.get("SUPABASE_URL", "").rstrip("/")
SUPABASE_SERVICE_ROLE_KEY = os.environ.get("SUPABASE_SERVICE_ROLE_KEY", "")

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

app = FastAPI(title="Course Compass Sync API", version="0.1.0")


class SyncRequest(BaseModel):
    username: str = Field(min_length=1)
    password: str = Field(min_length=1)
    profile_key: str | None = None
    persist_to_supabase: bool = True
    verify_ssl: bool = DEFAULT_VERIFY_SSL


class HistoryImportRequest(BaseModel):
    username: str = Field(min_length=1)
    password: str = Field(min_length=1)
    profile_key: str | None = None
    persist_to_supabase: bool = True
    verify_ssl: bool = DEFAULT_VERIFY_SSL


class MoodleAssignmentsRequest(BaseModel):
    username: str = Field(min_length=1)
    password: str = Field(min_length=1)
    profile_key: str | None = None
    persist_to_supabase: bool = True
    verify_ssl: bool = DEFAULT_VERIFY_SSL


class CourseRow(BaseModel):
    course_code: str
    course_name: str
    credits: float | str
    required_type: str
    professor: str
    note: str


class ScheduleSlot(BaseModel):
    weekday_key: str
    weekday_label: str
    period: str
    time: str
    course_name: str
    location: str
    raw: str


class ScheduleEntryPayload(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    weekday_key: str
    weekday_label: str
    title: str
    time_range: str
    slot_times: list[str] = []
    room: str
    instructor: str
    accent: str


class SyncResponse(BaseModel):
    profile_key: str
    school_account: str
    student_name: str | None = None
    source_url: str
    page_title: str
    total_credits_text: str
    total_credits: float | None
    synced_at: datetime
    course_count: int
    scheduled_slot_count: int
    schedule_entry_count: int
    persisted_to_supabase: bool
    courses: list[CourseRow]
    slots: list[ScheduleSlot]
    schedule_entries: list[ScheduleEntryPayload]


class HistoryCourseRecord(BaseModel):
    category: str
    course_code: str
    course_name: str
    academic_term: str
    grade: str
    earned_credits: str


class HistoryImportResponse(BaseModel):
    profile_key: str
    school_account: str
    student_name: str | None = None
    student_no: str | None = None
    department: str | None = None
    status: str | None = None
    source_url: str
    page_title: str
    imported_at: datetime
    record_count: int
    persisted_to_supabase: bool
    summary_texts: list[str]
    records: list[HistoryCourseRecord]


class MoodleAssignmentItem(BaseModel):
    due_at: datetime
    title: str
    summary: str
    course_name: str
    action_label: str
    action_url: str
    event_url: str
    overdue: bool


class MoodleAssignmentsResponse(BaseModel):
    profile_key: str
    school_account: str
    source_url: str
    page_title: str
    timeline_filter: str
    synced_at: datetime
    item_count: int
    persisted_to_supabase: bool
    items: list[MoodleAssignmentItem]


def now() -> datetime:
    return datetime.now(TAIPEI)


def normalize(text: str | None) -> str:
    return (text or "").replace("\xa0", " ").replace("\r", "").strip()


def split_lines(text: str | None) -> list[str]:
    return [line.strip() for line in normalize(text).split("\n") if line.strip()]


def first_form(soup: BeautifulSoup) -> Tag:
    form = soup.find("form")
    if not isinstance(form, Tag):
        raise RuntimeError("無法找到表單。")
    return form


def parse_hidden_inputs(form: Tag) -> dict[str, str]:
    values: dict[str, str] = {}
    for input_tag in form.find_all("input"):
        if not isinstance(input_tag, Tag):
            continue
        name = input_tag.get("name")
        if not name:
            continue
        input_type = (input_tag.get("type") or "").lower()
        if input_type in {"hidden", ""}:
            values[name] = input_tag.get("value", "")
    return values


def find_error_text(soup: BeautifulSoup) -> str | None:
    containers = soup.find_all(
        ["div", "span", "p"],
        class_=re.compile(r"error|alert|warning|danger|validation", re.I),
    )
    for container in containers:
        text = normalize(container.get_text(" ", strip=True))
        if text:
            return text

    for node in soup.find_all(string=re.compile("帳號或密碼|incorrect|失敗|錯誤", re.I)):
        text = normalize(str(node))
        if text:
            return text
    return None


def build_login_url(entry_response: requests.Response) -> str:
    if "ssoam" in entry_response.url:
        return entry_response.url

    soup = BeautifulSoup(entry_response.text, "html.parser")
    form = soup.find("form")
    if not isinstance(form, Tag):
        raise RuntimeError("入口頁沒有提供 SSO 登入資訊。")

    action = form.get("action")
    if action:
        return urljoin(entry_response.url, action)

    return_url_input = form.find("input", {"name": "ReturnUrl"})
    if isinstance(return_url_input, Tag):
        return_url = return_url_input.get("value", "")
        if return_url:
            return f"https://ssoam2.ntust.edu.tw/account/login?ReturnUrl={return_url}"

    raise RuntimeError("無法從入口頁推導 SSO 登入網址。")


def submit_hidden_form(
    session: requests.Session,
    page_response: requests.Response,
    verify_ssl: bool,
) -> requests.Response:
    soup = BeautifulSoup(page_response.text, "html.parser")
    form = first_form(soup)
    form_data = parse_hidden_inputs(form)
    action = urljoin(page_response.url, form.get("action", ""))
    response = session.post(
        action,
        data=form_data,
        timeout=DEFAULT_TIMEOUT,
        allow_redirects=True,
        verify=verify_ssl,
    )
    response.raise_for_status()
    return response


def requires_hidden_form_callback(page_response: requests.Response) -> bool:
    if "signin-oidc" in page_response.url:
        return True

    soup = BeautifulSoup(page_response.text, "html.parser")
    form = soup.find("form")
    if not isinstance(form, Tag):
        return False

    action = urljoin(page_response.url, form.get("action", ""))
    return "auth/oidc" in action or "signin-oidc" in action


def login_to_target(
    session: requests.Session,
    username: str,
    password: str,
    target_url: str,
    verify_ssl: bool,
) -> requests.Response:
    entry_response = session.get(
        target_url,
        timeout=DEFAULT_TIMEOUT,
        allow_redirects=True,
        verify=verify_ssl,
    )
    entry_response.raise_for_status()

    if "ssoam" not in entry_response.url:
        return entry_response

    soup = BeautifulSoup(entry_response.text, "html.parser")
    form = first_form(soup)
    login_data = parse_hidden_inputs(form)
    login_data["Username"] = username
    login_data["Password"] = password
    login_data.setdefault("captcha", "")

    submit_url = urljoin(entry_response.url, form.get("action", ""))
    login_response = session.post(
        submit_url,
        data=login_data,
        timeout=DEFAULT_TIMEOUT,
        allow_redirects=True,
        verify=verify_ssl,
    )
    login_response.raise_for_status()

    if requires_hidden_form_callback(login_response):
        login_response = submit_hidden_form(session, login_response, verify_ssl)

    if "login" in login_response.url.lower() and "ssoam" in login_response.url:
        error_text = find_error_text(BeautifulSoup(login_response.text, "html.parser"))
        if error_text:
            raise RuntimeError(f"SSO 登入失敗：{error_text}")
        raise RuntimeError(f"SSO 登入失敗，仍停留在登入頁：{login_response.url}")

    page_response = session.get(
        target_url,
        timeout=DEFAULT_TIMEOUT,
        allow_redirects=True,
        verify=verify_ssl,
    )
    page_response.raise_for_status()

    if requires_hidden_form_callback(page_response):
        page_response = submit_hidden_form(session, page_response, verify_ssl)
        page_response = session.get(
            target_url,
            timeout=DEFAULT_TIMEOUT,
            allow_redirects=True,
            verify=verify_ssl,
        )
        page_response.raise_for_status()

    if "login" in page_response.url.lower() or "ssoam" in page_response.url:
        raise RuntimeError(f"登入後無法進入目標頁面，目前停在 {page_response.url}")

    return page_response


def login(session: requests.Session, username: str, password: str, verify_ssl: bool) -> None:
    entry_response = session.get(
        ENTRY_URL,
        timeout=DEFAULT_TIMEOUT,
        allow_redirects=True,
        verify=verify_ssl,
    )
    entry_response.raise_for_status()

    login_url = build_login_url(entry_response)
    login_page = session.get(
        login_url,
        timeout=DEFAULT_TIMEOUT,
        allow_redirects=True,
        verify=verify_ssl,
    )
    login_page.raise_for_status()

    soup = BeautifulSoup(login_page.text, "html.parser")
    form = first_form(soup)
    login_data = parse_hidden_inputs(form)
    login_data["Username"] = username
    login_data["Password"] = password
    login_data.setdefault("captcha", "")

    submit_url = urljoin(login_page.url, form.get("action", ""))
    login_response = session.post(
        submit_url,
        data=login_data,
        timeout=DEFAULT_TIMEOUT,
        allow_redirects=True,
        verify=verify_ssl,
    )
    login_response.raise_for_status()

    if requires_hidden_form_callback(login_response):
        login_response = submit_hidden_form(session, login_response, verify_ssl)

    if "login" in login_response.url.lower() and "ssoam" in login_response.url:
        error_text = find_error_text(BeautifulSoup(login_response.text, "html.parser"))
        if error_text:
            raise RuntimeError(f"SSO 登入失敗：{error_text}")
        raise RuntimeError(f"SSO 登入失敗，仍停留在登入頁：{login_response.url}")

    verify_response = session.get(
        VERIFY_URL,
        timeout=DEFAULT_TIMEOUT,
        allow_redirects=True,
        verify=verify_ssl,
    )
    verify_response.raise_for_status()

    if requires_hidden_form_callback(verify_response):
        verify_response = submit_hidden_form(session, verify_response, verify_ssl)

    if "login" in verify_response.url.lower() or "ssoam" in verify_response.url:
        raise RuntimeError(f"登入後驗證失敗，目前停在 {verify_response.url}")


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


def extract_history_course_tables(soup: BeautifulSoup) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []

    for title_cell in soup.select("td.TD_title1_C"):
        section_title = normalize(title_cell.get_text(" ", strip=True))
        section_table = title_cell.find_parent("table")
        if not isinstance(section_table, Tag):
            continue

        for table in section_table.find_all("table"):
            tr_rows = table.find_all("tr", recursive=False)
            if not tr_rows:
                tr_rows = table.find_all("tr")
            if not tr_rows:
                continue

            header_cells = [normalize(cell.get_text(" ", strip=True)) for cell in tr_rows[0].find_all(["td", "th"])]
            if header_cells[:5] != ["課程代碼", "課程名稱", "學年期", "成績", "實得學分"]:
                continue

            for tr in tr_rows[1:]:
                cells = [normalize(cell.get_text(" ", strip=True)) for cell in tr.find_all("td")]
                if len(cells) < 5 or not cells[0]:
                    continue
                rows.append(
                    {
                        "category": section_title,
                        "course_code": cells[0],
                        "course_name": cells[1],
                        "academic_term": cells[2],
                        "grade": cells[3],
                        "earned_credits": cells[4],
                    }
                )

    return rows


def extract_history_summary_texts(soup: BeautifulSoup) -> list[str]:
    summaries: list[str] = []
    for cell in soup.find_all("td", align="right"):
        text = normalize(cell.get_text(" ", strip=True))
        if "學分" in text:
            summaries.append(text)
    return summaries


def fetch_history_records(username: str, password: str, verify_ssl: bool) -> dict[str, Any]:
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

    page_response = login_to_target(session, username, password, EDU_NEED_URL, verify_ssl)
    soup = BeautifulSoup(page_response.text, "html.parser")

    student_name = normalize(
        soup.select_one("#ContentPlaceHolder1_Lal_StudentName").get_text(" ", strip=True)
        if soup.select_one("#ContentPlaceHolder1_Lal_StudentName")
        else ""
    )
    student_no = normalize(
        soup.select_one("#ContentPlaceHolder1_Lal_StudentNo").get_text(" ", strip=True)
        if soup.select_one("#ContentPlaceHolder1_Lal_StudentNo")
        else ""
    )
    department = normalize(
        soup.select_one("#ContentPlaceHolder1_Lal_Subject").get_text(" ", strip=True)
        if soup.select_one("#ContentPlaceHolder1_Lal_Subject")
        else ""
    )
    status = normalize(
        soup.select_one("#ContentPlaceHolder1_Lal_Nowcondition").get_text(" ", strip=True)
        if soup.select_one("#ContentPlaceHolder1_Lal_Nowcondition")
        else ""
    )

    records = extract_history_course_tables(soup)
    summary_texts = extract_history_summary_texts(soup)

    return {
        "source_url": page_response.url,
        "page_title": normalize(soup.title.get_text(" ", strip=True) if soup.title else ""),
        "student_name": student_name or None,
        "student_no": student_no or None,
        "department": department or None,
        "status": status or None,
        "summary_texts": summary_texts,
        "records": records,
    }


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
        "limit_num": max(parsed_limit_num, 100),
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


def persist_snapshot(profile_key: str, school_account: str, payload: dict[str, Any]) -> bool:
    if not SUPABASE_URL or not SUPABASE_SERVICE_ROLE_KEY:
        return False

    endpoint = f"{SUPABASE_URL}/rest/v1/schedule_sync_snapshots"
    headers = {
        "apikey": SUPABASE_SERVICE_ROLE_KEY,
        "Authorization": f"Bearer {SUPABASE_SERVICE_ROLE_KEY}",
        "Content-Type": "application/json",
        "Prefer": "resolution=merge-duplicates,return=minimal",
    }
    body = {
        "profile_key": profile_key,
        "school_account": school_account,
        "student_name": payload.get("student_name"),
        "payload": payload,
        "synced_at": payload["synced_at"],
    }
    response = requests.post(endpoint, headers=headers, json=body, timeout=DEFAULT_TIMEOUT)
    if response.status_code >= 300:
        raise RuntimeError(f"Supabase 寫入失敗：{response.status_code} {response.text}")
    return True


def load_snapshot(profile_key: str) -> dict[str, Any] | None:
    if not SUPABASE_URL or not SUPABASE_SERVICE_ROLE_KEY:
        return None

    endpoint = (
        f"{SUPABASE_URL}/rest/v1/schedule_sync_snapshots"
        f"?profile_key=eq.{quote(profile_key, safe='')}&select=payload"
    )
    headers = {
        "apikey": SUPABASE_SERVICE_ROLE_KEY,
        "Authorization": f"Bearer {SUPABASE_SERVICE_ROLE_KEY}",
    }
    response = requests.get(endpoint, headers=headers, timeout=DEFAULT_TIMEOUT)
    if response.status_code >= 300:
        raise RuntimeError(f"Supabase 讀取失敗：{response.status_code} {response.text}")
    rows = response.json()
    if not rows:
        return None
    return rows[0]["payload"]


def ensure_schedule_entry_slot_times(payload: dict[str, Any]) -> dict[str, Any]:
    schedule_entries = payload.get("schedule_entries")
    if not isinstance(schedule_entries, list) or not schedule_entries:
        return payload

    if all(isinstance(entry, dict) and entry.get("slot_times") for entry in schedule_entries):
        return payload

    courses = payload.get("courses")
    slots = payload.get("slots")
    if not isinstance(courses, list) or not isinstance(slots, list):
        return payload

    rebuilt_entries = group_schedule_entries(courses, slots)
    return {
        **payload,
        "schedule_entries": rebuilt_entries,
        "schedule_entry_count": len(rebuilt_entries),
    }


def persist_history_snapshot(profile_key: str, school_account: str, payload: dict[str, Any]) -> bool:
    if not SUPABASE_URL or not SUPABASE_SERVICE_ROLE_KEY:
        return False

    endpoint = f"{SUPABASE_URL}/rest/v1/history_import_snapshots"
    headers = {
        "apikey": SUPABASE_SERVICE_ROLE_KEY,
        "Authorization": f"Bearer {SUPABASE_SERVICE_ROLE_KEY}",
        "Content-Type": "application/json",
        "Prefer": "resolution=merge-duplicates,return=minimal",
    }
    body = {
        "profile_key": profile_key,
        "school_account": school_account,
        "student_name": payload.get("student_name"),
        "payload": payload,
        "imported_at": payload["imported_at"],
    }
    response = requests.post(endpoint, headers=headers, json=body, timeout=DEFAULT_TIMEOUT)
    if response.status_code >= 300:
        raise RuntimeError(f"Supabase 歷史修課寫入失敗：{response.status_code} {response.text}")
    return True


def load_history_snapshot(profile_key: str) -> dict[str, Any] | None:
    if not SUPABASE_URL or not SUPABASE_SERVICE_ROLE_KEY:
        return None

    endpoint = (
        f"{SUPABASE_URL}/rest/v1/history_import_snapshots"
        f"?profile_key=eq.{quote(profile_key, safe='')}&select=payload"
    )
    headers = {
        "apikey": SUPABASE_SERVICE_ROLE_KEY,
        "Authorization": f"Bearer {SUPABASE_SERVICE_ROLE_KEY}",
    }
    response = requests.get(endpoint, headers=headers, timeout=DEFAULT_TIMEOUT)
    if response.status_code >= 300:
        raise RuntimeError(f"Supabase 歷史修課讀取失敗：{response.status_code} {response.text}")
    rows = response.json()
    if not rows:
        return None
    return rows[0]["payload"]


def persist_moodle_assignments_snapshot(profile_key: str, school_account: str, payload: dict[str, Any]) -> bool:
    if not SUPABASE_URL or not SUPABASE_SERVICE_ROLE_KEY:
        return False

    endpoint = f"{SUPABASE_URL}/rest/v1/moodle_assignment_snapshots"
    headers = {
        "apikey": SUPABASE_SERVICE_ROLE_KEY,
        "Authorization": f"Bearer {SUPABASE_SERVICE_ROLE_KEY}",
        "Content-Type": "application/json",
        "Prefer": "resolution=merge-duplicates,return=minimal",
    }
    body = {
        "profile_key": profile_key,
        "school_account": school_account,
        "payload": payload,
        "synced_at": payload["synced_at"],
    }
    response = requests.post(endpoint, headers=headers, json=body, timeout=DEFAULT_TIMEOUT)
    if response.status_code >= 300:
        raise RuntimeError(f"Supabase 待繳事項寫入失敗：{response.status_code} {response.text}")
    return True


def load_moodle_assignments_snapshot(profile_key: str) -> dict[str, Any] | None:
    if not SUPABASE_URL or not SUPABASE_SERVICE_ROLE_KEY:
        return None

    endpoint = (
        f"{SUPABASE_URL}/rest/v1/moodle_assignment_snapshots"
        f"?profile_key=eq.{quote(profile_key, safe='')}&select=payload"
    )
    headers = {
        "apikey": SUPABASE_SERVICE_ROLE_KEY,
        "Authorization": f"Bearer {SUPABASE_SERVICE_ROLE_KEY}",
    }
    response = requests.get(endpoint, headers=headers, timeout=DEFAULT_TIMEOUT)
    if response.status_code >= 300:
        raise RuntimeError(f"Supabase 待繳事項讀取失敗：{response.status_code} {response.text}")
    rows = response.json()
    if not rows:
        return None
    return rows[0]["payload"]


@app.get("/health")
def healthcheck() -> dict[str, Any]:
    return {
        "ok": True,
        "supabase_configured": bool(SUPABASE_URL and SUPABASE_SERVICE_ROLE_KEY),
        "timestamp": now().isoformat(),
    }


@app.post("/api/schedule/sync", response_model=SyncResponse)
def sync_schedule(request: SyncRequest) -> SyncResponse:
    try:
        payload = fetch_schedule(request.username, request.password, request.verify_ssl)
        synced_at = now().isoformat()
        response_payload = {
            **payload,
            "profile_key": request.profile_key or request.username,
            "school_account": request.username,
            "student_name": None,
            "synced_at": synced_at,
            "course_count": len(payload["courses"]),
            "scheduled_slot_count": len(payload["slots"]),
            "schedule_entry_count": len(payload["schedule_entries"]),
            "persisted_to_supabase": False,
        }
        if request.persist_to_supabase:
            response_payload["persisted_to_supabase"] = persist_snapshot(
                profile_key=response_payload["profile_key"],
                school_account=request.username,
                payload=response_payload,
            )
        return SyncResponse.model_validate(response_payload)
    except requests.RequestException as exc:
        raise HTTPException(status_code=502, detail=f"課表系統請求失敗：{exc}") from exc
    except RuntimeError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.get("/api/schedule/{profile_key}", response_model=SyncResponse)
def get_latest_schedule(profile_key: str) -> SyncResponse:
    try:
        payload = load_snapshot(profile_key)
        if payload is None:
            raise HTTPException(status_code=404, detail="Supabase 找不到此 profile 的課表快照。")
        payload = ensure_schedule_entry_slot_times(payload)
        return SyncResponse.model_validate(payload)
    except HTTPException:
        raise
    except RuntimeError as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@app.post("/api/history/import", response_model=HistoryImportResponse)
def import_history(request: HistoryImportRequest) -> HistoryImportResponse:
    try:
        payload = fetch_history_records(request.username, request.password, request.verify_ssl)
        response_payload = {
            **payload,
            "profile_key": request.profile_key or request.username,
            "school_account": request.username,
            "imported_at": now().isoformat(),
            "record_count": len(payload["records"]),
            "persisted_to_supabase": False,
        }
        if request.persist_to_supabase:
            response_payload["persisted_to_supabase"] = persist_history_snapshot(
                profile_key=response_payload["profile_key"],
                school_account=request.username,
                payload=response_payload,
            )
        return HistoryImportResponse.model_validate(response_payload)
    except requests.RequestException as exc:
        raise HTTPException(status_code=502, detail=f"歷史修課系統請求失敗：{exc}") from exc
    except RuntimeError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.get("/api/history/{profile_key}", response_model=HistoryImportResponse)
def get_latest_history(profile_key: str) -> HistoryImportResponse:
    try:
        payload = load_history_snapshot(profile_key)
        if payload is None:
            raise HTTPException(status_code=404, detail="Supabase 找不到此 profile 的歷史修課紀錄。")
        return HistoryImportResponse.model_validate(payload)
    except HTTPException:
        raise
    except RuntimeError as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@app.post("/api/moodle/assignments/sync", response_model=MoodleAssignmentsResponse)
def sync_moodle_assignments(request: MoodleAssignmentsRequest) -> MoodleAssignmentsResponse:
    try:
        payload = fetch_moodle_assignments(request.username, request.password, request.verify_ssl)
        response_payload = {
            **payload,
            "profile_key": request.profile_key or request.username,
            "school_account": request.username,
            "synced_at": now().isoformat(),
            "item_count": len(payload["items"]),
            "persisted_to_supabase": False,
        }
        if request.persist_to_supabase:
            response_payload["persisted_to_supabase"] = persist_moodle_assignments_snapshot(
                profile_key=response_payload["profile_key"],
                school_account=request.username,
                payload=response_payload,
            )
        return MoodleAssignmentsResponse.model_validate(response_payload)
    except requests.RequestException as exc:
        raise HTTPException(status_code=502, detail=f"Moodle 待繳事項請求失敗：{exc}") from exc
    except RuntimeError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.get("/api/moodle/assignments/{profile_key}", response_model=MoodleAssignmentsResponse)
def get_latest_moodle_assignments(profile_key: str) -> MoodleAssignmentsResponse:
    try:
        payload = load_moodle_assignments_snapshot(profile_key)
        if payload is None:
            raise HTTPException(status_code=404, detail="Supabase 找不到此 profile 的待繳事項快照。")
        return MoodleAssignmentsResponse.model_validate(payload)
    except HTTPException:
        raise
    except RuntimeError as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc
