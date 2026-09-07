# NTUST_Course_Monitor 併入 Course Compass 計畫（草案，待裁示）

日期：2026-09-07。狀態：已裁示 1a=A、1b=由 admin 建帳號、Web 回 Vercel；**Phase 0 已完成**（2026-09-07），Phase 1 以後待加退選結束。

## 0. 目標與不做的事

目標：一個 repo、一個後端、一個資料庫、一套 SSO 程式碼。Monitor 的「名額監控 + 自動加選」變成 Compass 後端裡的背景服務，前端併入 Compass Web，iOS 只讀狀態。

不做：不重寫監控引擎的判定邏輯（`monitor.py` 這兩天才在真實加退選驗證過）；不在這學期加退選期間動 Phase 2 以後；不保留兩份 SSO 登入流程。

## 1. 需要裁示的決策

### 1a. 資料庫放哪：雲端 Supabase 還是本地？

| 方案 | 優點 | 代價 | 適合嗎 |
|---|---|---|---|
| **A. 沿用 Monitor 的 Supabase 專案**（`eerlhmvwucnlbhemhvtz`，ACTIVE） | 不用搬資料庫；Auth、Realtime、RLS 現成；Vercel 前端與 iOS 都能直連；Windows 掛了資料還在 | 免費方案上限（500 MB、閒置暫停）；worker 高頻寫入曾遇 HTTP/2 斷線（已加重試） | **建議** |
| B. 沿用 Compass 的 Supabase 專案（`qpdvtsbqdpitreslazoe`） | Compass 的 `app_private` 與 RPC 已在這裡 | 免費方案閒置一週會暫停，對 24 小時 worker 是硬傷；Monitor 三張表要搬 | 不建議，除非升付費 |
| C. Windows 本地跑 Supabase（Docker self-host） | 無配額、無暫停、資料在自己手上 | 需 Docker Desktop + 約 8 個容器（Postgres、GoTrue、PostgREST、Realtime、Kong、Studio…），記憶體 3–4 GB；Auth 郵件要自己接 SMTP；iOS 與 Web 只能在 tailnet 內用；Windows 更新重開時整套服務都斷；備份要自己做 | 可行但運維成本最高 |
| D. Windows 本地只跑 PostgreSQL，Auth 改由 FastAPI 自己做 | 最輕量 | 要自己寫登入、密碼重設、token；Realtime 要改 SSE/WebSocket；等於重做一半的 Compass | 不建議 |

建議 **A**：資料庫留雲端，運算留本地。理由是這台 Windows 已經同時扛 worker、FastAPI、tailscale serve，再加一套 Supabase 會讓「Windows 出事 = 全部出事」，而現在 Windows 掛掉至少 Web 與資料還能看。若之後真的碰到配額，再評估 C，屆時 schema 都在 migration 裡，搬過去是機械工作。

若選 A，Compass 的 `app_private.*`、`user_data`、`*_snapshots` 與 migration 要搬到 Monitor 的專案；Compass 的 auth.users 也要在新專案重建（人少，重新註冊即可）。

### 1b. 帳號對應

三位使用者在兩個專案的 `auth.users` UUID 不同。人數少，建議：合併後請每人在保留的專案重新登入一次，我用一張對照表（舊 UUID → 新 UUID）把 `monitored_courses`、`user_settings`、`user_data` 的 `user_id` 改過去。對照表由你提供（每人用哪個 email）。

### 1c. 合併時間

建議 Phase 0–1 現在做（不影響現行 worker），Phase 2 以後等這學期加退選結束。

## 2. 目標結構（course-compass repo）

```
backend/
  app.py                      FastAPI 入口（既有）
  monitor/                    ← 從 Monitor 的 backend/src 搬入
    engine.py                 原 monitor.py（判定、加選派工、失敗節流）
    api_client.py             課程查詢 API（學期回退規則）
    semester.py
    worker.py                 原 worker.py 的 manager／每使用者執行緒，改為可被 app 啟動的服務
  ntust_common.py             共用 SSO 登入（以 Monitor 的 enrollment.login 為基礎，見 §4）
  official_selection.py       既有；改為呼叫共用 SSO
  credentials.py              既有；Monitor 的學生密碼改存 app_private.school_credentials
scripts/deployment/
  run_backend.bat             既有；同一 process 起 worker（或另加 run_worker.bat，見 §5）
supabase/migrations/          Monitor 的 baseline + retention + grants 併入
web/src/features/monitor/     儀表板、監聽列表、日誌（原 DashboardView / CoursesView）
tests/backend/                Monitor 的學期回退測試併入
```

Monitor repo 最後只留 README 指向 Compass，並在 GitHub 設為 archived。

## 3. 資料模型對應

