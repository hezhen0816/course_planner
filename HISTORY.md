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

## 2026-09-09 監控設定併入「設定」頁；選課監控只剩「現在在監聽什麼」

延續上一則的視覺對齊。監控頁原本自己帶一個「監控設定」分頁（監聽間隔、選課時段、
通知、代理），和「設定」頁的校務帳密、GPA 密鑰是同一類東西，卻分兩個地方找。

- `MonitorSettingsView` 與 `ProxyView` 改寫成設定頁那套卡片（頁首列＋圖示＋
  `text-base` 標題，儲存鈕放頁首右側），紫色點綴統一成藍色，控制項一個沒少。
- 兩張卡片由 `SettingsPage` 的 `monitorSettings` 插槽帶入，位置在 GPA 密鑰與畢業門檻之間。
  用插槽而不是在 settings 直接 import monitor：這個 repo 的 feature 之間互不相依，
  只在 `app/` 組裝，維持這個規則。
- 監控頁分頁剩「儀表板／課程管理」，分頁列右側放一個藍色的「監控設定 ↗」連到設定頁；
  原本那份「學校帳號請去設定頁」的說明整段刪掉（已經站在設定頁上了）。

跳轉的兩個坑（都在瀏覽器實測才看到）：
1. `setTimeout(..., 0)` 時 React 還沒畫出目標區塊，`getElementById` 拿到 null。
   改成短間隔重試，並讓 loading 狀態的卡片也帶同一個 `id`（它要抓完設定才會換成正式卡片）。
   重試用 `setTimeout` 不用 `requestAnimationFrame`——分頁在背景時 rAF 根本不觸發。
2. `scrollIntoView({ behavior: 'smooth' })` 同樣依賴 rAF，背景分頁不會捲；而且導覽列是
   `sticky top-0`，對齊 top 會被蓋住。改成直接 `scrollTo`，並扣掉 `[data-app-nav]` 的實測高度
   （手機 191px、桌機 56px，寫死會錯）。

驗證：375／768／1440 三種寬度掃過設定頁，無橫向溢出、短字串換行偵測回空陣列；
點「監控設定 ↗」後量到區塊上緣正好在導覽列下方 8px。

## 2026-09-09 選課監控頁併回 Compass 的視覺語言；刪掉重複的課程查詢

監控頁原本是另一個專案搬過來的，自己有一套外觀（`max-w-4xl` 窄容器、`rounded-2xl`、
歡迎語、頁內再放一個「新增課程」表單），夾在其他頁中間很突兀。這次只動樣式與入口，
不改監控行為：

- 頁首改用其他頁同一張卡片（`rounded-lg border-slate-200 bg-white p-5 shadow-sm`
  ＋ 藍色 eyebrow ＋ `text-2xl` 標題），分頁列收進卡片下緣；`text-2xl` 標題全站只留一個，
  設定分頁原本的「系統與通知設定」大標題因此移除（頁首＋分頁名已經說完了）。
- 圓角統一（`rounded-2xl`→`rounded-lg`、`rounded-xl`→`rounded-md`），移除窄容器，
  分頁間距由 `space-y-12` 收成 `space-y-4`。
- 儀表板四張圖示統計卡改成修課軌跡那套淡色摘要格（`StatCard`→`StatBox`），
  和狀態句、加課入口一起收進同一張白卡片；刪掉重複的 Worker 徽章與「歡迎回來，同學」。
- **課程管理不再自己做一份課程查詢**：原本有學期下拉＋課號輸入＋「新增課程」，
  等於第二套查詢介面，而且那裡看不到名額與 GPA。改成導到「課程查詢」，在那裡按該列
  的「監聽」加入（`addCourse`／`lookupCourseInfo`／`NTUST_API` 一併刪除）。

驗證：mobile 375／tablet 768／desktop 1265 三種寬度、三個分頁都看過，`scrollWidth`
沒有溢出，短字串換行偵測回空陣列；與 `修課軌跡`、`設定` 並排比對頁首確認同構
（`課程查詢` 沒有 eyebrow，是它自己的例外，這次不動）。

## 2026-09-08 22:36 上線後查證：10 門過期課程已停止輪詢，名額分母修正可見

