from __future__ import annotations

import re
import threading
import time
from collections import deque
from typing import Any

import requests
from bs4 import BeautifulSoup, Tag
from requests.cookies import create_cookie

try:
    from .config import (
        COURSE_LIST_URL,
        DEFAULT_TIMEOUT,
        INITIAL_SELECTION_CHOOSE_COURSE_LIST_URL,
        INITIAL_SELECTION_EXTRA_JOIN_URL,
        INITIAL_SELECTION_JOIN_URL,
        INITIAL_SELECTION_REMOVE_URL,
        INITIAL_SELECTION_SAVE_INDEX_URL,
        INITIAL_SELECTION_URL,
    )
    from .time_utils import now
    from .ntust_common import login, normalize, requires_hidden_form_callback, split_lines, submit_hidden_form
    from .schedule import find_latest_course_list_url, parse_course_list
    from .tr_rooms import fetch_current_query_semester, fetch_query_courses_filtered
except ImportError:  # pragma: no cover
    from config import (
        COURSE_LIST_URL,
        DEFAULT_TIMEOUT,
        INITIAL_SELECTION_CHOOSE_COURSE_LIST_URL,
        INITIAL_SELECTION_EXTRA_JOIN_URL,
        INITIAL_SELECTION_JOIN_URL,
        INITIAL_SELECTION_REMOVE_URL,
        INITIAL_SELECTION_SAVE_INDEX_URL,
        INITIAL_SELECTION_URL,
    )
    from ntust_common import login, normalize, requires_hidden_form_callback, split_lines, submit_hidden_form
    from schedule import find_latest_course_list_url, parse_course_list
    from tr_rooms import fetch_current_query_semester, fetch_query_courses_filtered
    from time_utils import now


MIN_LOGIN_INTERVAL_SECONDS = 10
MAX_LOGINS_PER_MINUTE = 5
MAX_CLIENT_IDLE_SECONDS = 30 * 60
OFFICIAL_SCHEDULE_HEADERS = ["節次", "時間", "星期一", "星期二", "星期三", "星期四", "星期五", "星期六", "星期日"]
OFFICIAL_SCHEDULE_PERIODS = [
    ("1", "08:10～09:00"),
    ("2", "9:10～10:00"),
    ("3", "10:20～11:10"),
    ("4", "11:20～12:10"),
    ("5", "12:20～13:10"),
    ("6", "13:20～14:10"),
    ("7", "14:20～15:10"),
    ("8", "15:30～16:20"),
    ("9", "16:30～17:20"),
    ("10", "17:30～18:20"),
    ("A", "18:25～19:15"),
    ("B", "19:20～20:10"),
    ("C", "20:15～21:05"),
    ("D", "21:10～22:00"),
]

_clients: dict[str, "OfficialSelectionClient"] = {}
_clients_lock = threading.Lock()


def get_official_selection_client(profile_key: str) -> "OfficialSelectionClient":
    cleanup_official_selection_clients()
    with _clients_lock:
        client = _clients.get(profile_key)
        if client is None:
            client = OfficialSelectionClient()
            _clients[profile_key] = client
        return client


def cleanup_official_selection_clients() -> None:
    cutoff = time.time() - MAX_CLIENT_IDLE_SECONDS
    with _clients_lock:
        for key, client in list(_clients.items()):
            if client.last_used_at < cutoff:
                del _clients[key]