| Monitor | Compass 目標 | 說明 |
|---|---|---|
| `user_settings.student_id / student_password / is_encrypted` | `app_private.school_credentials` | 走既有 RPC；worker 用 service role 讀密文、後端 Fernet 解密。Monitor 的 `ENCRYPTION_KEY` 退役，改用 `SCHOOL_CREDENTIALS_ENCRYPTION_SECRET`；需寫一次性腳本用舊金鑰解、新機制存 |
| `user_settings` 其餘（檢查間隔、開放時段、代理、Email 通知） | 新表 `public.monitor_settings`（user_id PK） | 保留原欄位，RLS 同 Monitor |
| `monitored_courses` | 原樣保留 | 加 `attempt_count` 欄位（TODO P0 項，順便做） |
| `system_logs` | 原樣保留，retention cron 一併搬 | 前端 Realtime 訂閱不變 |
| `email_test_requests` | 原樣保留或改成 API | 若改 API 可刪表 |

## 4. SSO 與 session 的單一持有者

現況：Monitor 每位使用者一個長期 `requests.Session`，高頻查詢 + 保活；Compass 官方初選在使用者按下時用 `app_private.school_sessions` 的 cookie 復原 session。兩者若各自登入會互踢。

規則：**worker 是 session 的唯一持有者**。
- 登入流程統一用 Monitor 的 `enrollment.login`（含 2026-09-07 的入口網／SSO 首頁回復），搬到 `ntust_common.py`。
- worker 登入成功後把 cookie 加密寫入 `app_private.school_sessions`；官方初選 API 只讀這份 session 執行操作，不自己登入。session 失效時官方初選回「請稍候」，由 worker 重登。
- 同一使用者的登入與加選共用一把鎖（Monitor 已有 `_enroll_locks`）。
- 學校限制寫進 AGENTS：密碼錯 10 次鎖 15 分鐘；登入／加選速率限制常數只留一份。

## 5. 執行階段

每個 Phase 結束都有可驗證的 gate；Phase 0–1 期間 Monitor 現行 worker 照跑。

### Phase 0：決策與準備（半天）
- 裁示 §1 三項。
- Compass 若選方案 A：把 Compass 的 migration 套到 Monitor 專案（`supabase link` 換 ref、`db push`），Compass 前後端改指新專案，三人重新註冊。
- Gate：Compass Web 與 iOS 在新專案能登入、同步、看到自己的規劃。

### Phase 1：後端搬入，worker 在 Compass repo 跑起來（1–2 天）
- 複製 `backend/src` → `backend/monitor/`，只改 import 與設定讀取；`worker.py` 改為 `backend/monitor/worker.py`，可獨立執行也可由 `app.py` 啟動。
- 帳密改讀 `app_private.school_credentials`；一次性遷移腳本把 Monitor 三位使用者的密文轉存。
- `monitor_settings` migration；`monitored_courses.attempt_count`。
- Windows 上先用第二個排程工作 `Course_Compass_Monitor` 跑新 worker，**舊 worker 停掉**（兩個 worker 同時跑會重複加選）。
- Gate：新 worker 心跳寫入、三人課程正常查詢、`pytest tests/backend` 全過、一次真實登入成功且 `school_sessions` 有寫入。

### Phase 2：SSO 合一（1 天）
- `official_selection.py` 改用共用登入與 worker 持有的 session；刪除重複的登入程式碼。
- Gate：官方初選頁能列出課表（讀 session）；worker 重登後官方初選仍可用；`backend:test` 全過。

### Phase 3：前端併入（1–2 天）
- `DashboardView`、`CoursesView` 監聽部分、`SettingsView` 監控設定搬到 `web/src/features/monitor/`，接 Compass 的 Navbar 與 Auth；「加入監聽」按鈕放進課程搜尋結果列。
- Realtime 訂閱與心跳常數（`workerStatus.ts`）照搬。
- Gate：`web:lint`、`web:build`、`tsc` 通過；瀏覽器實際操作新增監聽、暫停、刪除、看日誌。

### Phase 4：收尾（半天）
- Vercel 的 Monitor 站下線；Monitor repo README 改指向並 archive。
- Monitor 的 `ENCRYPTION_KEY` 作廢；`.env` 只留 Compass 的變數。
- AGENTS／README／HISTORY／TODO 合併，Monitor 的 HISTORY 併入 Compass `docs/archive/`。
- iOS：新增監聽狀態頁（可延後）。

## 6. 風險與對策

- **重複加選**：Phase 1 切換時舊 worker 必須先停；切換期間監控中斷約 1 分鐘，選非加退選時段做。
- **Supabase 配額**：worker 寫入量已在 2026-07 減量，system_logs 有 7 天 retention；合併後多了 Compass 的快照表，估計仍遠低於 500 MB。
- **單點故障**：Windows 掛掉 = worker 與 Compass 後端都停，但雲端資料與 Web 仍可讀（若 Web 仍由 FastAPI 提供則不可讀；可考慮 Web 回到 Vercel 只留後端在 Windows，這是另一個可裁示點）。
- **回退**：Phase 1–2 任一 gate 失敗，重啟舊 worker 排程即可回到現狀；資料表只增不改，不影響舊 worker。

## 7. 你需要回覆的

1. 資料庫方案：A（建議）／B／C。
2. 三位使用者的 email 對照，或同意「合併後各自重新註冊」。
3. Phase 2 以後的時間點（建議加退選結束後）。
4. Web 是否留在 Windows 由 FastAPI 提供，或回 Vercel。