13 門監控課程變成 expired 10／monitoring 2／enrolled 1，worker log 逐門列出「早於當前學期 1151，停止監控」且無錯誤。名額修正在真實資料上可見：`BA4409701 證券管理` 原本顯示 `49/9999`（Restrict1=9999 被當成無上限），現在是 `49/49`。已過期課程的 `current_enrolled` 一併清空（停止輪詢後不會再更新，留著會被當成現況）：既有 10 門用 service key 清為 null，worker 標記過期時也同步清除；監控頁人數欄補上 `—` 的預設值。

## 2026-09-09 `/api/courses/semesters` 曾把 25 個學期都標成 current

學校的 semestersinfo 對 25 個學期都給 `CurrentSemester: true`／`Static: false`，單看欄位分不出當前學期；`monitor/semester.py` 是靠「取清單第一筆有效值」。API 直接照抄該欄位，於是回傳 25 個 current，前端 `pickDefaultSemester` 取第一個才碰巧對——順序一變就會錯。改為只有 `get_default_semester()` 判定的那個標 true（實測 61 筆、current 只剩 `1151`），並補上端點測試。
另外：`from ..logging_setup import` 少了 try/except 雙路徑，正式後端以 `uvicorn app:app --app-dir backend` 啟動時 `backend/` 是頂層，相對 import 越界導致後端起不來——部署腳本的煙霧測試擋下了。`npm run backend:check` 有涵蓋這條路徑（`PYTHONPATH=backend python -c "import app"`），之後改 backend import 記得跑它，別只跑 `backend:test`。

## 2026-09-09 日誌集中；順帶修掉兩個實際缺陷

抽成 `backend/logging_setup.py`：模組只 `get_logger(__name__)`（掛在 `ntust_monitor` 底下），handler 只由進入點設定。過程中查出兩個真問題：
1. **後端與 worker 會寫同一個輪替檔**。`setup_logging()` 是在模組 import 時呼叫，而 `tr_rooms` 開始共用 `monitor.semester` 之後，FastAPI 後端 import 就會掛上 `ntust_monitor.log` 的 `TimedRotatingFileHandler`，兩個 process 午夜輪替會互搶。改成只有 worker 進入點呼叫 `configure_worker_logging(log_to_console=True)`；實測 `import backend.app` 後 handlers 為空、`import worker` 後才有檔案與 stdout。
2. **`email_sender` 的日誌等於丟掉**。它用 `getLogger(__name__)`，那棵樹與 root 都沒有 handler，寄信失敗看不到；改用 `get_logger` 後會進 `ntust_monitor.log`。
時區：`monitor.py` 內嵌的 `ZoneInfo('Asia/Taipei')` 改用 `config.TAIPEI` 與 `time_utils.now()`。其餘 `datetime.now()` 是顯示用的 naive 時間，主機本地時間即台北，改成 aware 反而可能與其他 naive 值比較出錯，維持原樣。

## 2026-09-09 後端共用：build_session 與學期偵測合一；學校端知識寫成文件

`NTUST_VERIFY_SSL` 原本在 `config.py`、`api_client.py`、`enrollment.py` 各解析一次，`urllib3.disable_warnings` 呼叫兩次，`_setup_proxy` 在兩個 client 各有一份幾乎相同的實作。收成 `monitor/utils.py` 的 `resolve_verify_ssl`／`proxies_from_env`／`build_session`（SOCKS5 一律轉 socks5h 走 session.proxies，不動全域 socket），兩個 client 共用。
學期偵測三份：`monitor/semester.py` 有格式驗證、候選回退與日期兜底，另外兩處是簡化版（取不到就丟例外）。抽出 `fetch_semesters_info`（快取原始清單），`tr_rooms.fetch_current_query_semester` 委派給 `get_default_semester`，`api/courses` 的學期清單改讀同一支，semestersinfo 不再被打三次。
另外把今天查到的學校端行為寫成 `docs/data-contracts/ntust-systems.md`（SSO 進入點與登入頁的假錯誤、各頁面資料來源、Restrict1/2 語意、通識第三碼 G 規則、選課階段時程、速率保護），並在 AGENTS.md 指向它——這些都是「看程式不會知道、每次都要重查」的東西。

## 2026-09-09 新版本提示；寫死的學期改為由日期推算

