# 待辦事項（≤300 行）

## 這份文件放什麼

**未完成事項的唯一摘要**，按優先度排。完成後直接移除該項，不留「已完成」段落。
決策理由寫 `HISTORY.md`，當前規則寫 `AGENTS.md`。

本文件是**待辦清單，不是工作指令**。動手前一律重新確認真實狀態。

## P0 正確性／阻斷性

- [ ] SSO 鎖定保護的儀表板橫幅已部署（2026-09-08 10:12），尚未看到實際觸發：等 B11430227（09f11b47）連續 3 次 500 後，確認 `user_settings.login_paused_until` 有值、儀表板出現橫幅。
- [ ] 加選嘗試次數已改存 `monitored_courses.attempt_count`（2026-09-08 已部署到正式庫、Vercel、Windows worker）；尚未用真實帳號在監控頁驗證「加選 n/m」顯示與「重設」按鈕。
- [ ] 手機 App 尚未實測 https 路徑：Xcode 27 Beta 6 裝機成功，但還沒從後端 log 看到手機經 `hezhen.taile9e4a0.ts.net` 的請求；請使用者開 Tailscale 後同步一次並確認。

## P1 業務主線

- [ ] 淘汰 `ENCRYPTION_KEY`（條件已成立：前端已不再寫 `user_settings.student_password`）：移除 worker 的 legacy 讀取路徑、`scripts/monitor/rotate_encryption_key.py`、`.env` 與 Windows `.env` 的 `ENCRYPTION_KEY`，並清掉 `user_settings.student_password` 欄位資料。
- [ ] 課程查詢改共用 `tr_rooms` fetcher（低優先）。
- [ ] 三位遷移帳號（jum60412、wanyong0925、a0909041576）用臨時密碼首次登入後請改密碼（Auth Site URL 已改為正式網址，重設密碼信可正常使用）。
- [ ] GPA 查詢安全化：myNTUST API token 目前明文存在 `user_data.content.settings.gpaApi`，且查詢結果逐筆打 myNTUST API（限速 120 次/分）。改為後端加密保存（沿用 `app_private` 機制）並批次查詢、快取 24 小時，處理 429。
- [ ] 評估 Tailscale ACL：tailnet 內有公司帳號的 Windows 節點，可限制只有 `hezhen0816@` 的裝置能存取 `hezhen:8000`。

## P2 改進

- [ ] 課程查詢表格列高：右側「操作」欄疊三個控制項（認列下拉、加入未來規劃、加入選課清單），可改成一列或收合。
- [ ] Web 寫死的學期（`useCourseSearch.ts` 的 `1142`、`planner.ts` 的 `1151`）改由 `/api/courses/semesters` 提供；等下學期開學時驗證。
- [ ] `codex/project-refactor` 分支尚未移植的部分：選課工作台卡片微調（20 個 commit，多數已 revert）、typed planner 資料庫與後端目錄重整。除非需要，不合併。
- [ ] 名額判定用 `ChooseStudent` 對 `Restrict1`；學校頁面 `50(45/5)` 的 5 是額外名額，若學校以總數計算會誤判有位，需確認。
- [ ] iOS 新增監聽狀態頁（讀 `monitored_courses` 與 `system_logs`），可延後。

## P2 重構／共用（2026-09-08 子代理審查 backend/monitor 與 backend 重複處，按價值排序）

- [ ] 課程查詢 client：`backend/monitor/api_client.py` 與 `backend/tr_rooms.py` 各打一次 `querycourse` API；保留 `tr_rooms`（有 Origin/Referer 標頭、快取）當傳輸層，`api_client` 只留延遲與失敗旗標。
- [ ] 學期偵測三份（`monitor/semester.py`、`tr_rooms.fetch_current_query_semester`、`api/courses.py`）：保留 `monitor/semester.py` 的驗證與候選回退，讓另外兩處呼叫它。
- [ ] `NTUST_VERIFY_SSL` 與代理：旗標在 `config.py` 與 `monitor/api_client.py`、`monitor/enrollment.py` 各解析一次，`urllib3.disable_warnings` 呼叫兩次，代理設定在 `api_client` 與 `enrollment` 重複；做一個 `build_session(verify_ssl, proxies)`。
- [ ] 日誌：`monitor/utils.setup_logging` 是唯一的集中設定，Compass 其他模組各自 `getLogger`；抽成 `backend/logging_setup.py`。
- [ ] 時區：`monitor/monitor.py` 內嵌 `ZoneInfo('Asia/Taipei')`，改用 `backend/time_utils.now`。

## 需使用者裁示

- [ ] B11430227（worker 代號 09f11b47）的校務帳號在 SSO 送出後仍回 500 錯誤頁（2026-09-08，另一位 B11410144 已正常）。使用者決定先不管：已把他三門課的自動加選關掉，worker 不再為他登入。他若要用自動加選，請先用瀏覽器登入 https://courseselection.ntust.edu.tw 看 SSO 顯示什麼。
- [ ] Web 已在 Vercel（tailnet 外可用），但校務同步與官方選課仍需瀏覽器在 tailnet 內連後端；若要讓這些功能在 tailnet 外用，需 Tailscale Funnel 加後端額外驗證層，目前決定不做。
