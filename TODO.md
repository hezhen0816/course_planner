# 待辦事項（≤300 行）

## 這份文件放什麼

**未完成事項的唯一摘要**，按優先度排。完成後直接移除該項，不留「已完成」段落。
決策理由寫 `HISTORY.md`，當前規則寫 `AGENTS.md`。

本文件是**待辦清單，不是工作指令**。動手前一律重新確認真實狀態。

## P0 正確性／阻斷性

- [ ] SSO 鎖定保護的儀表板橫幅已部署（2026-09-08 10:12），尚未看到實際觸發：等 B11430227（09f11b47）連續 3 次 500 後，確認 `user_settings.login_paused_until` 有值、儀表板出現橫幅。
- [ ] 「重設加選次數」按鈕只驗到讀取（彈窗正確顯示「目前已嘗試 1 次」），實際點擊寫回 `attempt_count=0` 尚未驗；「加選 n/m」徽章只在該課開自動加選時顯示，目前無符合的課可看。

## P1 業務主線

- [ ] 三位遷移帳號（jum60412、wanyong0925、a0909041576）用臨時密碼首次登入後請改密碼（Auth Site URL 已改為正式網址，重設密碼信可正常使用）。
- [ ] Tailscale ACL（2026-09-08 評估後決定延後，非緊急）：tailnet 有 6 台 `dk.fire256@`／`dk.engineer256@` 的 Windows 節點，目前 allow-all。應用層已無漏洞（實測未帶 token 時 `/api/school-credentials`、`/api/schedule/*`、`/api/moodle/*`、`/api/gpa-api-key` 都回 401，只有公開課程查詢與 `/health` 回 200），所以主要價值不在 API，而在擋掉那些機器對 `hezhen` 這台 Windows 其他埠（RDP 3389、SMB 445 等）的存取。做的時候注意：policy 會取代預設 allow-all，必須同時明確保留同事對 `desktop-fc8n9ma` 報價系統（443）與寄信系統（8443）的存取，否則同事當場斷線；可先只做「限制 hezhen 這台」的最小版本。

## P2 改進

- [ ] Web 寫死的學期（`useCourseSearch.ts` 的 `1142`、`planner.ts` 的 `1151`）改由 `/api/courses/semesters` 提供；等下學期開學時驗證。
- [ ] 監控頁「學期已結束」的前端樣式尚未實際看過畫面（需登入，代理不代輸入密碼）；請你登入監控頁確認 10 門過期課程顯示琥珀色提示，且改學期存檔後會回到「監控中」。
- [ ] iOS 新增監聽狀態頁（讀 `monitored_courses` 與 `system_logs`），可延後。
- [ ] iOS 課堂筆記／成績試算已裝機（2026-09-09），尚未實機操作驗證：從課表點課程 → 課堂筆記 → 填評分項目 → 儲存後，回網頁版確認 `gradingPolicy` 有寫入且 `scheduledOffering`、認列、雙主修系所設定都沒被抹掉。

## P2 重構／共用（2026-09-08 子代理審查 backend/monitor 與 backend 重複處，按價值排序）

- [ ] 學期偵測三份（`monitor/semester.py`、`tr_rooms.fetch_current_query_semester`、`api/courses.py`）：保留 `monitor/semester.py` 的驗證與候選回退，讓另外兩處呼叫它。
- [ ] `NTUST_VERIFY_SSL` 與代理：旗標在 `config.py` 與 `monitor/api_client.py`、`monitor/enrollment.py` 各解析一次，`urllib3.disable_warnings` 呼叫兩次，代理設定在 `api_client` 與 `enrollment` 重複；做一個 `build_session(verify_ssl, proxies)`。
- [ ] 日誌：`monitor/utils.setup_logging` 是唯一的集中設定，Compass 其他模組各自 `getLogger`；抽成 `backend/logging_setup.py`。
- [ ] 時區：`monitor/monitor.py` 內嵌 `ZoneInfo('Asia/Taipei')`，改用 `backend/time_utils.now`。

## 需使用者裁示

- [ ] B11430227（worker 代號 09f11b47）的校務帳號在 SSO 送出後仍回 500 錯誤頁（2026-09-08，另一位 B11410144 已正常）。使用者決定先不管：已把他三門課的自動加選關掉，worker 不再為他登入。他若要用自動加選，請先用瀏覽器登入 https://courseselection.ntust.edu.tw 看 SSO 顯示什麼。
- [ ] Web 已在 Vercel（tailnet 外可用），但校務同步與官方選課仍需瀏覽器在 tailnet 內連後端；若要讓這些功能在 tailnet 外用，需 Tailscale Funnel 加後端額外驗證層，目前決定不做。