部署後使用者的分頁仍跑舊 bundle，同一天踩兩次「明明部署了卻沒生效」（通識分類、修課中顯示）。新增 `UpdateNotice`：每 5 分鐘與分頁重新可見時抓一次 `index.html`（`cache: 'no-store'`），比對其中的 `/assets/*.js` 與目前載入的是否相同，不同就顯示可點的重新整理橫幅；抓不到就不提示，避免離線誤報。
寫死學期：`useCourseSearch` 初值是 `'1142'`（已過期），正是選課工作台模式沒自動切到加退選的原因；`coursesFromScheduleSync` 也把 `scheduledOffering.semester` 寫死 `'1151'`。改為 `guessCurrentSemester()` 由日期推算（8–1 月為上學期，規則與 `backend/monitor/semester.py` 一致），API 回來後再校正；同步時把 `querySemester` 傳進去。監控頁的離線 fallback 也改由推算決定 `current`。邊界驗算：1/15→1141、2/1→1142、7/31→1142、8/1→1151、2027/3/1→1152。

## 2026-09-09 修課軌跡補上「修課中」：正在修的課原本被過濾掉

`CourseTimelinePage` 的 `timelineSemesters` 是 `semester.courses.filter(isHistoryImportedCourse)`，只留有成績的歷史匯入課，於是校務同步寫入、還沒有成績的 12 門在修課程整批看不到——大二上因此只顯示 2 門待加簽。統計面板其實一直有算它們（`usePlannerStats` 走的是全部 `semester.courses`），所以是純顯示缺口。改為全部顯示，並以 `!isHistoryImportedCourse && !virtualSelection` 判定「修課中」（天藍色標籤），與歷史修課（綠）、待加簽／未來規劃（琥珀／藍）區分；摘要列多一格「修課中 N 門」。

## 2026-09-09 通識判定修正（第三碼 G）＋向度回查＋兩端顯示補齊

查證：`categoryFromSyncedCourse` 只認 `GE` 開頭是通識，於是 `TCG039301 環境關懷與生態寫作`、`TCG100301 書法藝術` 因為學校標「必修」被歸成本系必修，讓通識少算、本系必修多算。抓 1151 全學期 2189 門統計課碼前綴與官方 `Dimension` 的關係：**第三碼是 G 的 14 個前綴（TCG/GE3/DTG/BAG/EEG/ADG/MBG/IBG/VEG/CXG/ECG/ETG/MEG/MIG）共 173 門，向度覆蓋率 100%，且沒有任何第三碼為 G 的課沒有向度**，因此以「課碼第三碼為 G 或 GE 開頭」判定通識，且必須早於 `required_type`。
向度：校務同步的選課清單沒有 `Dimension`，改用課碼回查課程查詢系統（`lookupGenEdDimensions`，只查通識課，避免每門課都打一次 API）補上。
顯示：`usePlannerStats` 本來就有算 `genEdDimensions`，只是網頁版沒畫出來（手機版有）；門檻完成度補上 A–F 向度標記，hover 顯示向度名稱。iOS 課程卡與課堂筆記補上課碼、學分、類別與向度。

## 2026-09-09 iOS：課表變成課堂筆記入口、補上成績試算、修掉存檔會抹掉網頁資料的問題

查證到的資料遺失面（DB trigger 對 `semesters`／`settings`／`targets` 是「incoming 有就整包取代」）：iOS 的 `CloudCourse` 沒有 `scheduledOffering`，`cloudAppDataPayload()` 還把 `email`／`link`／`gradingPolicy` 寫死成 `nil`／`[]`，`CloudUserSettings` 也不含 `programDepartments`。所以在手機改一門課的老師名字，就會抹掉網頁版的課碼、節次、教室、必選修、Email、課程連結、整份成績試算權重與雙主修輔系系所設定。六位使用者的 `last_writer` 都還是 `web`、33 門課的 `scheduledOffering` 都完整，所以尚未實際發生。
做法：`CloudCourse`／`CloudSemester`／`CloudUserSettings` 改為保留未知欄位（新增 `JSONValue` 與動態鍵，未知鍵原樣進出），`PlannerCourse` 補 `email`／`link`／`gradingPolicy`／`extras`，兩個方向都完整對應。
定位：使用者指出會用到課堂筆記的時機是上課當下，入口應該在課表而不是學分規劃區。課表格子的詳情頁加「課堂筆記與成績試算」，與學分規劃共用同一支 `CourseNoteEditor`（教授／Email／地點／時間／課程連結／備註＋評分項目權重與分數，顯示總權重與依已填分數換算的目前總分）。手機原本沒有成績試算 UI，這次補上，與網頁版共用同一份 `gradingPolicy`。
同時移除手機端的「新增課程」與規劃頁的「設定畢業門檻」入口（門檻改在設定頁調整，`CloudTargets` 欄位齊全所以安全），避免手機再長出第二套殘缺編輯器；`CourseEditorSheet`、`CourseDetailSheet` 一併刪除。

