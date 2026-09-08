# 學校系統整合：查過才知道的事

這份記錄「看程式不會知道、每次都要重新查一遍」的學校端行為。實作分散在
`backend/ntust_common.py`、`backend/tr_rooms.py`、`backend/course_capacity.py`、
`backend/monitor/`、`web/src/shared/domain/`，這裡集中說明**為什麼**要那樣寫。

查證日期都寫在條目裡；學校改版後請重新查證再改這份文件，不要憑印象修改。

---

## 1. SSO 登入：進入點決定成敗

**查證 2026-09-08（B11430207 實登，逐跳記錄）**

登入必須從**站台根目錄**進入，不能直接打深層頁面。

```
GET  https://courseselection.ntust.edu.tw/            ← 進入點必須是這個
 302 ssoam2.ntust.edu.tw/connect/authorize?...
 200 ssoam2.ntust.edu.tw/account/login?ReturnUrl=...  ← 登入表單
POST ssoam2.ntust.edu.tw/                             ← 送出帳密
 200 ssoam2.ntust.edu.tw/connect/authorize?...        ← 回傳 form_post 表單
POST courseselection.ntust.edu.tw/signin-oidc         ← OIDC 回呼
 302 courseselection.ntust.edu.tw/Account/OpenIDCallback   ← 這一步才建立 ASP.NET_SessionId
 200 courseselection.ntust.edu.tw/Home/Index
```

**踩過的坑**：以 `/First/A06/A06` 當進入點時，登入回來會直接落在 A06，
沒有經過 `/Account/OpenIDCallback`，網站沒有自己的 session，於是把人導去
`/Account/Logout` —— 連 SSO session 一起登出，之後再取目標頁自然又回到登入頁，
表面症狀是「登入後無法進入目標頁面」。所以 `login_to_target()` 有 `entry_url`
參數，選課系統一定要傳站台根目錄。

**另一個坑**：判斷「這頁是不是 OIDC 回呼」不能用「URL 含 `signin-oidc`」——
登入頁的 `ReturnUrl` 查詢字串裡就含這個字，會把空白登入表單再 POST 一次。
要看 URL **path**。

**登入頁的假錯誤**：登入頁固定內含這些東西，只看「存在」會誤判成失敗。

| DOM 內容 | 實際狀態 |
|---|---|
| `cf-turnstile` / `h-captcha` / `g-recaptcha` 容器與 `*-response` 欄位 | 預設 `display:none`，連續失敗才由 JS 顯示 |
| `v-show="capsLockOn"` 的「Caps Lock is on」 | 常駐 DOM |
| 「密碼有效期間為 180 天」公告 | 常駐公告，不代表要求改密碼 |

所以錯誤判讀只看**實際顯示**的元素（`is_hidden_element()` 會跟著看 inline
`display:none`、`hidden`、`v-show`、`v-if`）；「要求改密碼」要等登入表單消失才算。

**兩套流程的 POST 完全相同**：離線比對過 `ntust_common` 與 monitor 自己組的
POST（URL 與欄位一字不差，都是 POST 到 `https://ssoam2.ntust.edu.tw/`），
差異只在失敗診斷，所以合一是安全的。

**SSO 端對特定帳號回 500**：`B11430227` 送出後 302 到根目錄回 500，
同一段程式對另外兩個帳號正常。這是學校端問題，只能請本人用瀏覽器登入確認。

---

## 2. 各頁面是哪一份資料

| 用途 | URL | 說明 |
|---|---|---|
| 目前選上的課、功課表 | `ChooseList/D01/D01` | 加退選期這份就是最新課表；網頁的「功課表／選課清單」綠色鈕就是它 |
| 初選志願、待加入、志願序 | `First/A02/A02` | **只有初選期有值**；加退選期回 0 門是正常的，不是同步失敗 |
| 歷年成績 | `StuScoreQueryServ/StuScoreQuery/DisplayAll` | 登入後實際會轉址停在 `stu.ntust.edu.tw/stueduneed/Edu_Need.aspx`，資料仍抓得到 |
| 加選／退選 | `First/A06/*`（初選後選課）、`AddAndSub/B01/*`（加退選） | 用哪一支取決於選課階段 |
| 課程查詢 API | `querycourse.ntust.edu.tw/QueryCourse/api/courses` | 需要 `Origin`／`Referer` 標頭；整學期未過濾清單約 2 MB，晚間要 60 秒以上 |
| 學期清單 API | `.../api/semestersinfo` | 唯一來源在 `backend/monitor/semester.py` |

