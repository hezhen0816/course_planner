# Docs

`docs/` 保存跨端產品決策與可回查的 QA 記錄，不放 build output、臨時截圖或本機快取。

- `architecture/refactor-plan.md`：目前有效的全專案重構計畫、執行順序與驗證 gate。
- `data-contracts/database-schema.md`：current production schema 與 planned typed schema 的責任邊界。
- `data-contracts/ntust-systems.md`：學校端行為的查證結果（SSO 進入點、各頁面資料來源、名額欄位語意、通識課碼規則、選課階段、速率保護）；動這些程式前先看。
- `design/`：設計 QA 記錄。
- `archive/2026-refactor/`：歷史產品定位、UX audit 與 reference images；只作為脈絡，不作為現行實作規格。

大型或可重現的測試 fixture 請放 `tests/fixtures/`；不需要長期保存的 debug 產物請留在 `/tmp` 或本機未追蹤目錄。