## 2026-09-09 同步拆成三項並重新命名；已保存密碼不再每次要求輸入

命名：原本「課表與成績」／「官方選課狀態」不精確——加退選也是官方狀態，差別在**階段與用途**。改成「目前選課」（選課清單＋功課表，`ChooseList/D01/D01`）、「歷年成績」（`StuScoreQuery/DisplayAll`）、「初選志願登記」（A02 已登記志願與志願序）。
拆分理由：原本按一次「課表與成績」會連打三段——選課清單、歷年成績、再對每筆歷史課去 querycourse 補查節次。歷年成績一學期才變一次（期末登分），加退選期天天同步課表卻要重抓 21 筆成績＋逐筆補查，慢且沒必要。`syncSchoolData` 改吃 `{ includeSchedule, includeHistory }`，只跑課表時不重算歷史合併（避免用空陣列蓋掉已修紀錄與待重修），覆蓋確認也只在真的要重寫課表時才問。設定頁三個來源各自一列、各自記上次同步時間。
非當期提示：加退選期點「初選志願登記」會說明「初選頁本來就會回 0 門，這不是同步失敗」——使用者實際踩到這個困惑。
密碼：帳密本來就已加密存在 `app_private.school_credentials`（留空即沿用），但 UI 每次都把空白密碼欄擺在最顯眼處，看起來像必填。已保存時改為顯示「使用已保存的密碼（帳號）」＋「改密碼」，只有要換才展開輸入框（用推導而非 effect 同步 state，符合 `react-hooks/set-state-in-effect`）。
另補：待加簽課程若已出現在選課清單，標示「已在選課清單中（已選上），這筆待加簽可以移除」——使用者的 `BA2208301 成本會計` 正是這個狀況。

## 2026-09-08 查出本地規劃資料比後端快照舊一輪（iOS 同步未寫回 user_data）

比對：後端 `schedule_sync_snapshots` 是 12 門且體育是 `PE139A032`；`public.user_data` 的大二上只有 11 門、體育是 `PE139A022`，缺 `TCG100301 書法藝術`。`user_data.updated_at`（15:21 UTC）比快照（09:09 UTC）還新，所以不是覆蓋順序問題。當天 12:45 左右後端 log 有手機經 tailnet 打 `/api/schedule/B11430207`，研判是**iOS 同步只更新了後端快照，沒把課程寫回 `user_data`**。待使用者在 Web 按一次「目前選課」同步後再判斷是否要追 iOS 寫入路徑。

## 2026-09-08 選課工作台依教務處時程表判斷階段；加退選期改顯示實際選課清單

問題：工作台三個面板都只讀官方**初選 A02**，加退選期 A02 本來就是空的，所以使用者在加退選期看到「已登記 0 門」而實際學校有 12 門，看起來像資料掉了。
查證：使用者提供「115 學年度第 1 學期選課作業時程表」PDF。今天（民國 115/9/8）落在**全校加退選 9/7 09:00–9/21 17:00**。那 12 門的權威來源是 `ChooseList/D01/D01`，校務同步已經在抓並寫進 `data.semesters[推定學期].courses`（`id` 前綴 `school-`、無歷史匯入標記），所以資料早就有，只是工作台沒讀。
做法：新增 `web/src/shared/domain/enrollmentCalendar.ts` 把時程表編碼成資料（民國年換算、`currentEnrollmentPhase`／`nextEnrollmentPhase`／`enrollmentPeriodCode`），換學期只需加一組。工作台顯示「目前階段」橫幅；加退選模式左欄改成「目前選課清單」（唯讀，本地刪除不會真的退選，所以不給刪除鈕）並把這些課畫進功課表、指標改成「已選上／目前學分」；初選模式在非初選期顯示明確說明而不是空面板。模式預設跟著階段，但因為 `querySemester` 初值是寫死的 `1142`（要等 `/api/courses/semesters` 回來才是 1151），改用 effect 在學期解析後補上，使用者手動切過就不再覆蓋。
邊界驗算：9/7 08:59 closed、9/7 09:01 addDrop、9/21 17:01 closed、9/23 correction、6/20 preregistration，與 PDF 一致。

