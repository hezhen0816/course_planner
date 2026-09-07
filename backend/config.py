from __future__ import annotations

import os
from datetime import time
from zoneinfo import ZoneInfo

import urllib3

TAIPEI = ZoneInfo("Asia/Taipei")
BASE_URL = "https://courseselection.ntust.edu.tw"
ENTRY_URL = f"{BASE_URL}/"
VERIFY_URL = f"{BASE_URL}/First/A06/A06"
INITIAL_SELECTION_URL = f"{BASE_URL}/First/A02/A02"
INITIAL_SELECTION_CHOOSE_COURSE_LIST_URL = f"{BASE_URL}/First/A02/ChooseCourseList"
INITIAL_SELECTION_JOIN_URL = f"{BASE_URL}/First/A02/Join"
INITIAL_SELECTION_EXTRA_JOIN_URL = f"{BASE_URL}/First/A02/ExtraJoin"
INITIAL_SELECTION_REMOVE_URL = f"{BASE_URL}/First/A02/SubCourse"
INITIAL_SELECTION_SAVE_INDEX_URL = f"{BASE_URL}/First/A02/SaveIdx"
COURSE_LIST_URL = f"{BASE_URL}/ChooseList/D01/D01"
EDU_NEED_URL = "https://stu.ntust.edu.tw/stueduneed/Edu_Need.aspx"
SCORE_DISPLAY_ALL_URL = "https://stuinfosys.ntust.edu.tw/StuScoreQueryServ/StuScoreQuery/DisplayAll"
MOODLE_DASHBOARD_URL = "https://moodle2.ntust.edu.tw/my/"
QUERY_COURSE_API_URL = "https://querycourse.ntust.edu.tw/QueryCourse/api/courses"
SEMESTERS_INFO_URL = "https://querycourse.ntust.edu.tw/QueryCourse/api/semestersinfo"
DEFAULT_TIMEOUT = 30
DEFAULT_VERIFY_SSL = os.environ.get("NTUST_VERIFY_SSL", "true").lower() in {"true", "1", "yes"}
SUPABASE_URL = os.environ.get("SUPABASE_URL", "").rstrip("/")
SUPABASE_ANON_KEY = os.environ.get("SUPABASE_ANON_KEY") or os.environ.get("VITE_SUPABASE_ANON_KEY", "")
SUPABASE_SERVICE_ROLE_KEY = os.environ.get("SUPABASE_SERVICE_ROLE_KEY", "")
SCHOOL_CREDENTIALS_ENCRYPTION_SECRET = (
    os.environ.get("SCHOOL_CREDENTIALS_ENCRYPTION_SECRET")
    or os.environ.get("COURSE_COMPASS_CREDENTIALS_SECRET")
    or ""
)

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
