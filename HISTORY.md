# 決策與查證歷程（≤400 行，超過搬 `docs/archive/`）

## 這份文件放什麼

只放**過程性、會過期、但之後需要回頭查的東西**：

- 已裁示的決策與**當時的理由**，尤其是被否決的方案（避免下次重提）。
- 查證結論：查過什麼、看到什麼、結論是什麼。含「查了發現沒有」。
- 一次性作業紀錄：遷移、備份、批次修復的時間與範圍。
- 已知但刻意不修的問題，以及重新評估的條件。

**不放**：當前規則（→ `AGENTS.md`）、操作方式（→ `README.md`）、
未完成事項（→ `TODO.md`）、程式碼變更本身（→ `git log`）。

新條目加在最上面，標日期。超過 400 行時把最舊的條目搬到 `docs/archive/HISTORY歸檔-YYYYMMDD.md`，並在下方留一行索引。

---

## 2026-09-08 監控的課程查詢改走 `tr_rooms.fetch_query_courses_filtered`

`tr_rooms` 加 `session`／`timeout` 參數並抽出共用 `QUERY_COURSE_HEADERS`（含學校 API 要求的 Origin/Referer）；`api_client.search_courses` 改為薄包裝，只保留延遲指標、失敗旗標與「網路中斷重新拋出」語意，刪掉 140 行 socket.gaierror 修補與重複的例外分支。監控查詢預設含跨校課程（與原行為一致），逾時仍為 10 秒。真實 API 煙霧測試：TCG100301 書法藝術 50/50，260ms。

## 2026-09-08 淘汰 worker 專用的 `ENCRYPTION_KEY`

執行（12:54）：`--apply` 更新 3 列；部署後 worker 以新密鑰解開 resend key，兩位使用者預先登入成功；本機與 Windows `.env` 已刪 `ENCRYPTION_KEY`。舊 worker 在重啟前 4 秒內看到新密文而報「解密失敗」略過該使用者，屬預期的切換空窗。

查證：`ENCRYPTION_KEY` 除了 legacy 的 `user_settings.student_password`，也加密 `smtp_password`／`resend_api_key`（正式庫 1 位使用者有 resend key），所以不能只刪讀取路徑。決策：這兩個欄位改用後端既有的 `SCHOOL_CREDENTIALS_ENCRYPTION_SECRET`（同一把 Fernet，由 `backend/credentials._fernet` 推導），整個後端只剩一把密鑰；校務密碼唯一來源為 `app_private.school_credentials`，三位使用者都已有。搬移用一次性腳本 `scripts/monitor/retire_encryption_key.py`（dry run 預設，拒絕清除沒有 app_private 帳密的列）。`rotate_encryption_key.py`、`migrate_monitor_credentials.py` 任務完成，移除。

## 2026-09-08 12:45 iOS 已驗證：改 plist 後由 xcodebuild + devicectl 裝機，登入、課表／Moodle 讀取與同步都經 tailnet 進到後端

後端 log 看到 tailnet IP 的 `/api/schedule`、`/api/moodle/assignments`、`POST /api/schedule/sync`（先 400 後 200）。iOS 對新 Supabase 專案與 https 路徑至此都確認。

## 2026-09-08 iOS 登入「hostname could not be found」：Info.plist 仍指舊 Supabase 專案

合併時只改了 Web 與後端的 Supabase 設定，iOS `Info.plist` 的 `SupabaseURL`／`SupabaseAnonKey` 漏改，仍是已刪除的 `qpdvtsbqdpitreslazoe`。已改為 `eerlhmvwucnlbhemhvtz` 與其 publishable key；需重新建置安裝才生效。

## 2026-09-08 盤點 Windows 部署方式並把 deploy_windows.sh 補到報價系統同等護欄

盤點：部署到 Windows 的有 4 個專案（course_planner → winhome；報價系統、工務管控、寄信系統 → dkfire），骨架都是「Mac ssh 叫 Windows git pull」，差別在護欄。報價系統最完整（乾淨樹、測試、腳本內 push、比對 HEAD、只在 .py 變動時重啟、煙霧測試），工務管控是其子集，本專案原本只有煙霧測試，寄信系統是手動清單（一次性、幾乎不改，不寫腳本）。決策：不統一 nssm／工作排程器與 dist 交付方式，只統一護欄；規則寫進 `~/AI協作/專案文件模板/AGENTS.md`「Windows 部署」。本專案腳本改為依 diff 決定 build web、重啟後端、重啟 worker，且只殺該任務自己的 python（原本一刀殺掉所有 course-compass python，是先前 worker 被殺卻不重啟的根源）。

