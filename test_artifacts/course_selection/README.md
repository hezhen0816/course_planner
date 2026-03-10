# 台科大選課清單測試資料

這個資料夾包含一個可重跑的 Python 自動化腳本，用來登入 `https://courseselection.ntust.edu.tw/`、進入「選課清單」、保存原始頁面並輸出 CSV。

## Python 安裝

```bash
cd /Users/hezhen/Project/course_planner/test_artifacts/course_selection
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt
```

## Python 執行

```bash
cd /Users/hezhen/Project/course_planner/test_artifacts/course_selection
NTUST_USERNAME="你的學號" \
NTUST_PASSWORD="你的校務密碼" \
.venv/bin/python fetch_course_schedule.py
```

如需強制驗證站台憑證，可額外指定：

```bash
NTUST_VERIFY_SSL=true
```

台科站台目前在 `requests` 下可能出現憑證鏈驗證問題，所以腳本預設使用 `NTUST_VERIFY_SSL=false`。

## 產物

- `courselist-page.html`: 選課清單頁原始 HTML
- `selected-courses.json`: 課程清單 JSON
- `schedule-slots.json`: 課表平面化 JSON
- `courses.csv`: 課程清單 CSV
- `schedule.csv`: 課表時段 CSV
- `run-summary.json`: 本次執行摘要
- `flow-log.md`: 從登入到開啟課表的流程紀錄

## 已驗證流程

2026-03-10 已驗證以下流程可達：

1. `GET` 選課系統入口並取得 SSO 登入頁。
2. 解析 SSO 登入表單與 hidden inputs，直接提交帳密。
3. 遇到 `signin-oidc` callback 時自動提交回傳表單。
4. 進入 `/ChooseList/D01/D01` 後解析課程表格與課表表格。
