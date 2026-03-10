from __future__ import annotations

import csv
import json
import os
import re
from datetime import datetime
from pathlib import Path
from urllib.parse import urljoin
from zoneinfo import ZoneInfo

import requests
import urllib3
from bs4 import BeautifulSoup, Tag


OUTPUT_DIR = Path(__file__).resolve().parent
TAIPEI = ZoneInfo("Asia/Taipei")
USERNAME = os.environ.get("NTUST_USERNAME")
PASSWORD = os.environ.get("NTUST_PASSWORD")
BASE_URL = "https://courseselection.ntust.edu.tw"
ENTRY_URL = f"{BASE_URL}/"
VERIFY_URL = f"{BASE_URL}/First/A06/A06"
COURSE_LIST_URL = f"{BASE_URL}/ChooseList/D01/D01"
DEFAULT_TIMEOUT = 30
VERIFY_SSL = os.environ.get("NTUST_VERIFY_SSL", "false").lower() in {"true", "1", "yes"}

if not USERNAME or not PASSWORD:
    raise SystemExit("Missing NTUST_USERNAME or NTUST_PASSWORD.")

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)


flow: list[dict[str, str]] = []


def now() -> str:
    return datetime.now(TAIPEI).isoformat()


def record(step: str, url: str, note: str = "") -> None:
    flow.append(
        {
            "step": step,
            "note": note,
            "timestamp": now(),
            "url": url,
        }
    )


def write_json(filename: str, payload: object) -> None:
    (OUTPUT_DIR / filename).write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )


def write_csv(filename: str, fieldnames: list[str], rows: list[dict[str, object]]) -> None:
    with (OUTPUT_DIR / filename).open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def render_flow_markdown(entries: list[dict[str, str]]) -> str:
    lines = ["# 選課清單抓取流程紀錄", ""]
    for entry in entries:
        line = f"- {entry['timestamp']} | {entry['step']} | {entry['url']}"
        if entry["note"]:
            line += f" | {entry['note']}"
        lines.append(line)
    lines.append("")
    return "\n".join(lines)


def write_debug_html(filename: str, html: str) -> None:
    (OUTPUT_DIR / filename).write_text(html, encoding="utf-8")


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
    step: str,
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
        verify=VERIFY_SSL,
    )
    response.raise_for_status()
    record(step, response.url, "submitted hidden callback form")
    return response


def login(session: requests.Session) -> requests.Response:
    entry_response = session.get(
        ENTRY_URL,
        timeout=DEFAULT_TIMEOUT,
        allow_redirects=True,
        verify=VERIFY_SSL,
    )
    entry_response.raise_for_status()
    record("open-entry", entry_response.url, "opened course selection entry")

    login_url = build_login_url(entry_response)
    login_page = session.get(
        login_url,
        timeout=DEFAULT_TIMEOUT,
        allow_redirects=True,
        verify=VERIFY_SSL,
    )
    login_page.raise_for_status()
    record("open-sso-login", login_page.url, "loaded SSO login page")

    soup = BeautifulSoup(login_page.text, "html.parser")
    form = first_form(soup)
    login_data = parse_hidden_inputs(form)
    login_data["Username"] = USERNAME
    login_data["Password"] = PASSWORD
    login_data.setdefault("captcha", "")

    submit_url = urljoin(login_page.url, form.get("action", ""))
    login_response = session.post(
        submit_url,
        data=login_data,
        timeout=DEFAULT_TIMEOUT,
        allow_redirects=True,
        verify=VERIFY_SSL,
    )
    login_response.raise_for_status()
    record("submit-sso-login", login_response.url, "submitted SSO credentials")

    if "signin-oidc" in login_response.url:
        login_response = submit_hidden_form(session, login_response, "submit-oidc-callback")

    if "login" in login_response.url.lower() and "ssoam" in login_response.url:
        write_debug_html("login-timeout.html", login_response.text)
        error_text = find_error_text(BeautifulSoup(login_response.text, "html.parser"))
        if error_text:
            raise RuntimeError(f"SSO 登入失敗：{error_text}")
        raise RuntimeError(f"SSO 登入失敗，仍停留在登入頁：{login_response.url}")

    verify_response = session.get(
        VERIFY_URL,
        timeout=DEFAULT_TIMEOUT,
        allow_redirects=True,
        verify=VERIFY_SSL,
    )
    verify_response.raise_for_status()
    record("verify-session", verify_response.url, "verified authenticated course selection session")

    if "signin-oidc" in verify_response.url:
        verify_response = submit_hidden_form(session, verify_response, "submit-verify-oidc")

    if "login" in verify_response.url.lower() or "ssoam" in verify_response.url:
        write_debug_html("login-timeout.html", verify_response.text)
        raise RuntimeError(f"登入後驗證失敗，目前停在 {verify_response.url}")

    return verify_response


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