## 2026-09-08 只有開自動加選才登入 SSO；冷卻改遞增；B11430227 自動加選已關

查證：B11430227 三門課都開了自動加選，worker 每輪 `check_all_courses` 前的 session 保活只要 `is_logged_in` 為 False 就預先登入，所以即使 SSO 回 500 也每 15 分鐘再打 3 次，不會停。查名額走公開 querycourse API 不需登入，預先登入只為加選準備。
做法：`_keep_session_alive_locked` 在該使用者沒有任何課程開自動加選時直接略過（開啟後加選路徑本來就會登入）；`EnrollmentClient` 冷卻改 15 → 30 → 60 分鐘遞增，登入成功重置。依使用者指示，用 service key 把 B11430227 的三門課 `auto_enroll` 改為 false（他本人可隨時在監控頁再開）。

## 2026-09-08 token 驗證加 60 秒快取；worker 缺 service role key 改為直接失敗

`resolve_user_id` 以 token 的 SHA-256 為鍵快取成功結果 60 秒，且不超過 JWT `exp`；失敗不快取，上限 2000 筆。撤銷的 token 最多多活 60 秒，可接受（Supabase 本身 access token 也是一小時）。worker 啟動改讀 `backend/config.py` 的 `SUPABASE_URL`／`SUPABASE_SERVICE_ROLE_KEY`，缺服務金鑰直接退出：以前退回 anon key 會讓 `app_private` 讀取與 session 寫入靜默失敗。

## 2026-09-08 10:12 部署登入流程合一等六個 commit

migration `20260908170000` 已套用；Vercel、Windows 後端與 worker 都在 `93c0f49`。worker 重啟後三個帳號的預先登入：B11430207 成功、B11410144 成功（此帳號在舊流程下整天回 500）、B11430227 仍回 SSO 500。

## 2026-09-08 移除 `backend/supabase_schema.sql`

程式與測試都沒有引用；內容與 migration 不一致（保留已淘汰的 `public.school_credentials`、沒有 monitor 三張表與今天新增的欄位）。否決「改寫成與 migration 同步」：同一事實只維護一處，schema 以 `supabase/migrations/` 為準。

## 2026-09-08 登入流程合一：查出 Phase 2 失敗的真正原因是進入點，不是 POST

查證方式：匿名抓 SSO 登入頁，離線讓兩套解析器各自組 POST（URL、欄位完全相同，都是 POST 到 `https://ssoam2.ntust.edu.tw/`）；再用使用者授權的帳號 B11430207 各實登一次並記錄每一跳。結果：
- 共用流程以 `/First/A06/A06` 進入，登入回來被導回 A06，但選課系統只在 `/Account/OpenIDCallback → /Home/Index` 這條路才建立 `ASP.NET_SessionId`；A06 看不到 session 就轉 `/Account/Logout`，連 SSO session 一起登出，之後再取目標頁自然回到登入頁（即「登入後無法進入目標頁面」）。monitor 從根目錄 `/` 進入所以沒事。
- 第二個 bug：`requires_hidden_form_callback` 用「URL 含 signin-oidc」判斷，登入頁的 ReturnUrl 就含這字串，導致把空白登入表單再 POST 一次。改看 URL path。
- 兩個帳號的 500 是 SSO 端對該帳號回錯誤頁（POST 後 302 到根目錄回 500），與流程無關，至今仍是。
- 附帶：登入頁固定內含隱藏的 CAPTCHA 容器、`v-show` 的 Caps Lock 提示與 180 天改密碼公告，兩套流程的錯誤判讀都會誤報；已改為只看實際顯示的元素。

做法：`login_to_target` 加 `entry_url`（monitor 傳站台根目錄；Moodle、成績頁呼叫端不變），`EnrollmentClient._login_once` 改呼叫它並保留速率限制、冷卻與網路錯誤訊息；刪掉 monitor 自己的 OIDC 回呼提交。實登結果 10 跳、2.7 秒成功，經 OpenIDCallback 建立 session。留下 `tests/fixtures/sso/login_page.html`（token 與 sitekey 已去除）做回歸。

