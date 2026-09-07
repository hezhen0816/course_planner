create schema if not exists legacy;

alter table if exists public.course_meetings set schema legacy;
alter table if exists public.courses set schema legacy;
alter table if exists public.school_accounts set schema legacy;
alter table if exists public.sync_states set schema legacy;
