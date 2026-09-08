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