---

## 3. 名額欄位：`Restrict1` 不是唯一上限

**查證 2026-09-08（querycourse 自己的 `app.js` 標籤表）**

| 欄位 | 學校標籤 |
|---|---|
| `ChooseStudent` | 本校選課人數 |
| `ThreeStudent` | 系統學校（台大系統）選課人數 |
| `AllStudent` | 選課總人數(本校/系統學校) |
| `Restrict1` | **本校初選人數上限(限舊生)** |
| `Restrict2` | **本校加退選人數上限／新生第一學期初選人數上限** |
| `NTURestrict` / `NTNURestrict` | 台大／師大名額 |

所以：

- 課程列表顯示的 `50(45/5)` 是**總人數(本校/系統學校)**，不是「額外名額」。
- 台大師大學生有自己的名額，分母是本校上限時，分子就必須用 `ChooseStudent`，不能用 `AllStudent`。
- 上限要看階段：初選用 `Restrict1`，加退選用 `Restrict2`；該欄位是 `9999`（無上限哨兵）時退回另一個。
  1151 學期 2189 門課中有 **833 門 `Restrict1=9999`**，只看 `Restrict1` 會把它們當成「無人數上限」而永遠不通知額滿。
  兩欄都有實數的 1356 門課，兩者**完全相同**，所以這個規則不會改變既有判斷。
- 兩個上限都不是硬上限：授權加簽會讓 `ChooseStudent` 超過上限（1151 有 319 門），剩餘名額可能是負數。

實作在 `backend/course_capacity.py`。

---

## 4. 通識課：看課碼第三碼

**查證 2026-09-09（1151 全學期 2189 門）**

課碼**第三碼是 `G`**（或 `GE` 開頭）就是通識：`TCG`、`GE3`、`DTG`、`BAG`、`EEG`、
`ADG`、`MBG`、`IBG`、`VEG`、`CXG`、`ECG`、`ETG`、`MEG`、`MIG` 共 173 門，
官方 `Dimension` 覆蓋率 **100%**，且沒有任何第三碼為 G 的課缺向度。

**判定必須早於 `required_type`**：學校對通識也會標「必修」，先看 `required_type`
會把 `TCG039301 環境關懷與生態寫作` 之類歸成本系必修。

**向度來源**：校務同步的選課清單**沒有** `Dimension` 欄位，要用課碼回查課程查詢
系統補上（`lookupGenEdDimensions`，只查通識課，不對每門課都打一次 API）。

---

## 5. 選課階段：以教務處時程表為準

時程表編碼在 `web/src/shared/domain/enrollmentCalendar.ts`（來源：教務處「選課作業
時程表」PDF），換學期只需新增一組。用它推導：

- 選課工作台的預設模式（加退選期看選課清單，初選期看志願登記）
- 監控 worker 的 `enrollment_period`（加退選 `B01`、初選 `A06`）——用錯會打到錯的加選端點

115-1 實際區間：本校初選 6/12–6/24、台大系統初選 8/6–8/11、新生轉學生初選
8/14–8/24、**全校加退選 9/7 09:00–9/21 17:00**、選課更正 9/22–9/24、二次退選 11/16–12/3。

---

## 6. 速率與保護

- **登入**：連續 3 次失敗暫停自動登入，冷卻遞增 15 → 30 → 60 分鐘，成功即重置。
  學校規定密碼錯 10 次鎖 15 分鐘，這是為了不把帳號打到鎖住。
  冷卻狀態存 `user_settings.login_paused_until`，worker 重啟後沿用，儀表板會顯示橫幅。
- **加選**：只有實際送出請求才計入 `attempt_count`（速率限制與「非選課時段」的失敗不計），
  次數存資料庫，worker 重啟不歸零。
- **只有課程開了自動加選才會登入 SSO**：查名額走公開 API 不需登入，
  沒有課要自動加選就不該為了「準備 session」反覆打 SSO。
- **myNTUST GPA API**：120 次/分，沒有批次端點。GPA 與使用者無關，所以程序內共用
  24 小時快取、去重、最多 4 條併發，收到 429 就依 `Retry-After` 暫停整批。