class OfficialSelectionClient:
    def __init__(self) -> None:
        self.session = requests.Session()
        self.session.headers.update(
            {
                "User-Agent": (
                    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                    "AppleWebKit/537.36 (KHTML, like Gecko) "
                    "Chrome/122.0.0.0 Safari/537.36"
                ),
                "Accept-Language": "zh-TW,zh;q=0.9,en;q=0.8",
            }
        )
        self.is_logged_in = False
        self.last_used_at = time.time()
        self.last_login_at: float | None = None
        self.login_times: deque[float] = deque()
        self.lock = threading.Lock()

    def fetch_a02_workspace(self, username: str, password: str, verify_ssl: bool) -> dict[str, Any]:
        with self.lock:
            self.last_used_at = time.time()
            page_response = self.ensure_session(username, password, verify_ssl)
            if page_response.url.rstrip("/") != INITIAL_SELECTION_URL.rstrip("/"):
                page_response = self._get_workspace_page(verify_ssl)
            return self._workspace_payload(page_response, verify_ssl)

    def fetch_current_a02_workspace(self, verify_ssl: bool) -> dict[str, Any]:
        with self.lock:
            self.last_used_at = time.time()
            return self._workspace_payload(self._get_workspace_page(verify_ssl), verify_ssl)

    def export_session_state(self) -> dict[str, Any]:
        cookies: list[dict[str, Any]] = []
        for cookie in self.session.cookies:
            cookies.append(
                {
                    "name": cookie.name,
                    "value": cookie.value,
                    "domain": cookie.domain,
                    "path": cookie.path,
                    "expires": cookie.expires,
                    "secure": cookie.secure,
                    "rest": dict(getattr(cookie, "_rest", {}) or {}),
                }
            )
        return {
            "cookies": cookies,
            "is_logged_in": self.is_logged_in,
            "saved_at": now().isoformat(),
        }

    def restore_session_state(self, session_state: dict[str, Any]) -> bool:
        cookies = session_state.get("cookies")
        if not isinstance(cookies, list) or not cookies:
            return False

        self.session.cookies.clear()
        restored = 0
        for raw_cookie in cookies:
            if not isinstance(raw_cookie, dict):
                continue
            name = str(raw_cookie.get("name") or "")
            value = str(raw_cookie.get("value") or "")
            if not name:
                continue
            expires = raw_cookie.get("expires")
            cookie = create_cookie(
                name=name,
                value=value,
                domain=str(raw_cookie.get("domain") or ""),
                path=str(raw_cookie.get("path") or "/"),
                secure=bool(raw_cookie.get("secure")),
                expires=int(expires) if isinstance(expires, (int, float)) else None,
                rest=raw_cookie.get("rest") if isinstance(raw_cookie.get("rest"), dict) else None,
            )
            self.session.cookies.set_cookie(cookie)
            restored += 1

        self.is_logged_in = bool(restored)
        self.last_used_at = time.time()
        return bool(restored)

    def join_course(self, course_no: str, verify_ssl: bool) -> dict[str, Any]:
        return self._submit_course_action(
            course_no=course_no,
            endpoint=INITIAL_SELECTION_JOIN_URL,
            action_type=1,
            verify_ssl=verify_ssl,
        )

    def add_course_to_waitlist(self, course_no: str, verify_ssl: bool) -> dict[str, Any]:
        return self._submit_course_action(
            course_no=course_no,
            endpoint=INITIAL_SELECTION_EXTRA_JOIN_URL,
            action_type=3,
            verify_ssl=verify_ssl,
        )

    def remove_course(self, course_no: str, verify_ssl: bool) -> dict[str, Any]:
        return self._submit_course_action(
            course_no=course_no,
            endpoint=INITIAL_SELECTION_REMOVE_URL,
            action_type=2,
            verify_ssl=verify_ssl,
        )

    def reorder_registered_courses(self, ordered_course_nos: list[str], verify_ssl: bool) -> dict[str, Any]:
        normalized_course_nos = [
            course_no.strip().upper()
            for course_no in ordered_course_nos
            if course_no.strip()
        ]
        if not normalized_course_nos:
            raise RuntimeError("缺少官方志願序資料，無法儲存。")
        if len(normalized_course_nos) != len(set(normalized_course_nos)):
            raise RuntimeError("官方志願序包含重複課碼，請重新同步後再試。")

        with self.lock:
            self.last_used_at = time.time()
            page_response = self._get_workspace_page(verify_ssl)
            payload = parse_a02_workspace(page_response.text)
            registered_courses = payload["registered_courses"]
            current_by_no = {
                str(course["course_no"]).strip().upper(): course
                for course in registered_courses
            }
            if set(current_by_no) != set(normalized_course_nos):
                raise RuntimeError("官方志願清單已變更，請重新同步後再調整志願序。")

            rows = [["志願序", "課碼", "課程名稱", "取消加入"]]
            for index, course_no in enumerate(normalized_course_nos, start=1):
                course = current_by_no[course_no]
                rows.append([str(index), course_no, str(course.get("course_name") or ""), "取消加入"])

            response = self.session.post(
                INITIAL_SELECTION_SAVE_INDEX_URL,
                data=_arraydata_form_rows(rows),
                headers={
                    "Content-Type": "application/x-www-form-urlencoded",
                    "Referer": INITIAL_SELECTION_URL,
                    "X-Requested-With": "XMLHttpRequest",
                },
                timeout=DEFAULT_TIMEOUT,
                allow_redirects=True,
                verify=verify_ssl,
            )
            response.raise_for_status()
            response = self._complete_callback_if_needed(response, verify_ssl)
            if _is_auth_response(response):
                self.is_logged_in = False
                raise RuntimeError("Session 已失效，請重新同步官方初選資料後再送出。")
            workspace_response = self._get_workspace_page(verify_ssl)
            action_notices = _merge_unique_texts(
                _parse_action_response_notices(response.text),
                _parse_action_response_notices(workspace_response.text),
            )
            payload = self._workspace_payload(workspace_response, verify_ssl, refresh_choose_course_list=False)
            if action_notices:
                payload["notices"] = _merge_unique_texts(action_notices, payload.get("notices", []))
            return payload

    def ensure_session(self, username: str, password: str, verify_ssl: bool) -> requests.Response:
        if self._check_session_quick(verify_ssl):
            return self._get_workspace_page(verify_ssl)

        self._check_login_rate_limit()
        login(self.session, username, password, verify_ssl)
        self.is_logged_in = True
        self.last_login_at = time.time()
        self.login_times.append(self.last_login_at)
        return self._get_workspace_page(verify_ssl)

    def keep_alive(self, verify_ssl: bool) -> bool:
        try:
            response = self.session.get(
                INITIAL_SELECTION_URL,
                timeout=5,
                allow_redirects=True,
                verify=verify_ssl,
                stream=True,
            )
            response.close()
            self.is_logged_in = not _is_auth_response(response)
            self.last_used_at = time.time()
            return self.is_logged_in
        except requests.RequestException:
            self.is_logged_in = False
            return False

    def _get_workspace_page(self, verify_ssl: bool) -> requests.Response:
        response = self.session.get(
            INITIAL_SELECTION_URL,
            timeout=DEFAULT_TIMEOUT,
            allow_redirects=True,
            verify=verify_ssl,
        )
        response.raise_for_status()
        response = self._complete_callback_if_needed(response, verify_ssl)
        if _is_auth_response(response):
            self.is_logged_in = False
            raise RuntimeError("Session 已失效，請重新登入官方選課系統。")
        self.is_logged_in = True
        return response

    def _submit_course_action(
        self,
        course_no: str,
        endpoint: str,
        action_type: int,
        verify_ssl: bool,
    ) -> dict[str, Any]:
        normalized_course_no = course_no.strip().upper()
        if not normalized_course_no:
            raise RuntimeError("缺少課碼，無法送出官方選課請求。")
        with self.lock:
            self.last_used_at = time.time()
            self._get_workspace_page(verify_ssl)
            response = self.session.post(
                endpoint,
                data={"CourseNo": normalized_course_no, "type": action_type},
                headers={
                    "Content-Type": "application/x-www-form-urlencoded",
                    "Referer": INITIAL_SELECTION_URL,
                    "X-Requested-With": "XMLHttpRequest",
                },
                timeout=DEFAULT_TIMEOUT,
                allow_redirects=True,
                verify=verify_ssl,
            )
            response.raise_for_status()
            response = self._complete_callback_if_needed(response, verify_ssl)
            if _is_auth_response(response):
                self.is_logged_in = False
                raise RuntimeError("Session 已失效，請重新同步官方初選資料後再送出。")
            workspace_response = self._get_workspace_page(verify_ssl)
            action_notices = _merge_unique_texts(
                _parse_action_response_notices(response.text),
                _parse_action_response_notices(workspace_response.text),
            )
            payload = self._workspace_payload(workspace_response, verify_ssl, refresh_choose_course_list=False)
            if action_notices:
                payload["notices"] = _merge_unique_texts(action_notices, payload.get("notices", []))
            return payload

    def _check_session_quick(self, verify_ssl: bool) -> bool:
        try:
            response = self.session.head(
                INITIAL_SELECTION_URL,
                timeout=3,
                allow_redirects=True,
                verify=verify_ssl,
            )
            if response.status_code == 405:
                return self.keep_alive(verify_ssl)
            self.is_logged_in = not _is_auth_response(response)
            return self.is_logged_in
        except requests.RequestException:
            self.is_logged_in = False
            return False

    def _complete_callback_if_needed(self, response: requests.Response, verify_ssl: bool) -> requests.Response:
        if requires_hidden_form_callback(response):
            response = submit_hidden_form(self.session, response, verify_ssl)
            response = self.session.get(
                INITIAL_SELECTION_URL,
                timeout=DEFAULT_TIMEOUT,
                allow_redirects=True,
                verify=verify_ssl,
            )
            response.raise_for_status()
        return response

    def _check_login_rate_limit(self) -> None:
        current_time = time.time()
        while self.login_times and current_time - self.login_times[0] > 60:
            self.login_times.popleft()
        if self.last_login_at is not None and current_time - self.last_login_at < MIN_LOGIN_INTERVAL_SECONDS:
            wait_seconds = int(MIN_LOGIN_INTERVAL_SECONDS - (current_time - self.last_login_at)) + 1
            raise RuntimeError(f"登入太頻繁，請 {wait_seconds} 秒後再試。")
        if len(self.login_times) >= MAX_LOGINS_PER_MINUTE:
            raise RuntimeError("登入太頻繁，請稍後再試。")

    def _workspace_payload(
        self,
        page_response: requests.Response,
        verify_ssl: bool,
        *,
        refresh_choose_course_list: bool = True,
    ) -> dict[str, Any]:
        payload = parse_a02_workspace(page_response.text)
        if refresh_choose_course_list:
            refreshed_response, refresh_notices = self._refresh_choose_course_list(verify_ssl)
            if refreshed_response is not None:
                page_response = refreshed_response
                payload = parse_a02_workspace(page_response.text)
            if refresh_notices:
                payload["notices"] = _merge_unique_texts(payload["notices"], refresh_notices)

        _enrich_registered_courses_from_query_system(payload["registered_courses"], verify_ssl)
        _enrich_registered_courses_from_query_system(payload["required_preset_courses"], verify_ssl)
        course_list_rows = self._fetch_course_list_schedule_rows(verify_ssl)
        has_workspace_schedule = _schedule_rows_have_weekday_data(payload["schedule_rows"])
        if course_list_rows and not has_workspace_schedule:
            payload["schedule_rows"] = course_list_rows
            payload["notices"].append("官方功課表由正式課程清單補齊。")
        elif course_list_rows and course_list_rows != payload["schedule_rows"]:
            payload["schedule_rows"] = course_list_rows
            payload["notices"].append("官方功課表由正式課程清單校正。")
        if payload["selection_list_rows"] and not _schedule_rows_have_weekday_data(payload["schedule_rows"]):
            payload["notices"].append("官方選課清單已取得，但功課表資料仍為空或未取得。")
        return {
            **payload,
            "source_url": page_response.url,
            "synced_at": now().isoformat(),
            "session_valid": True,
        }

    def _fetch_course_list_schedule_rows(self, verify_ssl: bool) -> list[dict[str, str]]:
        try:
            response = self.session.get(
                COURSE_LIST_URL,
                timeout=DEFAULT_TIMEOUT,
                allow_redirects=True,
                verify=verify_ssl,
            )
            response.raise_for_status()
            if "signin-oidc" in response.url:
                submit_hidden_form(self.session, response, verify_ssl)
                response = self.session.get(
                    COURSE_LIST_URL,
                    timeout=DEFAULT_TIMEOUT,
                    allow_redirects=True,
                    verify=verify_ssl,
                )
                response.raise_for_status()
            if _is_auth_response(response):
                return []

            latest_course_list_url = find_latest_course_list_url(response.text, response.url, COURSE_LIST_URL)
            if latest_course_list_url != response.url.split("#", 1)[0]:
                response = self.session.get(
                    latest_course_list_url,
                    timeout=DEFAULT_TIMEOUT,
                    allow_redirects=True,
                    verify=verify_ssl,
                )
                response.raise_for_status()
                if "signin-oidc" in response.url:
                    submit_hidden_form(self.session, response, verify_ssl)
                    response = self.session.get(
                        latest_course_list_url,
                        timeout=DEFAULT_TIMEOUT,
                        allow_redirects=True,
                        verify=verify_ssl,
                    )
                    response.raise_for_status()
                if _is_auth_response(response):
                    return []

            extracted = parse_course_list(response.text)
            return _schedule_rows_from_slots(extracted["slots"])
        except (RuntimeError, requests.RequestException):
            return []

    def _refresh_choose_course_list(self, verify_ssl: bool) -> tuple[requests.Response | None, list[str]]:
        try:
            response = self.session.post(
                INITIAL_SELECTION_CHOOSE_COURSE_LIST_URL,
                data={"type": 1},
                headers={
                    "Content-Type": "application/x-www-form-urlencoded",
                    "Referer": INITIAL_SELECTION_URL,
                    "X-Requested-With": "XMLHttpRequest",
                },
                timeout=DEFAULT_TIMEOUT,
                allow_redirects=True,
                verify=verify_ssl,
            )
            response.raise_for_status()
            response = self._complete_callback_if_needed(response, verify_ssl)
            if _is_auth_response(response):
                self.is_logged_in = False
                raise RuntimeError("Session 已失效，請重新登入官方選課系統。")
            notices = _parse_action_response_notices(response.text)
            return self._get_workspace_page(verify_ssl), notices
        except requests.RequestException:
            return None, ["官方選課清單刷新失敗，保留 A02 主頁現有資料。"]


