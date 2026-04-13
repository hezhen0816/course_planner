# Course Compass 修課羅盤 Web

`web/` 是桌面優先的課程規劃產品，負責：

- 八學期課程編排
- HTML 匯入
- 學分門檻設定與進度統計
- 課程詳細資訊與成績試算

不承擔首頁摘要、課表同步或手機提醒流程。

## 啟動

```bash
cd /Users/hezhen/Project/course_planner/web
npm install
npm run dev
```

也可以從 repo 根目錄執行：

```bash
cd /Users/hezhen/Project/course_planner
npm run web:dev
```

## 建置與檢查

```bash
npm run build
npm run lint
npm audit --audit-level=moderate
```

## 環境變數

Web 會透過 `envDir` 讀取 repo 根目錄的 `.env`：

```bash
VITE_SUPABASE_URL=...
VITE_SUPABASE_ANON_KEY=...
```

## 資料邊界

- 直接使用雲端帳號登入
- 規劃資料保存到 `public.user_data`
- 與 iOS 共用學分規劃資料模型，但不共用 UI 狀態
