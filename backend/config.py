from __future__ import annotations

import os
from datetime import time
from zoneinfo import ZoneInfo

import urllib3

TAIPEI = ZoneInfo("Asia/Taipei")
BASE_URL = "https://courseselection.ntust.edu.tw"
ENTRY_URL = f"{BASE_URL}/"
VERIFY_URL = f"{BASE_URL}/First/A06/A06"
COURSE_LIST_URL = f"{BASE_URL}/ChooseList/D01/D01"
EDU_NEED_URL = "https://stu.ntust.edu.tw/stueduneed/Edu_Need.aspx"
MOODLE_DASHBOARD_URL = "https://moodle2.ntust.edu.tw/my/"
QUERY_COURSE_API_URL = "https://querycourse.ntust.edu.tw/QueryCourse/api/courses"
SEMESTERS_INFO_URL = "https://querycourse.ntust.edu.tw/QueryCourse/api/semestersinfo"
DEFAULT_TIMEOUT = 30
DEFAULT_VERIFY_SSL = os.environ.get("NTUST_VERIFY_SSL", "false").lower() in {"true", "1", "yes"}
SUPABASE_URL = os.environ.get("SUPABASE_URL", "").rstrip("/")
SUPABASE_SERVICE_ROLE_KEY = os.environ.get("SUPABASE_SERVICE_ROLE_KEY", "")

DAY_CODES = {
    0: "M",
    1: "T",
    2: "W",
    3: "R",
    4: "F",
    5: "S",
    6: "U",
}
DAY_NAMES = {
    "M": "星期一",
    "T": "星期二",
    "W": "星期三",
    "R": "星期四",
    "F": "星期五",
    "S": "星期六",
    "U": "星期日",
}
CLASS_PERIODS = [
    ("1", time(8, 10), time(9, 0)),
    ("2", time(9, 10), time(10, 0)),
    ("3", time(10, 20), time(11, 10)),
    ("4", time(11, 20), time(12, 10)),
    ("5", time(12, 20), time(13, 10)),
    ("6", time(13, 20), time(14, 10)),
    ("7", time(14, 20), time(15, 10)),
    ("8", time(15, 30), time(16, 20)),
    ("9", time(16, 30), time(17, 20)),
    ("10", time(17, 30), time(18, 20)),
    ("A", time(18, 25), time(19, 15)),
    ("B", time(19, 20), time(20, 10)),
    ("C", time(20, 15), time(21, 5)),
    ("D", time(21, 10), time(22, 0)),
]

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