def parse_a02_workspace(html: str) -> dict[str, Any]:
    soup = BeautifulSoup(html, "html.parser")
    available = _parse_available_courses(soup)
    registered = _parse_registered_courses(soup)
    schedule_rows = _parse_schedule_table_rows(soup.select_one("#loginModal table"))
    selection_list_rows = _parse_generic_table_rows(soup.select_one("#loginModal2"))
    required_preset_table = soup.select_one("#DetermineTable") or _find_table_containing(soup, ["課碼", "課程名稱", "退選"])
    required_preset_rows = _parse_generic_table_rows(required_preset_table)
    required_preset_courses = _parse_required_preset_courses(required_preset_rows)
    registered = _merge_registered_course_details(registered, selection_list_rows)

    return {
        "page_title": normalize(soup.title.get_text(" ", strip=True) if soup.title else ""),
        "available_count": len(available),
        "registered_count": len(registered),
        "available_courses": available,
        "registered_courses": registered,
        "schedule_rows": schedule_rows,
        "selection_list_rows": selection_list_rows,
        "required_preset_rows": required_preset_rows,
        "required_preset_courses": required_preset_courses,
        "notices": _parse_notice_texts(soup),
    }


def _schedule_rows_have_weekday_data(rows: list[dict[str, str]]) -> bool:
    weekdays = OFFICIAL_SCHEDULE_HEADERS[2:]
    return any(any(row.get(weekday) for weekday in weekdays) for row in rows)


