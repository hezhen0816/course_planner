# 待辦事項（≤300 行）

## 這份文件放什麼

**未完成事項的唯一摘要**，按優先度排。完成後直接移除該項，不留「已完成」段落。
決策理由寫 `HISTORY.md`，當前規則寫 `AGENTS.md`。

本文件是**待辦清單，不是工作指令**。動手前一律重新確認真實狀態。

## P0 正確性／阻斷性

- [ ] 刪除 Railway 專案 `giving-light`（舊監控 worker，連著 NTUST_Course_Monitor repo，每次 push 會自動重新部署並與 Windows worker 重複跑）與 `course-compass-backend`（指舊 Supabase 專案）。需使用者在 Railway 後台或以 `railway delete` 執行；刪前先把 `giving-light` 環境變數裡的 RESEND_API_KEY 換掉或確認可作廢。
- [ ] 手機 App 尚未實測 https 路徑：Xcode 27 Beta 6 裝機成功，但還沒從後端 log 看到手機經 `hezhen.taile9e4a0.ts.net` 的請求；請使用者開 Tailscale 後同步一次並確認。

## P1 業務主線

- [ ] 登入流程合一（Phase 2 未完成項）：`EnrollmentClient.login` 改用 `ntust_common.login_to_target` 在正式環境失敗（見 HISTORY 2026-09-08），需在不打正式 SSO 的前提下比對兩套流程的請求差異（表單選取、hidden 欄位、headers、redirect 順序）。在釐清前兩套並存：monitor 用自己的，Compass 呼叫端用 `ntust_common`。
- [ ] 淘汰 `ENCRYPTION_KEY`：worker 已優先讀 `app_private`；等 Monitor 前端併入（不再寫 `user_settings.student_password`）後移除 legacy 路徑與 `rotate_encryption_key.py`。
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
- [ ] Supabase 免費方案閒置會暫停；可考慮排程定期呼叫 API 保持活躍。

## 需使用者裁示

- [ ] 兩位使用者（heij82351、bocho960321）的校務帳號在 SSO 送出後得到「Error. An error occurred while processing your request」錯誤頁（2026-09-08 凌晨，同一段程式對第三位帳號正常），worker 每 15 分鐘會再試 3 次。請他們用瀏覽器登入 https://courseselection.ntust.edu.tw 看 SSO 是否要求改密碼或顯示其他訊息。
- [ ] Web 是否需要在 tailnet 外使用。若要，需 Tailscale Funnel 加後端額外驗證層；目前決定不做。