## 2026-09-08 收掉 2026-09-06 審查的四項安全問題；順便查出待處理課程解析一直失敗

- `api_client` 不再把整個 proxies dict（含代理密碼）寫進日誌，改用只含主機的 `get_proxy_info_for_logging`。
- `worker.resolve_pending_courses` 原本 `from src.api_client import ...`（舊 repo 路徑，合併後不存在），整段一直丟 ImportError 被 except 吃掉，新課程只靠使用者迴圈的 `check_course` 補上狀態。改為套件內 import，並依各使用者 `verify_ssl` 設定建 client，不再寫死關閉 TLS 驗證。
- 測試信收件人改由 `auth.admin.get_user_by_id` 取得，前端寫入的 `email_test_requests.email` 只用來滿足 NOT NULL，worker 不再讀它。
- `.gitignore` 補根目錄 `/debug_responses/`、`/config/`（用根目錄限定，避免誤忽略其他 `config` 子目錄）。

## 2026-09-08 自動登入冷卻狀態持久化並顯示在儀表板

做法：`EnrollmentClient` 冷卻觸發／解除時呼叫 `on_login_pause` 回呼，worker 把到期時間與最後錯誤寫進 `user_settings.login_paused_until/login_pause_reason` 並寫一筆 `warn` 日誌；worker 重啟時從同欄位還原冷卻（否則重啟等於清零，帳號鎖定保護失效）。儀表板在到期前顯示黃色橫幅，導引使用者先用瀏覽器登入選課系統確認。否決把狀態只寫進 `system_logs`：前端要從日誌反推「目前是否暫停」不可靠，也無法在重啟後還原。

## 2026-09-08 加選嘗試次數改存資料庫；查出正式庫缺 `max_attempts`／`reset_attempts` 欄位

查證：以 service key 讀 `monitored_courses` 一列，正式庫只有 baseline migration 的 10 個欄位，沒有前端與 worker 都在用的 `max_attempts`、`reset_attempts`（兩者從未進 migration）。前端「課程設定」存檔與「重設次數」因此一直回 PostgREST 欄位不存在錯誤；worker 用 `.get` 預設值所以沒察覺。
決策：新增 migration `20260908150000_monitored_courses_attempt_count.sql` 建 `max_attempts`（預設 3）與 `attempt_count`（預設 0），不建 `reset_attempts`：前端重設直接把 `attempt_count` 寫 0。worker 每次讀設定時以資料庫值校正記憶體：資料庫為 0 就歸零並清除「已達上限」通知節流，否則取較大值（避免加選執行緒剛寫入、讀設定時讀到舊值而多試一次）；每次實際送出加選後同步寫回 `attempt_count`。

## 2026-09-08 名稱統一與清理

