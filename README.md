# Course Compass 修課羅盤 Workspace

這個 repo 明確分成兩條產品線與共享支援區：

- `web/`：React + Vite 的課程與學分規劃 Web 版
- `ios/`：SwiftUI 原生 iPhone App
- `backend/`：Python 同步服務
- `supabase/`：migration 與資料庫結構
- `docs/`：現行 architecture/data contract、設計 QA 與歷史歸檔
- `tests/`：測試與可重跑 fixture

`backend/`、`supabase/`、`docs/`、`tests/` 都維持在根目錄，方便兩端共用。根目錄只放 workspace 總控設定與跨端文件，不放 build output 或臨時截圖。

## 目錄角色

### Web

- 專注在大螢幕操作最有價值的流程
- 提供課程查詢、選課工作台、HTML 匯入、學分門檻設定、課程細節與成績試算
- 透過 backend 執行校務同步與使用者確認式官方選課操作
- 使用雲端帳號保存 `public.user_data`

詳細說明在 [web/README.md](web/README.md)。

### iOS

- 原生 SwiftUI App
- 提供首頁摘要、每週課表、手機版學分規劃與設定
- 額外串接同步服務，從校務系統抓課表與歷史修課紀錄

詳細說明在 [ios/README.md](ios/README.md)。

### Backend

- `FastAPI` 提供課表同步與歷史修課匯入 API
- 以校務帳密登入校務系統抓資料
- 將同步結果寫入 `schedule_sync_snapshots` 與 `history_import_snapshots`
- 使用已保存校務帳密恢復 session，並執行使用者確認式官方初選操作
- 入口仍是 `backend/app.py`；SSO/課表、Moodle、TR 空教室、Supabase snapshot 存取已拆成 backend 內部模組

### Supabase

- Web 與 iOS 共用同一個 Supabase 專案
- 學分規劃存於 `public.user_data`
- iOS 額外的同步快照由後端寫入
- Web/backend 的校務帳密保存改由 `app_private.school_credentials` 保存加密密文，並只透過 service-role-only RPC 存取
- 官方選課 session cookie/state 由後端加密保存到 `app_private.school_sessions`，透過 service-role-only RPC 存取
- `user_data.content.settings` 目前使用的欄位鍵：
  - `school_account`
  - `reminder_minutes`
  - `school_password` 已由 migration 清除；Web/iOS 新寫入不應再使用

### Test Artifacts

- `tests/fixtures/course_selection/`：課表與選課頁樣本
- `tests/fixtures/edu_need_history/`：歷史修課紀錄頁樣本
- `tests/fixtures/moodle_timeline/`：Moodle 時間軸與待繳事項樣本

### Docs

- `docs/architecture/refactor-plan.md`：目前有效的全專案重構計畫、執行順序與驗證 gate
- `docs/data-contracts/database-schema.md`：current production schema 與 planned typed schema 的資料責任邊界
- `docs/design/`：設計 QA 記錄
- `docs/archive/2026-refactor/`：歷史產品定義、UX audit 與 reference images

## 開發指令

### 根目錄總控

```bash
npm run web:dev
npm run dev:all
npm run web:build
npm run web:lint
npm run ios:open
npm run ios:build
npm run backend:dev
npm run backend:check
npm run check
```

`npm run dev:all` 會優先使用 repo `.venv/bin/python`，若不存在則使用 `/Users/hezhen/.venvs/course_planner/bin/python` 啟動 backend。

### Web 安裝

```bash
cd web
npm install
```

Web 會從 repo 根目錄讀取 `.env`，不需要另外複製一份到 `web/`。

### Backend 安裝

```bash
python3 -m venv .venv
.venv/bin/pip install -r backend/requirements-dev.txt
cp .env.example .env
```

需要的環境變數：

```bash
VITE_SUPABASE_URL=...
VITE_SUPABASE_ANON_KEY=...
SUPABASE_URL=...
SUPABASE_SERVICE_ROLE_KEY=...
SCHOOL_CREDENTIALS_ENCRYPTION_SECRET=... # 建議使用 openssl rand -hex 32 產生
NTUST_VERIFY_SSL=true
```

