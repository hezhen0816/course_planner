-- 加選嘗試次數改存資料庫（原本只在 worker 記憶體，重啟歸零）。
-- max_attempts 先前只存在於程式與前端，正式庫從未建立，一併補上。
-- 前端「重設次數」直接把 attempt_count 寫成 0，worker 讀到 0 即清除記憶體計數。
alter table public.monitored_courses
  add column if not exists max_attempts integer not null default 3,
  add column if not exists attempt_count integer not null default 0;

alter table public.monitored_courses
  drop constraint if exists monitored_courses_attempts_check;
alter table public.monitored_courses
  add constraint monitored_courses_attempts_check
  check (max_attempts >= 1 and max_attempts <= 100 and attempt_count >= 0);
