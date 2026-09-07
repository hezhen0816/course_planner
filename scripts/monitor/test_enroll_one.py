#!/usr/bin/env python3
"""
單次加選測試：對指定課程代碼送出一筆加選請求。
使用方式（在 backend 目錄下）：
  python scripts/test_enroll_one.py 3NG124701           # 電腦抽選後選課 (A06)
  python scripts/test_enroll_one.py --b01 3NG124701    # 加退選 (B01)
或先設定學號密碼：
  export NTUST_STUDENT_ID=<你的學號>
  export NTUST_STUDENT_PASSWORD=<你的密碼>
  python scripts/test_enroll_one.py 3NG124701
兩個環境變數皆為必填。
"""
import os
import sys

# 讓 backend 為 root，才能 import src
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from dotenv import load_dotenv

# 載入環境變數：frontend/.env、config/.env、backend/.env
for rel in ('frontend/.env', 'config/.env', '.env'):
    env_path = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), rel)
    if not os.path.isabs(env_path):
        env_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), rel)
    if os.path.exists(env_path):
        load_dotenv(env_path)

from backend.monitor.semester import get_default_semester

def main():
    argv = [a for a in sys.argv[1:] if a and not a.startswith("-")]
    use_b01 = "--b01" in sys.argv or "-b" in sys.argv
    course_no = argv[0].strip() if argv else "3NG124701"

    # 學號密碼只從環境變數取；不再從 Supabase 撈其他使用者的憑證
    student_id = os.getenv("NTUST_STUDENT_ID", "").strip()
    password = os.getenv("NTUST_STUDENT_PASSWORD", "").strip()

    if not student_id or not password:
        print("請設定 NTUST_STUDENT_ID 與 NTUST_STUDENT_PASSWORD 環境變數。", file=sys.stderr)
        sys.exit(1)

    semester = get_default_semester(verify_ssl=False)

    from backend.monitor.config import CourseConfig
    from backend.monitor.api_client import NTUSTCourseAPI
    from backend.monitor.enrollment import EnrollmentClient

    # 查詢課程取得 course_info
    api = NTUSTCourseAPI(verify_ssl=False)
    course_info = api.get_course_by_code(course_no, semester=semester)
    if not course_info:
        print(f"查無課程: {course_no}（學期 {semester}）")
        sys.exit(2)

    course = CourseConfig(
        course_no=course_no,
        course_name=course_info.get("CourseName", ""),
        semester=semester,
        alias=course_info.get("CourseName", course_no),
    )
    print(f"課程: {course_info.get('CourseName')} ({course_no})")
    print("登入中...")
    client = EnrollmentClient(verify_ssl=False)
    ok, msg = client.login(student_id, password)
    if not ok:
        print(f"登入失敗: {msg}")
        sys.exit(3)
    print("登入成功，送出加選請求（加退選 B01）..." if use_b01 else "登入成功，送出加選請求...")
    success, message = client.enroll_course(
        course, course_info, student_id, password, use_add_drop=use_b01
    )
    if success:
        print(f"加選成功: {message}")
    else:
        print(f"加選失敗: {message}")
    sys.exit(0 if success else 4)

if __name__ == "__main__":
    main()