def _schedule_rows_from_slots(slots: list[dict[str, Any]]) -> list[dict[str, str]]:
    rows = [
        {header: "" for header in OFFICIAL_SCHEDULE_HEADERS}
        for _period, _time in OFFICIAL_SCHEDULE_PERIODS
    ]
    period_index = {period: index for index, (period, _time) in enumerate(OFFICIAL_SCHEDULE_PERIODS)}
    for index, (period, time_text) in enumerate(OFFICIAL_SCHEDULE_PERIODS):
        rows[index]["節次"] = period
        rows[index]["時間"] = time_text

    for slot in slots:
        period = str(slot.get("period") or "").strip()
        weekday = str(slot.get("weekday_label") or "").strip()
        course_name = str(slot.get("course_name") or "").strip()
        if period not in period_index or weekday not in OFFICIAL_SCHEDULE_HEADERS or not course_name:
            continue
        row = rows[period_index[period]]
        row[weekday] = "、".join([value for value in [row[weekday], course_name] if value])

    return rows


def _arraydata_form_rows(rows: list[list[str]]) -> list[tuple[str, str]]:
    fields: list[tuple[str, str]] = []
    for row_index, row in enumerate(rows):
        for column_index, value in enumerate(row):
            fields.append((f"Arraydata[{row_index}][{column_index}]", value))
    return fields