## 2026-09-08 移除選課工作台的「加簽追蹤」模式

查證：`addCode` 只出現在型別聯集與模式選項兩處，沒有任何模式專屬邏輯（全app 唯一的模式判斷是 `planningMode !== 'lottery'` 用來決定衝堂是否阻擋），因此它與「加退選」完全等價；「待加簽課程」清單是官方拒絕後產生的 `virtualCourses`，不依模式顯示，移除模式不影響那些課與畢業門檻統計。模式也沒有持久化（只是 component state，預設 lottery），不需要資料遷移。使用者裁示移除，理由是該情境已由選課監控系統涵蓋。

## 2026-09-08 用登入中的 Chrome 逐頁檢查換行；只有「重設」是真的多餘換行

寫了一支偵測器（走 text node，用 Range 的 client rects 數不同 top，避開 padding 造成的誤判）掃過課程查詢、選課工作台、選課監控三個分頁、修課軌跡、設定：唯一真的多餘換行是課程設定彈窗的「重設」按鈕（圖示＋兩字被拆成「重／設」），已加 `whitespace-nowrap shrink-0`；同類「圖示＋短標籤」按鈕（監控設定的測試信、儀表板的清除日誌）一併補上。選課工作台課表的 `08:10 / 09:00` 是 `whitespace-pre-line` 刻意換行，監控設定那兩處是長句子，都不是問題。同時在正式站確認 GPA 欄位有值（3.27／3.31，證明 app_private 密鑰路徑端到端可用）、名額分母正確（68/55 超額標紅）、課程列高 81px、操作三顆按鈕同一行、監控頁時間已顯示日期、課程設定彈窗正確讀出 `attempt_count`「目前已嘗試 1 次」。

## 2026-09-08 課程查詢列高從 156px 降到 81px

操作欄四個控制項改成一列三顆小按鈕（規劃／選課／監聽，完整說明放 title），認列下拉只在真的有雙主修／輔系規則時才出現（沒有時它只有「不指定認列」一個選項）。量測後發現列高的主因其實不只是按鈕：課名欄被壓到 48px 寬，字與標籤垂直堆成 119px；補上 `min-w-[200px]`、操作欄改 `w-px whitespace-nowrap` 後，六列都是 81px（原 156px），無水平溢出。

## 2026-09-08 刪除三個 codex 殘留分支

都停在 6 月，且沒有 main 缺少的東西：`web-planner-redesign` 領先 0 個 commit（內容全在 main）；`web-ux-audit-low-risk`（19）與 `project-refactor`（99）的內容在 2026-09-07 已挑完，剩下的是刻意不要的後端目錄重整與 typed planner。刪除本機與 origin 的分支，並移除殘留的空目錄 `tests/backend/typed_planner`。分支尖端 SHA 記錄於此以備救回（GitHub 端 90 天內也可用 reflog／API 復原）：
`project-refactor` 7b15141c1dfa00e0ee165b34d7272f37bf70b6a2、
`web-ux-audit-low-risk` 9952315b6b3a006dd0ca9b63ef35e01039d2cd9f、
`web-planner-redesign` d46699d1168731db3e1352438a5051944ed793f7。

## 2026-09-08 名額判定欄位查清（TODO 的假設是錯的）＋過期學期停止輪詢

查證來源：querycourse 的 `app.js` 標籤表（權威，不是猜的）——
`ChooseStudent`=本校選課人數、`ThreeStudent`=系統學校選課人數、`AllStudent`=選課總人數(本校/系統學校)、
`Restrict1`=**本校初選人數上限(限舊生)**、`Restrict2`=**本校加退選人數上限/新生第一學期初選人數上限**、
`NTURestrict`/`NTNURestrict`=台大/師大名額。所以列表的 `50(45/5)` 是總人數(本校/系統學校)，**不是額外名額**；台大師大學生有自己的名額，分母是本校上限時分子就必須是 `ChooseStudent`，不能用 `AllStudent`。

