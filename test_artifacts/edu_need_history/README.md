# 台科大歷史修課紀錄測試資料

這個資料夾包含一個可重跑的 Python 自動化腳本，用來登入 `https://stu.ntust.edu.tw/stueduneed/Edu_Need.aspx`，抓取學生必修課程查詢頁面中的歷史修課紀錄並輸出 CSV。

## Python 安裝

```bash
cd /Users/hezhen/Project/course_planner/test_artifacts/edu_need_history
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt
```

## Python 執行

```bash
cd /Users/hezhen/Project/course_planner/test_artifacts/edu_need_history
NTUST_USERNAME="你的學號" \
NTUST_PASSWORD="你的校務密碼" \
.venv/bin/python fetch_edu_need_history.py
```

如需強制驗證站台憑證，可額外指定：

```bash
NTUST_VERIFY_SSL=true
```

台科站台目前在 `requests` 下可能出現憑證鏈驗證問題，所以腳本預設使用 `NTUST_VERIFY_SSL=false`。

## 產物

- `edu-need-page.html`: 學生必修課程查詢原始 HTML
- `history-courses.json`: 平面化課程紀錄 JSON
- `history-courses.csv`: 平面化課程紀錄 CSV
- `run-summary.json`: 本次執行摘要
- `flow-log.md`: 從登入到開啟頁面的流程紀錄
