-- worker 連續登入失敗達門檻會暫停自動登入 15 分鐘（保護校務帳號不被鎖）。
-- 把暫停到期時間與原因存進 user_settings，讓儀表板能顯示警示、worker 重啟後也能延續冷卻。
alter table public.user_settings
  add column if not exists login_paused_until timestamptz,
  add column if not exists login_pause_reason text;
