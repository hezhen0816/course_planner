# Course Compass 修課羅盤 iOS

`ios/` 是原生 SwiftUI App，負責：

- 首頁摘要
- 每週課表
- 手機版學分規劃
- 設定與同步入口

## 啟動

```bash
cd /Users/hezhen/Project/course_planner
npm run ios:open
```

## 驗證編譯

```bash
cd /Users/hezhen/Project/course_planner
npm run ios:build
```

## 資料流

- 使用雲端帳號登入
- 規劃資料讀寫 `public.user_data`
- 課表與歷史修課紀錄透過根目錄 `backend/` 的同步服務抓取
- 同步結果由後端寫入快照表，再回傳給 iOS
- 同步服務網址由 `Info.plist` 的 `BackendServiceBaseURL` 提供，預設為 Railway production backend

## 程式結構

- `AppSessionStore.swift` 保留 shared state、初始化與簡單 planner mutation
- `AppSessionStore+Auth.swift`、`+PlannerCloud.swift`、`+ScheduleSync.swift`、`+HistoryImport.swift`、`+MoodleAssignments.swift`、`+LocalCache.swift`、`+Notifications.swift`、`+Networking.swift` 依責任拆分同步、登入、快取與網路 helper
- `NativeModels.swift` 保留 app tab 與共用基礎型別；planner、schedule、API DTO、cloud DTO 已拆到獨立模型檔

## 注意事項

- `school_password` 目前依產品需求保存在 `user_data.content.settings`，這是已知安全取捨；本次整理沒有改成 Keychain 或後端加密代管
- iOS 端透過 `BackendServiceBaseURL` 使用 Railway 上的同步服務，不需要手動輸入 IP
