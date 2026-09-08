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

## 2026-09-08 前端也已併入 course-compass；Railway 已刪除

「選課監控」頁上線於 https://ntust-course-compass.vercel.app。Railway 專案由使用者刪除，本 repo 可再 push。本 repo 進入只讀狀態，待舊 Vercel 站下線後封存。

## 2026-09-08 Worker 已搬到 course-compass repo 執行；本 repo 的 push 仍會觸發 Railway 舊 worker

Windows 上改由 course-compass 的排程工作 `Course_Compass_Monitor` 跑 `backend/monitor/worker.py`（內容即本 repo 的 `backend/src` + `worker.py`），本 repo 的 `NTUST_Course_Monitor` 排程工作已停用。查出 Railway 專案 `giving-light` 有一個連著本 repo 的 `worker` 服務，每次 push 就自動部署並用共用 Supabase 金鑰跑第二份 worker（金鑰是換鑰前的舊值，登入不了，但心跳與查詢都在寫）。已 `railway down`；在刪除該 Railway 服務前，**不要 push 本 repo**，否則會再部署一份。9-06 認定 Railway 額度用盡是誤判。後續程式修改一律在 course-compass 的 `backend/monitor/` 進行，本 repo 只留歷史。

## 2026-09-07 Supabase 專案改為與 Course Compass 共用；本 repo 將併入 course-compass

Course Compass（`~/Documents/Project/GitHub/course_planner`）的資料庫已搬進本專案的 Supabase 專案 `eerlhmvwucnlbhemhvtz`，多了 `user_data`、三張快照表與 `app_private.*`，本專案的四張表與 worker 不受影響。後續依 course_planner 的 `docs/architecture/monitor-merge-plan.md`，worker 與前端會在加退選結束後搬進 course-compass repo，本 repo 最終歸檔。schema 現在由 course-compass 的 `supabase/migrations/` 維護（含本 repo 的三個 migration 副本）；在本 repo 新增 migration 前先確認兩邊同步。

## 2026-09-07 SSO 登入落在入口網或 SSO 首頁時視為可回復，不再當失敗

加退選首日 08:58–11:09 共 251 次登入失敗、14 次成功；12 次最終 URL 是 `i.ntust.edu.tw`、18 次停在 `ssoam2.ntust.edu.tw/`，三個帳號都有，排除密碼錯誤。10:38 企業投資分析空出一席，重登花 26 秒後被判失敗，錯過該席。查證：SSO 登入頁表單 action 是 SSO 根路徑，帶 `ReturnUrl`；尖峰時 SSO 會丟掉 ReturnUrl 把人導到入口網，但 SSO session 已建立。修法：落在非選課系統的網址就重新 GET 選課系統讓 OIDC 靜默完成；停在 SSO 根路徑且頁面沒有登入表單也走同一路徑。部署後零登入失敗，兩門課皆第一次嘗試加選成功（11:56、13:21）。

## 2026-09-07 學校 API 尖峰逾時屬正常，只節流日誌不降頻率

09:00 起學校查詢約兩成逾時、成功量減半，Mac 直連 0.12 秒正常，判定是學校伺服器壅塞。尖峰正是要盯的時段，決定不降低檢查頻率；改為每門課連續失敗（2 分鐘內視為同一段）只在開頭與每 5 分鐘寫一筆即時日誌，恢復時寫一筆含中斷時長。檔案日誌仍完整。

## 2026-09-06 Supabase 寫入偶發 HTTP/2 斷線，加重試而非換連線方式

Windows 上 worker 每分鐘約 7 次 `ConnectionTerminated / Server disconnected`，Mac 6 月日誌沒有，判定與家用網路環境有關。影響是該週期人數沒寫回，最壞是加選成功後停用旗標沒寫入導致重複送單。在 `monitored_courses` 的四個更新點加三次重試（0.3s 遞增），重啟後 5,500 行零失敗。沒改 supabase 客戶端的 HTTP 版本，因為重試已足夠且改動面小。

## 2026-09-06 Supabase schema 與 RLS 納入 repo；收掉 anon 寫入權