def parse_course_rows(table: Tag) -> list[dict[str, object]]:
    rows: list[dict[str, object]] = []
    for tr in table.find_all("tr")[1:]:
        cells = [normalize(td.get_text(" ", strip=True)) for td in tr.find_all("td")]
        if len(cells) < 6 or not cells[0] or not cells[1]:
            continue
        rows.append(
            {
                "courseCode": cells[0],
                "courseName": cells[1],
                "credits": float(cells[2]) if re.fullmatch(r"\d+(?:\.\d+)?", cells[2]) else cells[2],
                "requiredType": cells[3],
                "professor": cells[4],
                "note": cells[5],
            }
        )
    return rows


def parse_schedule_rows(table: Tag) -> list[dict[str, object]]:
    tr_rows = table.find_all("tr")
    if len(tr_rows) < 2:
        return []

    header_cells = [normalize(cell.get_text(" ", strip=True)) for cell in tr_rows[0].find_all(["th", "td"])]
    weekdays = header_cells[2:]
    slot_rows: list[dict[str, object]] = []

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
                    "weekday": weekday,
                    "period": period,
                    "time": time_text,
                    "courseName": " / ".join(lines[:-1]) if len(lines) > 1 else lines[0],
                    "location": lines[-1] if len(lines) > 1 else "",
                    "raw": " | ".join(lines),
                }
            )

    return slot_rows


def parse_course_list(html: str) -> dict[str, object]:
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
        "pageTitle": normalize(soup.title.get_text(" ", strip=True) if soup.title else ""),
        "totalCreditsText": total_credits_text,
        "courseRows": course_rows,
        "slotRows": slot_rows,
        "html": html,
    }


def main() -> None:
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

    login(session)

    page_response = session.get(
        COURSE_LIST_URL,
        timeout=DEFAULT_TIMEOUT,
        allow_redirects=True,
        verify=VERIFY_SSL,
    )
    page_response.raise_for_status()
    record("open-course-list-page", page_response.url, "loaded course list page")

    if "signin-oidc" in page_response.url:
        page_response = submit_hidden_form(session, page_response, "submit-course-list-oidc")
        page_response = session.get(
            COURSE_LIST_URL,
            timeout=DEFAULT_TIMEOUT,
            allow_redirects=True,
            verify=VERIFY_SSL,
        )
        page_response.raise_for_status()
        record("reload-course-list-page", page_response.url, "reloaded course list page after OIDC callback")

    if "login" in page_response.url.lower() or "ssoam" in page_response.url:
        write_debug_html("courselist-timeout.html", page_response.text)
        raise RuntimeError(f"無法進入選課清單頁面，目前停在 {page_response.url}")

    extracted = parse_course_list(page_response.text)
    total_credits_match = re.search(r"(\d+(?:\.\d+)?)", str(extracted["totalCreditsText"]))
    total_credits = float(total_credits_match.group(1)) if total_credits_match else None

    (OUTPUT_DIR / "courselist-page.html").write_text(page_response.text, encoding="utf-8")
    write_json("selected-courses.json", extracted["courseRows"])
    write_json("schedule-slots.json", extracted["slotRows"])
    (OUTPUT_DIR / "flow-log.md").write_text(render_flow_markdown(flow), encoding="utf-8")
    write_json(
        "run-summary.json",
        {
            "generatedAt": now(),
            "url": page_response.url,
            "title": extracted["pageTitle"],
            "totalCredits": total_credits,
            "courseCount": len(extracted["courseRows"]),
            "scheduledSlotCount": len(extracted["slotRows"]),
        },
    )
    write_csv(
        "courses.csv",
        ["courseCode", "courseName", "credits", "requiredType", "professor", "note"],
        extracted["courseRows"],
    )
    write_csv(
        "schedule.csv",
        ["weekday", "period", "time", "courseName", "location", "raw"],
        extracted["slotRows"],
    )

    print(
        json.dumps(
            {
                "outputDir": str(OUTPUT_DIR),
                "totalCredits": total_credits,
                "courseCount": len(extracted["courseRows"]),
                "scheduledSlotCount": len(extracted["slotRows"]),
            },
            ensure_ascii=False,
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