def _parse_available_courses(soup: BeautifulSoup) -> list[dict[str, str]]:
    rows = _extract_div_table_rows(soup.select_one("#draggable"))
    if not rows:
        table = _find_table_containing(soup, ["課碼", "課程名稱", "上課教師", "加入登記"])
        rows = _extract_html_table_rows(table) if table else []
    body_rows = _drop_header_rows(rows, {"課碼", "課程名稱", "上課教師"})

    courses: list[dict[str, str]] = []
    for cells in body_rows:
        if len(cells) < 3:
            continue
        course_no, course_name, teacher = cells[0], cells[1], cells[2]
        if not course_no or course_no == "課碼":
            continue
        courses.append(
            {
                "course_no": course_no,
                "course_name": course_name,
                "teacher": teacher,
            }
        )
    return courses


def _parse_registered_courses(soup: BeautifulSoup) -> list[dict[str, str | int | None]]:
    rows = _extract_html_table_rows(soup.select_one("#cartTable"))
    if not rows:
        rows = _extract_div_table_rows(soup.select_one("#cartTable"))
    body_rows = _drop_header_rows(rows, {"志願序", "課碼", "課程名稱"})

    courses: list[dict[str, str | int | None]] = []
    for cells in body_rows:
        if len(cells) < 3:
            continue
        priority_text, course_no, course_name = cells[0], cells[1], cells[2]
        if not course_no or course_no == "課碼":
            continue
        courses.append(
            {
                "priority": _as_int(priority_text),
                "course_no": course_no,
                "course_name": course_name,
                "raw_priority": priority_text,
                "credits": None,
                "require_option": "",
                "teacher": "",
            }
        )
    return courses