說明：

- `VITE_SUPABASE_*` 給 Web 前端使用
- `SUPABASE_SERVICE_ROLE_KEY` 只給 Python 後端使用
- iOS 不應直接持有 `service_role`
- 後端使用 Supabase Auth `/auth/v1/user` 驗證 Web/iOS 傳入的 access token，不以本地 JWT payload decode 當作身份驗證
- `SCHOOL_CREDENTIALS_ENCRYPTION_SECRET` 只給 Python 後端使用，用於加解密 `app_private.school_credentials.password_ciphertext`；不可使用 `.env.example` placeholder，長度需至少 32 字元
- Web 不會讀取或保存校務密碼明文；官方選課 session 會由後端加密保存，過期或失效時由後端使用已保存密文重新登入
- iOS 不再把校務密碼寫入 `user_data.content.settings.school_password`；production legacy plaintext 已由 `20260613031804_remove_legacy_school_password_from_user_data.sql` 清除，使用者下次輸入密碼並勾選保存後會寫入 `app_private.school_credentials`

資料表與快照 schema 在 [backend/supabase_schema.sql](backend/supabase_schema.sql)，migration 在 [supabase/migrations](supabase/migrations)。

## API

- `GET /api/school-credentials`：讀取校務帳密保存狀態，不回傳密碼
- `PUT /api/school-credentials`：由後端加密保存校務帳密
- `DELETE /api/school-credentials`：清除已保存校務帳密
- `POST /api/schedule/sync`：同步校務課表並保存快照；可用 request password，或使用已保存帳密
- `GET /api/schedule/{profile_key}`：讀取最新課表快照
- `POST /api/history/import`：匯入歷史修課紀錄並保存快照；可用 request password，或使用已保存帳密
- `GET /api/courses/search`：查詢官方開課資料；可帶 `X-GPA-API-Key`（myNTUST API token）在結果附上 GPA
- `GET /api/tr-rooms/status`：查詢目前或下一節 TR 教室使用狀態
- `POST /api/moodle/assignments/sync`：同步 Moodle 待繳事項快照；可用 request password，或使用已保存帳密
- `POST /api/official-selection/a02/*`：使用者明確確認後送出官方初選操作；mutating request 需帶 `confirmed: true`，後端會重用已保存官方 session 或用已保存帳密重新登入，但不做自動搶課、輪詢或排程送出

授權規則（2026-09-06 起）：

- 除 `/health`、`/api/courses/*`、`/api/tr-rooms/*`、`/api/planner/*` 外，所有校務資料 API 都必須帶 Supabase access token（`Authorization: Bearer`），否則回 401
- 已綁定校務帳號（`app_private.school_credentials`）的使用者只能操作該帳號；`profile_key` 必須等於校務帳號，否則回 403 / 400
- 快照 `GET` 需登入且 `profile_key` 與綁定帳號相同；尚未綁定的使用者需先輸入校務帳密同步一次
- 官方選課 session 快取以「雲端使用者 + 校務帳號」為 key，不再由 caller 指定
- 對校務系統的 TLS 驗證由後端 `NTUST_VERIFY_SSL` 決定（預設開啟），request body 內的 `verify_ssl` 會被忽略
- CORS 只允許 `https://hezhen.taile9e4a0.ts.net` 與本機 Vite dev server（Vercel 部署已於 2026-09-06 刪除）

## 驗證

```bash
npm run lint
npm run build
npm audit --prefix web --audit-level=moderate
npm run backend:check
npm run ios:build
```

`npm run check` 會串起 Web lint/build、backend check 與 iOS build，適合提交前使用。

## 維護腳本

### 驗證 production backend

Web 與 backend 都部署在家用 Windows 主機（見下方「Windows 後端部署」）；Railway 與 Vercel 部署已於 2026-09-06 移除。部署後用以下指令確認 production backend 已包含校務帳密、官方 session 持久化與官方初選 API：

