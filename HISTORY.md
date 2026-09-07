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