def _merge_registered_course_details(
    registered_courses: list[dict[str, Any]],
    selection_list_rows: list[dict[str, str]],
) -> list[dict[str, Any]]:
    details_by_course_no: dict[str, dict[str, Any]] = {}
    for row in selection_list_rows:
        course_no = _row_value(row, ["課碼", "課程代碼", "課號"]).strip().upper()
        if not course_no:
            continue
        details_by_course_no[course_no] = {
            "course_no": course_no,
            "course_name": _row_value(row, ["課程名稱", "課名"]),
            "credits": _as_float(_row_value(row, ["學分數", "學分"])),
            "require_option": _row_value(row, ["必、選修", "必選修", "必修選修", "必選別"]),
            "teacher": _row_value(row, ["上課教師", "授課教師", "教師"]),
        }

    merged: list[dict[str, Any]] = []
    for course in registered_courses:
        course_no = str(course.get("course_no") or "").strip().upper()
        details = details_by_course_no.get(course_no, {})
        merged.append(
            {
                **course,
                "course_name": details.get("course_name") or course.get("course_name") or "",
                "credits": details.get("credits"),
                "require_option": details.get("require_option") or "",
                "teacher": details.get("teacher") or "",
            }
        )
    return merged


def _parse_required_preset_courses(rows: list[dict[str, str]]) -> list[dict[str, Any]]:
    courses: list[dict[str, Any]] = []
    for row in rows:
        course_no = _row_value(row, ["課碼", "課程代碼", "課號"]).strip().upper()
        if not course_no:
            continue
        courses.append(
            {
                "course_no": course_no,
                "course_name": _row_value(row, ["課程名稱", "課名"]),
                "credits": None,
                "require_option": "",
                "teacher": "",
                "classroom": "",
                "node": "",
                "contents": "",
                "selected_count": None,
                "capacity": None,
            }
        )
    return courses


def _enrich_registered_courses_from_query_system(
    registered_courses: list[dict[str, Any]],
    verify_ssl: bool,
) -> None:
    if not registered_courses:
        return
    try:
        semester = fetch_current_query_semester(verify_ssl)
    except (RuntimeError, requests.RequestException):
        return

    for course in registered_courses:
        course_no = str(course.get("course_no") or "").strip().upper()
        if not course_no:
            continue
        try:
            matches = fetch_query_courses_filtered(
                semester,
                course_no=course_no,
                course_name="",
                verify_ssl=verify_ssl,
            )
        except (RuntimeError, requests.RequestException):
            continue
        match = next(
            (
                item for item in matches
                if str(item.get("CourseNo") or "").strip().upper() == course_no
            ),
            matches[0] if matches else None,
        )
        if not match:
            continue
        course["classroom"] = str(match.get("ClassRoomNo") or "")
        course["node"] = str(match.get("Node") or "")
        course["contents"] = str(match.get("Contents") or "")
        course["selected_count"] = _as_int(match.get("ChooseStudent"))
        course["capacity"] = _as_int(match.get("Restrict2"))
        course["credits"] = _as_float(match.get("CreditPoint")) if _as_float(match.get("CreditPoint")) is not None else course.get("credits")
        course["require_option"] = str(match.get("RequireOption") or course.get("require_option") or "")
        course["teacher"] = str(match.get("CourseTeacher") or course.get("teacher") or "")


def _parse_schedule_table_rows(table: Tag | None) -> list[dict[str, str]]:
    rows = _extract_html_table_rows(table)
    if not rows:
        return []

    header_index = next(
        (index for index, row in enumerate(rows) if {"節次", "星期一"}.issubset(set(row))),
        0,
    )
    headers = rows[header_index]
    result: list[dict[str, str]] = []
    for cells in rows[header_index + 1:]:
        if not any(cells):
            continue
        if len(cells) >= len(OFFICIAL_SCHEDULE_HEADERS):
            result.append({
                OFFICIAL_SCHEDULE_HEADERS[index]: cells[index]
                for index in range(len(OFFICIAL_SCHEDULE_HEADERS))
            })
            continue
        result.append(
            {
                headers[index] if index < len(headers) and headers[index] else f"欄位{index + 1}": value
                for index, value in enumerate(cells)
            }
        )
    return result


