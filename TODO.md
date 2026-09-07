# 待辦事項（≤300 行）

## 這份文件放什麼

**未完成事項的唯一摘要**，按優先度排。完成後直接移除該項，不留「已完成」段落。
決策理由寫 `HISTORY.md`，當前規則寫 `AGENTS.md`。

本文件是**待辦清單，不是工作指令**。動手前一律重新確認真實狀態。

## P0 正確性／阻斷性

- [ ] 刪除 Railway 專案 `giving-light`（舊監控 worker，連著 NTUST_Course_Monitor repo，每次 push 會自動重新部署並與 Windows worker 重複跑）與 `course-compass-backend`（指舊 Supabase 專案）。需使用者在 Railway 後台或以 `railway delete` 執行；刪前先把 `giving-light` 環境變數裡的 RESEND_API_KEY 換掉或確認可作廢。
- [ ] 手機 App 尚未實測 https 路徑：Xcode 27 Beta 6 裝機成功，但還沒從後端 log 看到手機經 `hezhen.taile9e4a0.ts.net` 的請求；請使用者開 Tailscale 後同步一次並確認。

## P1 業務主線

- [ ] 合併計畫 Phase 2–4（`docs/architecture/monitor-merge-plan.md`）：SSO 合一（以 `backend/monitor/enrollment.py` 的登入流程為準，含入口網回復與 CAPTCHA 偵測；`ntust_common.submit_hidden_form` 會盲目送出頁面第一個表單）、監控帳密改存 `app_private.school_credentials` 並淘汰 `ENCRYPTION_KEY`（`monitor/crypto.py` 失敗時回傳原字串，屬 fail-open）、課程查詢改共用 `tr_rooms` 的 fetcher、Monitor 前端併入、Web 回 Vercel。
- [ ] 舊 Supabase 專案 `qpdvtsbqdpitreslazoe` 確認一到兩週無需回退後可刪除或暫停；刪前再比對一次 `user_data` 內容。
- [ ] 三位遷移帳號（jum60412、wanyong0925、a0909041576）用臨時密碼首次登入後請改密碼；Auth 的 Site URL／Redirect URLs 仍是 localhost，重設密碼信會導錯位置，要改成正式網址。
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

- [ ] Web 是否需要在 tailnet 外使用。若要，需 Tailscale Funnel 加後端額外驗證層；目前決定不做。