真正的缺陷：監控一律用 `Restrict1`，且把 9999 當成「無人數上限、恆視為有名額」。1151 學期 2189 門課中有 **833 門 `Restrict1=9999`**（其中 235 門依 `Restrict2` 其實已額滿），這些課永遠不會通知額滿，儀表板還顯示「40/9999」。量測後確認：兩欄都有實數的 1356 門課裡兩者**完全相同**（差異 0），只有 R2 的 810 門、沒有只有 R1 的——所以「依階段選欄位、該欄位 9999 就退回另一個」既正確又安全。抽成 `backend/course_capacity.py`，monitor、worker、Compass 課程查詢、官方初選四處共用。行為變化：原本被當成無上限的課若已額滿，自動加選不再盲送（使用者裁示採用新行為，且舊行為會在正式選課期間立刻用光 3 次嘗試然後永久停止）。

同時查出：13 門監控課程有 10 門屬於過去學期（最舊 1121，三年前），每幾秒被查一次但資料永不變動。worker 改為在讀設定時把 `semester` 嚴格早於當前學期的課標成 `status='expired'` 並寫一筆使用者可見的日誌，之後不再輪詢；取不到當前學期或寫入失敗就不判定，避免課程靜默消失。前端顯示「學期已結束」與說明，改學期存檔時會把 `expired` 重設回 `monitoring`（否則改了也不會再被檢查）。

## 2026-09-08 移除 `user_settings.student_password` 欄位

資料已於稍早清空、`ENCRYPTION_KEY` 也已從本機與 Windows 的 `.env` 移除（查證：resend 密鑰以共用密鑰解得開）。前端與 worker 都用 `select('*')` 讀取、upsert payload 不含此欄位，所以直接 drop 不影響。套用後查證：PostgREST 回 42703（欄位不存在），worker 實際 `fetch_config()` 三位使用者都仍從 `app_private.school_credentials` 取得密碼。任務完成的一次性腳本 `retire_encryption_key.py`、`migrate_gpa_api_keys.py` 一併移除。

## 2026-09-08 15:26 GPA 安全化已上線

migration 已套用；B11430207 的 62 字元密鑰搬進 `app_private.gpa_api_keys`（解密比對長度相同），`user_data.content.settings.gpaApi` 已移除。部署後查證：`/api/gpa-api-key` 無 token 回 401，未登入的課程查詢回 `gpa_status=not_enabled`，worker 200 行內 54 次查詢成功零錯誤。

## 2026-09-08 部署腳本補型別檢查：`tsc --noEmit -p .` 不等於 build 的 `tsc -b`

GPA 那次部署在 web build 失敗（`api.ts` 少 import 型別）。原因：驗證時跑的 `npx tsc --noEmit -p .` 走根 tsconfig，不含 app 專案參照，因此沒檢到；build 用的是 `tsc -b`。而部署腳本把 build 排在 push 與遠端 pull 之後，遠端已前進到壞 commit 才失敗。已在腳本的測試階段加 `cd web && npx tsc -b`。另注意：中斷的部署會讓遠端 HEAD 已前進，重跑時 diff 判斷會認為沒事要做，必須用 `--force`。

## 2026-09-08 GPA 密鑰改存 app_private，查詢加快取與 429 退避

問題：myNTUST token 明文存在 `public.user_data.content.settings.gpaApi`（使用者自己的 session 就讀得到，且會隨資料同步四處流動），前端還把它塞進 `X-GPA-API-Key` 標頭；一次搜尋 30 筆就打 30 次 API（限速 120 次/分）。正式庫只有 1 位使用者設定過（B11430207，62 字元）。
做法：新增 `app_private.gpa_api_keys` 與三個 service_role RPC，沿用校務帳密同一把 Fernet；新增 `/api/gpa-api-key`（GET/PUT/DELETE，只回報是否已保存）；課程查詢改由 `Authorization` 取出密鑰於後端解密使用，`X-GPA-API-Key` 移除。查詢改 `fetch_course_gpas`：課程代碼去重、程序內共用 24 小時快取（GPA 與使用者無關）、最多 4 條併發、收到 429 就依 `Retry-After` 暫停整批並回 `rate_limited`；`error` 不進快取以免暫時故障被記一天。查證：myNTUST 沒有公開的批次端點，所以「批次」以去重＋快取＋限流併發實作，而非單一批次請求。

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