Supabase 專案改名 `course-compass`（ref 不變）；Vercel 專案 `ntust-course-monitor` 刪除（使用者自行告知同學新網址，先前做的 307 轉址隨之失效）；GitHub `NTUST_Course_Monitor` 封存；Windows 上 `NTUST_Course_Monitor` 排程工作解除登記、checkout 移到 `_retired\`。本機 `course_planner` 資料夾與 `~/.venvs/course_planner` 刻意不改名（要連動腳本與設定，收益只有好看）。

## 2026-09-08 Phase 3–4：監控前端併入 Web、Web 回 Vercel、Railway 全數刪除

`web/src/features/monitor/` 為 NTUST_Course_Monitor 前端的移植（儀表板、課程管理、監控設定＋代理），Navbar 新增「選課監控」；監控設定頁不再有學號密碼欄位，帳密只在「設定 → 校務帳密」（`app_private`）。Vercel 新專案 `course-compass` 連 GitHub、root `web/`、環境變數只有 `VITE_SUPABASE_URL`、`VITE_SUPABASE_ANON_KEY`、`VITE_BACKEND_URL`。建立時發現 `course-compass.vercel.app` 已被別的 Vercel 使用者佔用（curl 到的是他們的登入頁），改申請 `ntust-course-compass.vercel.app` 為正式網域；CORS 與 Supabase Auth 的 site_url／redirect 白名單（原本是 localhost:3000）都指到這個網域。用內建瀏覽器以略過登入模式確認正式站的「選課監控」頁可開。Railway 兩個專案由使用者刪除，repo 內 Railway 檔案移除。子代理移植時把 `catch (e: any)` 改成型別安全寫法並補了 `MonitorSettingsPayload` 型別，原本 SettingsView 的 `delete`／`is_encrypted` TypeScript 錯誤因此消失。

## 2026-09-08 Phase 2 結果：session 共用與帳密集中成功，登入流程合一失敗已回退

成功：worker 登入後把 cookie 寫進 `app_private.school_sessions`（官方初選 API 可直接復用，不必再登入）；監控 worker 改以 `app_private.school_credentials` 為帳密來源，兩位使用者的 `user_settings` 密文已用 `scripts/monitor/migrate_monitor_credentials.py` 搬入（比對過與 legacy 解密結果一致）；`monitor/crypto.py` 改 fail-closed。失敗：把 `EnrollmentClient.login` 改為呼叫 `ntust_common.login_to_target` 後，正式環境三個帳號都登不進（一個「登入後無法進入目標頁面」、兩個 SSO 回 500），持續約 45 分鐘每 20 秒重試；回退到 monitor 原本的登入流程後第一個帳號立即成功，另兩個仍停在 SSO 登入頁，研判是被連續失敗觸發學校端鎖定或節流。因此新增「連續 3 次登入失敗暫停 15 分鐘」保護。附帶發現 `backend/config.py` 在 import 時讀環境變數，worker 必須在 import `credentials`／`school_sessions` 之前 `load_dotenv`，否則 app_private 讀取與 session 寫入在 Windows 上靜默失敗。兩套登入流程差異尚未釐清，`ntust_common` 這次的強化（CAPTCHA 偵測、回呼表單挑選、SSO 首頁視為可回復）保留給 Compass 既有呼叫端。

## 2026-09-08 監控 worker 搬入本 repo（Phase 1）；查出 Railway 上仍有一個舊 worker 在跑

`backend/monitor/` 為原 NTUST_Course_Monitor 的 `backend/src` + `worker.py`，改為套件相對匯入，以 `python -m backend.monitor.worker` 執行；Windows 新排程工作 `Course_Compass_Monitor`，舊的 `NTUST_Course_Monitor` 已停用。切換後心跳變成每分鐘兩筆，追查 Windows、Mac、公司 PC 都只有一個 worker，最後用 Supabase API 日誌看到寫入來源有兩個 IP：家裡的 49.159.x 與 Railway 的 152.55.x。Railway 專案 `giving-light` 有一個 `worker` 服務連著 NTUST_Course_Monitor repo，每次 push 就自動重新部署（今天 23:17、23:21、23:48 各一次），用的是共用 Supabase 專案的金鑰但 `ENCRYPTION_KEY` 是換鑰前的舊值，所以它查得到課程、寫得了心跳，卻解不開學生密碼、無法登入加選，未造成重複加選。已 `railway down`；服務仍在，下次 push 會再部署，需刪除。9-06 判定「Railway 額度用盡」是錯的：當時 `railway list` 就列了 giving-light，被忽略。順手修正：學校 API 的 `OnleyNTUST` 拼法（原 `OnlyNTUST` 被忽略，跨校課程會混入）、日誌與設定路徑改錨定 repo 根目錄、學期回退預設改由日期推算、移除已不存在的 `frontend/.env` 讀取。

## 2026-09-07 Supabase 專案與 NTUST_Course_Monitor 合一（合併計畫 Phase 0）

決策：資料庫沿用 Monitor 的專案 `eerlhmvwucnlbhemhvtz`（ACTIVE），否決沿用 Compass 免費專案（閒置一週暫停，24 小時 worker 撐不住）與 Windows 本地自架（運維與單點風險過高，見 `docs/archive/2026-09-monitor-merge-plan.md` §1a）。做法：以 catalog 反推的 `20260907120000_compass_core.sql` 一次建立 `user_data`、三張快照表、`app_private.*`、RPC 與 grants；舊專案 15 個增量 migration 不重放，搬到 `docs/archive/supabase-migrations-old-project/`，三個測試改讀該路徑。Monitor 的三個 migration 複製進本 repo，CLI 改連新專案並 repair 歷史。資料：5 筆 `user_data` 依 email 對照 UUID 搬入（2 人兩邊都有，3 人由 admin API 新建帳號並設臨時密碼）；快照以學號為鍵原樣搬；`school_credentials` 1 筆密文沿用同一把 `SCHOOL_CREDENTIALS_ENCRYPTION_SECRET`；`school_sessions` 不搬。未用到的 typed planner 表（`planner_profiles` 等，來自未合併分支）與 legacy `public.school_credentials` 不搬。

## 2026-09-07 課程查詢預設不含台大／師大跨校課，另加勾選

學校查詢頁預設包含跨校課（課碼 3N、3T），App 原本用 `OnleyNTUST=1` 排除。決定加「含台大／師大跨校課」勾選、預設不勾，兼顧結果乾淨與對照學校頁面。查「經濟」：不勾 12 筆，勾選 46 筆（34 筆跨校）。否決「一律包含」：跨校課多數不可選，會稀釋結果。

## 2026-09-07 以整支前端取代方式移植 `codex/project-refactor`

該分支 99 個 commit 從未合併，main 自 6 月 13 日起凍結。決定不整支合併（後端目錄重整與 typed planner 資料庫風險高、未收尾），改為：把分支的 `web/` 整個搬到 main，再把當天在 main 做的修正逐一疊回；後端只移植官方選課拒絕原因解析、GPA 查詢、課碼正規化與對應測試。分支的課表卡片 20 個微調（多數互相 revert）略過。

## 2026-09-06 查詢結果比學校少：主校區過濾

後端向學校 API 帶 `CampusNotes=Main_Campus`，把華夏校區班次（如 BA305A001/2 統計學）濾掉。已移除該條件，與學校頁面一致。

## 2026-09-06 學校課程 API 晚間需 60 秒以上

整學期未過濾課程清單約 2 MB，晚間實測 62 到 68 秒（TLS 驗證開關無差異）。原 30 秒 timeout 造成空教室功能 502，已把該次請求 timeout 放寬到 150 秒；其他請求維持 30 秒。

## 2026-09-06 後端授權補強（原本所有校務 API 皆可匿名呼叫）

盤點發現：官方選課 API 對驗證失敗採「忽略」；快照 GET 完全無驗證；同步 POST 只驗校務帳密。已改為所有校務資料 API 必須帶有效 Supabase token，已綁定校務帳號者只能操作該帳號，官方選課 session 快取以「雲端使用者＋學號」為 key。CORS 改白名單，TLS 驗證改由後端決定並預設開啟。理由：後端雖在 tailnet 內，但 tailnet 含其他帳號的機器，且未來可能對外。

## 2026-09-06 部署搬到家用 Windows，關閉 Railway 與 Vercel

Supabase 因閒置被暫停（已 Restore）；Railway 部署狀態 Failed 且免費方案在新加坡尖峰時段（08:00–20:00）拒絕部署；Vercel 站台未設後端網址、bundle 是遠古版本。決定比照 `NTUST_Course_Monitor`，後端與 Web 一起常駐在家用 Windows（工作排程器＋`tailscale serve` HTTPS），Railway 部署與 Vercel 專案刪除。否決 Tailscale Funnel 公開：後端持有校務帳密，沒有必要暴露到公網；否決 Web 用 http 的 Tailscale IP：https 頁面呼叫 http 會被 mixed content 擋下。

## 2026-09-06 Windows 部署踩坑紀錄

- venv 缺 `tzdata`，`ZoneInfo("Asia/Taipei")` 啟動即失敗。
- 透過 ssh 執行 PowerShell 時 `$_` 逃逸不可靠，改用 `Where-Object Path -like` 比較語法。
- Chrome 開啟安全 DNS（DoH）時解析不到 `*.ts.net`，需關閉或改用系統 DNS。
- Mac 上 Python 3.14 對學校憑證驗證失敗（Missing Subject Key Identifier），Windows Python 3.12 正常；本機探測時才需 `verify=False`。

## 2026-09-06 Web 課表格子錯位的原因

官方課表格子在該格為空時退回「第幾欄」取值，但 `schedule_rows` 經 Supabase JSONB 儲存後鍵順序被重排，導致星期二顯示星期三的課。已改為資料列有星期鍵時不做位置退回。另外工作台格子只在官方初選同步時更新，已改為一般課表同步也重建。

## 2026-09-06 myNTUST GPA API 在 main 沒有紀錄

查證：main 與線上都沒有任何 myNTUST 呼叫；相關實作只存在 `codex/project-refactor` 的 `b3915e7`。後於 09-07 隨分支移植回 main。