用 `supabase db query` 核對：四張表 RLS 皆開，policy 只給 `authenticated`、條件 `auth.uid() = user_id`；`anon` 無 policy，匿名讀三張表皆 0 筆。遠端 migration 歷史有 5 筆從後台套用、repo 沒有的紀錄，已用 `migration repair` 對齊。這台 Mac 沒有 Docker，`db pull`／`db dump` 不能用，改由 catalog 查詢產生 `20260618111348_baseline_schema.sql`（之後若裝 Docker 可用 `db diff` 核對）。新增 migration 收掉 `anon` 的寫入與 `authenticated` 的 TRUNCATE/REFERENCES/TRIGGER；worker 走 service role 不受影響。

## 2026-09-06 機密外洩處置：換金鑰、清歷史、移除協作者；密碼由使用者決定不換

安全審查發現測試腳本註解含真實 NTUST 密碼、`.env.example` 歷史版本含正式 Fernet 金鑰（與當時 `.env` 相同）。repo 私有但有兩位協作者，已移除。處置：測試腳本改只讀環境變數；`rotate_encryption_key.py` 重加密 3 位使用者 4 個欄位並同步 Windows `.env`；`git filter-repo` 把舊密碼與舊金鑰替換成 `***REMOVED***` 後 force push，備份 bundle 在 `~/Documents/Project/GitHub/_backups/`。使用者裁示不改 NTUST 密碼。附帶發現 PowerShell 5.1 `Set-Content` 會把 `.env` 存成 cp950，worker 讀不了；需用 .NET 寫無 BOM UTF-8。

## 2026-09-06 「非選課開放時間」的加選失敗不計入嘗試次數

開放前每次名額變動都會送加選並失敗，3 次後達上限，真正開放時反而不動（且次數只在記憶體，重啟歸零又打 3 次）。改為不計次並套 20 秒冷卻。嘗試次數改存資料庫的方案因需動 schema 暫緩，列在 TODO。

## 2026-09-06 人數顯示去年數字的根因是學期回退方向錯

儀表板顯示 55/45、34/45，學校頁面是 45/45、41/41。每門課存加入時的學期（1141/1142），worker 以該學期查。更深的問題：學校 API 逾時回傳空列表被當成「查無」，回退到舊學期查到資料後把舊學期寫回資料庫，之後永遠查舊學期。修法：只允許往更新的學期回退；傳輸失敗不回退；已把兩門課改為 1151。課程設定視窗因此加了學期欄位。

## 2026-09-06 儀表板「心跳年齡」改為檢查週期；學校延遲改夾在心跳裡

心跳年齡每秒跳動只表達「活著」，與標題徽章重複；改顯示學校 API 延遲、檢查週期與上次檢查時間，心跳只在超過 60 秒時才顯示警告。學校延遲原本靠獨立日誌列，7 月減量時被拿掉導致永遠空白；改夾在每 60 秒的心跳訊息裡，不增加日誌列數。前端離線門檻統一為 90 秒常數，不再隨檢查間隔放大（後端心跳固定 60 秒）。

## 2026-09-06 Worker 從 Railway 改到家中 Windows 主機

Railway 帳號下沒有本專案服務，另一專案部署全為 REMOVED，判定額度用盡；Railway 帳單 API 對 CLI token 回 Not Authorized 無法直接確認。使用者選擇用長開的 Windows（Tailscale 節點 `hezhen`，帳號 `hezhe`）。repo 私有且 Windows 無 GitHub 憑證，改用 git bundle 部署；之後更新用 scp 逐檔複製。工作排程器以 S4U 登入型態於開機執行 `run_worker.bat`（無限重啟迴圈、10 MB 輪替）。Windows 專屬修正：console cp950 需 `PYTHONUTF8=1`；無 IANA 時區庫需 `tzdata`。`railway.toml`、`Procfile`、`runtime.txt` 保留但已不使用。

## 2026-09-06 已加選課程不再輪詢，是刻意設計

`status` 為 `enrolled` 或 `paused` 的課程在 `fetch_config` 就被跳過，人數與最後檢查時間停在加選成功那一刻。要繼續看人數需刪除重加或暫停再恢復。