def _parse_generic_table_rows(table: Tag | None) -> list[dict[str, str]]:
    rows = _extract_html_table_rows(table)
    if not rows:
        rows = _extract_div_table_rows(table)
    if not rows:
        return []
    headers = rows[0]
    result: list[dict[str, str]] = []
    for cells in rows[1:]:
        if not any(cells):
            continue
        result.append(
            {
                headers[index] if index < len(headers) and headers[index] else f"欄位{index + 1}": value
                for index, value in enumerate(cells)
            }
        )
    return result


def _parse_notice_texts(soup: BeautifulSoup) -> list[str]:
    notices: list[str] = []
    for selector in [".alert", ".panel", ".well", "#message", "#Msg"]:
        for element in soup.select(selector):
            text = normalize(element.get_text(" ", strip=True))
            if text and text not in notices:
                notices.append(text)
    return notices[:10]


def _parse_action_response_notices(html: str) -> list[str]:
    if not html.strip():
        return []

    soup = BeautifulSoup(html, "html.parser")
    notices: list[str] = []
    for script in soup.find_all("script"):
        if not isinstance(script, Tag):
            continue
        script_text = script.get_text("\n", strip=True)
        script_messages = _extract_script_action_messages(script_text)
        for text in script_messages:
            _append_unique_notice(notices, text)
    if notices:
        return notices[:5]

    selectors = [
        "#message",
        "#Msg",
        ".alert-danger",
        ".alert-warning",
        ".alert",
        ".modal-body",
        ".ui-dialog-content",
        ".swal2-html-container",
    ]
    for selector in selectors:
        for element in soup.select(selector):
            text = normalize(element.get_text(" ", strip=True))
            _append_unique_notice(notices, text)

    if notices:
        return notices[:5]

    for text in _extract_known_action_error_patterns(html):
        _append_unique_notice(notices, text)
    if notices:
        return notices[:5]

    body = soup.body or soup
    for text in _extract_action_notice_candidates(body.get_text("\n", strip=True)):
        _append_unique_notice(notices, text)
    for script in soup.find_all("script"):
        if not isinstance(script, Tag):
            continue
        script_text = script.get_text("\n", strip=True)
        for text in _extract_action_notice_candidates(script_text):
            _append_unique_notice(notices, text)
    if notices:
        return notices[:5]

    body_text = normalize(body.get_text(" ", strip=True))
    has_workspace_tables = bool(soup.select("#draggable, #cartTable, #loginModal, table, form"))
    if body_text and not has_workspace_tables and len(body_text) <= 300:
        return [body_text]
    return []


def _extract_known_action_error_patterns(text: str) -> list[str]:
    normalized_text = normalize(text)
    normalized_plain_text = normalize(BeautifulSoup(text, "html.parser").get_text(" ", strip=True))
    patterns = [
        r"本門課設有選課.*?條件[，,、 ]*您?不符合條件[，,、 ]*無法選修[。.]?",
        r"設有選課.*?條件[，,、 ]*.*?不符合.*?無法選修[。.]?",
        r"不符合.*?條件[，,、 ]*.*?無法選修[。.]?",
        r"選修的這門課與.*?衝堂[，,、 ]*.*?無法選修[。.]?",
        r"衝堂[，,、 ]*.*?無法選修[。.]?",
        r"這門課遴選不開放選修[，,、 ]*所以無法選修[。.]?",
        r"這門課.*?無法選修[。.]?",
        r"課程人數額滿[。.]?",
        r"人數額滿[。.]?",
        r"名額已滿[。.]?",
        r"重複選課[（(]?.*?[）)]?",
        r"已經在您的選課表.*?重複選課[。.]?",
        r"已經修過.*?請勿重複選課[。.]?",
        r"非選課.*?開放時間[。.]?",
        r"無法選修[。.]?",
        r"無法加選[。.]?",
        r"選修失敗[。.]?",
    ]
    matches: list[str] = []
    if _has_class_restriction_rejection(normalized_text) or _has_class_restriction_rejection(normalized_plain_text):
        _append_unique_notice(matches, "本門課設有選課班級條件，您不符合條件，無法選修。")
    for pattern in patterns:
        for match in re.finditer(pattern, normalized_text, re.IGNORECASE):
            text_value = normalize(match.group(0))
            if _is_action_notice_text(text_value):
                _append_unique_notice(matches, text_value)
    return matches[:5]