```bash
bash scripts/python.sh scripts/verify_production_backend.py
```

若此檢查失敗，正式站台可能已更新前端但 backend 仍是舊版，官方選課送出會無法使用。

### Windows 後端部署

backend 以 `NTUST_Course_Monitor` 相同方式常駐在家用 Windows 主機（Tailscale 節點 `hezhen` / `100.72.243.88`，SSH 別名 `winhome`）：

- 程式位於 `C:\Users\hezhe\source\repos\course-compass`，venv 在 `.venv\`，`.env` 放在 repo 根目錄
- `scripts/deployment/run_backend.bat` 複製到該 repo 根目錄，由工作排程器 `Course_Compass_Backend`（開機啟動、S4U）常駐，監聽 `0.0.0.0:8000`，log 在 `logs\backend.log`
- 課程監控 worker（原 NTUST_Course_Monitor）同樣常駐於此：`scripts/deployment/run_monitor.bat` 複製到 repo 根目錄，由工作排程器 `Course_Compass_Monitor` 執行 `python -m backend.monitor.worker`，log 在 `logs\monitor.log`（stdout）與 `logs\ntust_monitor.log`（每日輪替 7 天）。`.env` 另需 `ENCRYPTION_KEY`、`NTUST_SEMESTER`、`NTUST_ENROLLMENT_LOG_RETENTION_DAYS`（見 `.env.example`）
- venv 需額外安裝 `tzdata`，否則 `ZoneInfo("Asia/Taipei")` 會失敗
- iOS `Info.plist` 的 `BackendServiceBaseURL` 指向 `https://hezhen.taile9e4a0.ts.net`（tailscale serve 提供的 HTTPS，不需 ATS 例外）

Web 也一併由此後端提供：`web/dist` 存在時 FastAPI 會在 `/` 回傳 SPA，`/api/*` 不變。對外以 `tailscale serve` 提供 HTTPS，網址為 `https://hezhen.taile9e4a0.ts.net`，只有 tailnet 內的裝置（手機需開 Tailscale）連得到。

更新程式（建置 web、同步 checkout 與 dist、重啟排程、確認 tailscale serve）：

```bash
bash scripts/deployment/deploy_windows.sh
```

只更新後端可加 `--skip-web`。

### 遷移 legacy 校務密碼

若其他環境或舊備份的 `public.user_data.content.settings` 仍有舊的 `school_password` 或 `schoolCredentials.passwordCiphertext`，可用後端 Fernet 金鑰加密搬到 `app_private.school_credentials`，再清掉 JSON 內的舊欄位。

```bash
# 只統計，不寫 DB
bash scripts/python.sh scripts/migrate_legacy_school_credentials.py

# 確認 .env 有真實 SUPABASE_SERVICE_ROLE_KEY 與 SCHOOL_CREDENTIALS_ENCRYPTION_SECRET 後才執行
bash scripts/python.sh scripts/migrate_legacy_school_credentials.py --apply
```

腳本不會輸出密碼內容；如果 `.env` 的 service role key 還是 placeholder，會停止而不寫入。

## 維護原則

1. Web 與 iOS 不共用畫面與互動流程，只共用資料規則。
2. `backend/`、`supabase/`、`docs/`、`tests/` 維持根目錄，作為共享基礎設施、決策紀錄與可重跑 fixture。
3. 新功能優先先判斷屬於 Web 還是 iOS，再決定落點。
4. build output、暫存截圖與本機快取不進 repo；可重現的測試 fixture 才放入 `tests/fixtures/`。

## 慣例文件分工

規則邊界 → [AGENTS.md](AGENTS.md)；Claude 入口 → [CLAUDE.md](CLAUDE.md)；待辦 → [TODO.md](TODO.md)；決策查證 → [HISTORY.md](HISTORY.md)；過時文件 → `docs/archive/`。
