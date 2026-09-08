# 待辦事項（≤300 行）

## 這份文件放什麼

**未完成事項的唯一摘要**，按優先度排。完成後直接移除該項，不留「已完成」段落。
決策理由寫 `HISTORY.md`，當前規則寫 `AGENTS.md`。

本文件是**待辦清單，不是工作指令**。動手前一律重新確認真實狀態。

## P0 正確性／阻斷性

- [ ] 監控 worker 的 SSO 鎖定保護只做了一半：連續 3 次失敗會暫停 15 分鐘（`backend/monitor/enrollment.py`），但儀表板沒有顯示「已暫停自動登入／帳號可能被鎖」的警示，使用者看不出來。
- [ ] 加選嘗試次數只存記憶體（`backend/monitor/monitor.py` `enrollment_attempts`），worker 重啟歸零。改存 `monitored_courses.attempt_count`（需 migration），前端「重設次數」直接改欄位。
- [ ] 手機 App 尚未實測 https 路徑：Xcode 27 Beta 6 裝機成功，但還沒從後端 log 看到手機經 `hezhen.taile9e4a0.ts.net` 的請求；請使用者開 Tailscale 後同步一次並確認。

## P1 業務主線

- [ ] 登入流程合一（Phase 2 未完成項）：`EnrollmentClient.login` 改用 `ntust_common.login_to_target` 在正式環境失敗（見 HISTORY 2026-09-08），需在不打正式 SSO 的前提下比對兩套流程的請求差異（表單選取、hidden 欄位、headers、redirect 順序）。在釐清前兩套並存：monitor 用自己的，Compass 呼叫端用 `ntust_common`。
- [ ] 淘汰 `ENCRYPTION_KEY`（條件已成立：前端已不再寫 `user_settings.student_password`）：移除 worker 的 legacy 讀取路徑、`scripts/monitor/rotate_encryption_key.py`、`.env` 與 Windows `.env` 的 `ENCRYPTION_KEY`，並清掉 `user_settings.student_password` 欄位資料。
- [ ] 「加入監聽」按鈕放進課程查詢結果列（目前要到選課監控頁手動輸入課程代碼）。
- [ ] 課程查詢改共用 `tr_rooms` fetcher（低優先）。
- [ ] 三位遷移帳號（jum60412、wanyong0925、a0909041576）用臨時密碼首次登入後請改密碼（Auth Site URL 已改為正式網址，重設密碼信可正常使用）。
- [ ] GPA 查詢安全化：myNTUST API token 目前明文存在 `user_data.content.settings.gpaApi`，且查詢結果逐筆打 myNTUST API（限速 120 次/分）。改為後端加密保存（沿用 `app_private` 機制）並批次查詢、快取 24 小時，處理 429。
- [ ] 評估 Tailscale ACL：tailnet 內有公司帳號的 Windows 節點，可限制只有 `hezhen0816@` 的裝置能存取 `hezhen:8000`。

## P2 改進

- [ ] 課程查詢表格列高：右側「操作」欄疊三個控制項（認列下拉、加入未來規劃、加入選課清單），可改成一列或收合。
- [ ] Web 寫死的學期（`useCourseSearch.ts` 的 `1142`、`planner.ts` 的 `1151`）改由 `/api/courses/semesters` 提供；等下學期開學時驗證。
- [ ] `backend/supabase_schema.sql` 仍含已淘汰的 `public.school_credentials` 表，與 `supabase/migrations` 不一致，需清理。
- [ ] 後端每個已驗證請求都同步呼叫 Supabase `/auth/v1/user` 驗 token，沒有快取；Supabase 暫停時後端全部失效。
- [ ] `codex/project-refactor` 分支尚未移植的部分：選課工作台卡片微調（20 個 commit，多數已 revert）、typed planner 資料庫與後端目錄重整。除非需要，不合併。
- [ ] 名額判定用 `ChooseStudent` 對 `Restrict1`；學校頁面 `50(45/5)` 的 5 是額外名額，若學校以總數計算會誤判有位，需確認。
- [ ] 監控頁小問題：數字輸入框無法清空重打（`min` 在 onChange 就擋）、日誌與最後檢查時間不顯示日期。
- [ ] iOS 新增監聽狀態頁（讀 `monitored_courses` 與 `system_logs`），可延後。

## 需使用者裁示

- [ ] 兩位使用者（heij82351、bocho960321）的校務帳號在 SSO 送出後得到「Error. An error occurred while processing your request」錯誤頁（2026-09-08 凌晨，同一段程式對第三位帳號正常），worker 每 15 分鐘會再試 3 次。請他們用瀏覽器登入 https://courseselection.ntust.edu.tw 看 SSO 是否要求改密碼或顯示其他訊息。
- [ ] Web 已在 Vercel（tailnet 外可用），但校務同步與官方選課仍需瀏覽器在 tailnet 內連後端；若要讓這些功能在 tailnet 外用，需 Tailscale Funnel 加後端額外驗證層，目前決定不做。