def _has_class_restriction_rejection(text: str) -> bool:
    return (
        ("設有選課" in text or "選課班級" in text or "班級條件" in text)
        and "不符合" in text
        and "無法選修" in text
    )


def _extract_action_notice_candidates(text: str) -> list[str]:
    candidates: list[str] = []
    for raw_line in re.split(r"[\n\r;]+", text):
        line = normalize(raw_line.strip(" '\"`()[]{}"))
        if _has_class_restriction_rejection(line):
            _append_unique_notice(candidates, "本門課設有選課班級條件，您不符合條件，無法選修。")
            continue
        if not _is_action_notice_text(line):
            continue
        candidates.append(line)
    return candidates


def _extract_script_action_messages(text: str) -> list[str]:
    messages: list[str] = []
    for match in re.finditer(r"(?:alert|swal|Swal\.fire)\s*\(\s*['\"](?P<message>[^'\"]+)['\"]", text):
        for candidate in _extract_action_notice_candidates(match.group("message")):
            if candidate not in messages:
                messages.append(candidate)
    return messages


def _is_action_notice_text(text: str) -> bool:
    if not text or len(text) > 180:
        return False
    if any(skip in text for skip in ("訊息公告", "志願序登記至多", "請直接拖拉", "待選清單")):
        return False
    return any(keyword in text for keyword in ("不符合", "無法", "失敗", "額滿", "重複", "已加入", "成功", "不存在", "衝堂"))


def _merge_unique_texts(primary: list[str], secondary: list[str]) -> list[str]:
    merged: list[str] = []
    for text in [*primary, *secondary]:
        normalized = normalize(str(text))
        _append_unique_notice(merged, normalized)
    return merged[:10]


def _append_unique_notice(notices: list[str], text: str) -> None:
    normalized = _canonical_action_notice(normalize(text))
    if not normalized:
        return
    for existing in list(notices):
        if normalized == existing or normalized in existing:
            return
        if existing in normalized:
            notices.remove(existing)
    notices.append(normalized)


def _canonical_action_notice(text: str) -> str:
    if _has_class_restriction_rejection(text):
        return "本門課設有選課班級條件，您不符合條件，無法選修。"
    return text


def _extract_div_table_rows(container: Tag | None) -> list[list[str]]:
    if not isinstance(container, Tag):
        return []
    rows: list[list[str]] = []
    for row in container.select(".table-row"):
        if not isinstance(row, Tag):
            continue
        cells = [
            _clean_cell_text(cell)
            for cell in row.select(".table-cell")
            if isinstance(cell, Tag)
        ]
        if cells:
            rows.append(cells)
    return rows


def _extract_html_table_rows(table: Tag | None) -> list[list[str]]:
    if not isinstance(table, Tag):
        return []
    rows: list[list[str]] = []
    for tr in table.find_all("tr"):
        if not isinstance(tr, Tag):
            continue
        cells = [_clean_cell_text(cell) for cell in tr.find_all(["th", "td"]) if isinstance(cell, Tag)]
        if cells:
            rows.append(cells)
    return rows


def _find_table_containing(soup: BeautifulSoup, labels: list[str]) -> Tag | None:
    for table in soup.find_all("table"):
        if not isinstance(table, Tag):
            continue
        text = normalize(table.get_text(" ", strip=True))
        if all(label in text for label in labels):
            return table
    return None


def _drop_header_rows(rows: list[list[str]], expected_headers: set[str]) -> list[list[str]]:
    return [
        row
        for row in rows
        if len(expected_headers.intersection(set(row))) < 2
    ]


def _clean_cell_text(cell: Tag) -> str:
    lines = split_lines(cell.get_text("\n", strip=True))
    return normalize(" ".join(lines))


def _as_int(value: Any) -> int | None:
    match = re.search(r"\d+", str(value or ""))
    return int(match.group(0)) if match else None


def _as_float(value: Any) -> float | None:
    match = re.search(r"\d+(?:\.\d+)?", str(value or ""))
    return float(match.group(0)) if match else None


def _row_value(row: dict[str, str], aliases: list[str]) -> str:
    compact_aliases = {normalize(alias).replace(" ", "") for alias in aliases}
    for key, value in row.items():
        if normalize(key).replace(" ", "") in compact_aliases:
            return value
    return ""


def _is_auth_response(response: requests.Response) -> bool:
    url = response.url.lower()
    return "signin-oidc" in url or "ssoam" in url or "/login" in url or "account/login" in url
