from __future__ import annotations

from typing import Any

import requests
from bs4 import BeautifulSoup, Tag

try:
    from .config import EDU_NEED_URL
    from .ntust_common import login_to_target, normalize
    from .time_utils import now
except ImportError:  # pragma: no cover
    from config import EDU_NEED_URL
    from ntust_common import login_to_target, normalize
    from time_utils import now

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

