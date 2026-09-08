-- 校務密碼的唯一來源是 app_private.school_credentials（密文，只有 service_role 可讀）。
-- user_settings.student_password 是 NTUST_Course_Monitor 時代的欄位，2026-09-08 已由
-- scripts/monitor/retire_encryption_key.py 清空，前端與 worker 都不再讀寫，移除欄位本身
-- 以免日後有人又往這裡寫明文。
alter table public.user_settings drop column if exists student_password;
