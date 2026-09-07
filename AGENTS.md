# Course Compass 修課羅盤 — 共用協作規則

本檔供 Codex、Claude 共用，適用於本 repo（GitHub `hezhen0816/course-compass`）。
依使用者已明確的需求與授權完成工作。

- 共用規則只寫本檔；[CLAUDE.md](CLAUDE.md) 只放入口與必要工具專屬設定。
- [README.md](README.md) 查環境與操作，[TODO.md](TODO.md) 查待辦，[HISTORY.md](HISTORY.md) 查決策。
- `docs/archive/` 只讀，不是現行規則，預設不讀；`docs/architecture/refactor-plan.md` 描述的是未合併的 `codex/project-refactor` 分支計畫，同樣只作脈絡。
- 接手先讀交接（若有），再核對分支、HEAD、工作樹與相關實作。
- 一般可回復細節依證據決定；影響授權、資料、金額的缺口才詢問。
- 本機 commit、push、部署、寄信等依使用者授權，不因模板自動執行。

## 資料與環境

- 正式資料自 2026-09-07 起在與 NTUST_Course_Monitor 共用的 Supabase 專案 `NTUST_Course_Monitor_restored`（ref `eerlhmvwucnlbhemhvtz`）；舊專案 `course-compass`（`qpdvtsbqdpitreslazoe`）只保留作回退，不再寫入。schema 以 `supabase/migrations/` 為準（含 Monitor 的三張表），舊專案的歷史 migration 在 `docs/archive/supabase-migrations-old-project/` 只讀。學分規劃在 `public.user_data`，校務帳密與官方 session 密文在 `app_private.*`，同步快照在 `*_snapshots`。
- 後端、Web 與課程監控 worker（`backend/monitor/`，2026-09-08 自 NTUST_Course_Monitor 搬入）都跑在家用 Windows 主機，經 Tailscale 提供 HTTPS；網址、部署腳本與排程器名稱見 README「Windows 後端部署」。Railway 專案仍存在且會在 push 時自動部署（`course-compass-backend` 指舊 Supabase 專案、`giving-light/worker` 是舊的監控 worker，已 `railway down`），刪除前不要依賴它們；Vercel 只剩 NTUST Monitor 的舊前端。
- 監控 worker 的規則（多使用者隔離、加選判定、學期回寫方向、學校端限制）沿用 NTUST_Course_Monitor 的 AGENTS.md，併入前以該檔為準；同一時間只能有一個 worker 對同一個資料庫跑，切換時先停舊的。
- 後端只在 tailnet 內可達；同一 tailnet 內有公司帳號的 Windows 節點，因此所有校務資料 API 都必須驗 Supabase token，不可回退為選擇性驗證。
- 對學校系統的 TLS 驗證由後端環境變數決定（預設開啟），request 內的 `verify_ssl` 一律忽略。
- 本機 Python 用 `scripts/python.sh`（優先 `.venv`，否則 `~/.venvs/course_planner`）；不要用系統 `python3` 跑專案。
- iOS 需要 Xcode 27（iPhone 跑 iOS 27）；`Info.plist` 的 `BackendServiceBaseURL` 指向 tailnet HTTPS 網址，沒有備援主機。
- Web 有「略過登入」示範模式，可在沒有帳號的情況下檢視版面；示範模式不會寫入正式資料。

## 驗證

- 後端：`npm run backend:test`；改 API 授權時另用 curl 對線上 `/health` 與未帶 token 的資料端點確認 200 / 401。
- Web：`npm run web:lint`、`npm run web:build`，並用 `npx --prefix web tsc -p web/tsconfig.app.json --noEmit`。
- UI 變更：以瀏覽器實際檢視。內建瀏覽器面板可用示範模式；需要真實資料時可用使用者已登入的 Chrome，但只做查詢，不改動資料。
- iOS：`npm run ios:build`；裝機用 `xcodebuild -destination 'id=<UDID>'` 加 `devicectl install`。
- 部署後跑 `bash scripts/python.sh scripts/verify_production_backend.py`，並看 Windows 上的 `logs\backend.log`。
- 純文件只檢查差異、連結及事實。成功後不無故擴大測試；未驗證項目與原因明確回報。

## 收尾

更新受影響的待辦與決策；同一事實只維護一處。
交接只在使用者說「寫交接」時寫，固定一份覆寫，寫完回報檔案位置。
