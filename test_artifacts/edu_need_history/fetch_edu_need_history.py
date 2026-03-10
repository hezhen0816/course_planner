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
VERIFY_SSL = os.environ.get("NTUST_VERIFY_SSL", "false").lower() in {"true", "1", "yes"}
DEFAULT_TIMEOUT = 30
TARGET_URL = "https://stu.ntust.edu.tw/stueduneed/Edu_Need.aspx"

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


def normalize(text: str | None) -> str:
    return (text or "").replace("\xa0", " ").replace("\r", "").strip()


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
    lines = ["# 學生必修課程查詢流程紀錄", ""]
    for entry in entries:
        line = f"- {entry['timestamp']} | {entry['step']} | {entry['url']}"
        if entry["note"]:
            line += f" | {entry['note']}"
        lines.append(line)
    lines.append("")
    return "\n".join(lines)


def first_form(soup: BeautifulSoup) -> Tag:
    form = soup.find("form")
    if not isinstance(form, Tag):
        raise RuntimeError("無法找到登入表單。")
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


def submit_hidden_form(
    session: requests.Session,
    page_response: requests.Response,
    step: str,
) -> requests.Response:
    soup = BeautifulSoup(page_response.text, "html.parser")
    form = first_form(soup)
    data = parse_hidden_inputs(form)
    action = urljoin(page_response.url, form.get("action", ""))
    response = session.post(
        action,
        data=data,
        timeout=DEFAULT_TIMEOUT,
        allow_redirects=True,
        verify=VERIFY_SSL,
    )
    response.raise_for_status()
    record(step, response.url, "submitted hidden callback form")
    return response


def login_to_target(session: requests.Session) -> requests.Response:
    entry_response = session.get(
        TARGET_URL,
        timeout=DEFAULT_TIMEOUT,
        allow_redirects=True,
        verify=VERIFY_SSL,
    )
    entry_response.raise_for_status()
    record("open-target-entry", entry_response.url, "opened target site entry")

    if "ssoam" not in entry_response.url:
        return entry_response

    soup = BeautifulSoup(entry_response.text, "html.parser")
    form = first_form(soup)
    login_data = parse_hidden_inputs(form)
    login_data["Username"] = USERNAME
    login_data["Password"] = PASSWORD
    login_data.setdefault("captcha", "")

    submit_url = urljoin(entry_response.url, form.get("action", ""))
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
        (OUTPUT_DIR / "login-timeout.html").write_text(login_response.text, encoding="utf-8")
        error_text = find_error_text(BeautifulSoup(login_response.text, "html.parser"))
        if error_text:
            raise RuntimeError(f"SSO 登入失敗：{error_text}")
        raise RuntimeError(f"SSO 登入失敗，仍停留在登入頁：{login_response.url}")

    page_response = session.get(
        TARGET_URL,
        timeout=DEFAULT_TIMEOUT,
        allow_redirects=True,
        verify=VERIFY_SSL,
    )
    page_response.raise_for_status()
    record("open-edu-need-page", page_response.url, "loaded Edu_Need page after login")

    if "signin-oidc" in page_response.url:
        page_response = submit_hidden_form(session, page_response, "submit-target-oidc")
        page_response = session.get(
            TARGET_URL,
            timeout=DEFAULT_TIMEOUT,
            allow_redirects=True,
            verify=VERIFY_SSL,
        )
        page_response.raise_for_status()
        record("reload-edu-need-page", page_response.url, "reloaded Edu_Need page after OIDC callback")

    if "login" in page_response.url.lower() or "ssoam" in page_response.url:
        (OUTPUT_DIR / "login-timeout.html").write_text(page_response.text, encoding="utf-8")
        raise RuntimeError(f"登入後無法進入 Edu_Need.aspx，目前停在 {page_response.url}")

    return page_response


def extract_course_tables(soup: BeautifulSoup) -> list[dict[str, object]]:
    rows: list[dict[str, object]] = []

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
                        "courseCode": cells[0],
                        "courseName": cells[1],
                        "academicTerm": cells[2],
                        "grade": cells[3],
                        "earnedCredits": cells[4],
                    }
                )

    return rows


def extract_summary_texts(soup: BeautifulSoup) -> list[str]:
    summaries: list[str] = []
    for cell in soup.find_all("td", align="right"):
        text = normalize(cell.get_text(" ", strip=True))
        if "學分" in text:
            summaries.append(text)
    return summaries


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

    page_response = login_to_target(session)
    soup = BeautifulSoup(page_response.text, "html.parser")

    student_name = normalize(soup.select_one("#ContentPlaceHolder1_Lal_StudentName").get_text(" ", strip=True) if soup.select_one("#ContentPlaceHolder1_Lal_StudentName") else "")
    student_no = normalize(soup.select_one("#ContentPlaceHolder1_Lal_StudentNo").get_text(" ", strip=True) if soup.select_one("#ContentPlaceHolder1_Lal_StudentNo") else "")
    department = normalize(soup.select_one("#ContentPlaceHolder1_Lal_Subject").get_text(" ", strip=True) if soup.select_one("#ContentPlaceHolder1_Lal_Subject") else "")
    status = normalize(soup.select_one("#ContentPlaceHolder1_Lal_Nowcondition").get_text(" ", strip=True) if soup.select_one("#ContentPlaceHolder1_Lal_Nowcondition") else "")
    records = extract_course_tables(soup)
    summaries = extract_summary_texts(soup)

    (OUTPUT_DIR / "edu-need-page.html").write_text(page_response.text, encoding="utf-8")
    (OUTPUT_DIR / "flow-log.md").write_text(render_flow_markdown(flow), encoding="utf-8")
    write_json("history-courses.json", records)
    write_json(
        "run-summary.json",
        {
            "generatedAt": now(),
            "url": page_response.url,
            "title": normalize(soup.title.get_text(" ", strip=True) if soup.title else ""),
            "studentName": student_name,
            "studentNo": student_no,
            "department": department,
            "status": status,
            "recordCount": len(records),
            "summaryTexts": summaries,
        },
    )
    write_csv(
        "history-courses.csv",
        ["category", "courseCode", "courseName", "academicTerm", "grade", "earnedCredits"],
        records,
    )

    print(
        json.dumps(
            {
                "outputDir": str(OUTPUT_DIR),
                "recordCount": len(records),
                "studentName": student_name,
                "studentNo": student_no,
                "status": status,
            },
            ensure_ascii=False,
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
