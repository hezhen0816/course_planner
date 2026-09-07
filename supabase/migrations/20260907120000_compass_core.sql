-- Course Compass core schema, consolidated from the retired project
-- qpdvtsbqdpitreslazoe (its incremental migrations are kept under
-- docs/archive/supabase-migrations-old-project/ for reference only).
-- Applied to the shared project eerlhmvwucnlbhemhvtz, which already holds the
-- NTUST_Course_Monitor tables (see 20260618111348_baseline_schema.sql).
-- Idempotent: safe to re-run.

-- ---------------------------------------------------------------- helpers
create or replace function public.set_updated_at()
returns trigger
language plpgsql
set search_path to 'public', 'pg_catalog'
as $$
begin
  new.updated_at = timezone('utc', now());
  return new;
end;
$$;

-- ---------------------------------------------------------------- user_data
create table if not exists public.user_data (
  id uuid default gen_random_uuid() not null,
  user_id uuid not null,
  content jsonb,
  updated_at timestamptz default timezone('utc'::text, now()),
  content_version integer default 2 not null,
  legacy_content jsonb,
  migrated_at timestamptz,
  last_writer text,
  constraint user_data_pkey primary key (id),
  constraint user_data_user_id_key unique (user_id),
  constraint user_data_user_id_fkey foreign key (user_id) references auth.users(id)
);

create or replace function public.normalize_user_data_content_v2()
returns trigger
language plpgsql
security definer
set search_path to 'public'
as $$
declare
  previous_content jsonb;
  incoming_content jsonb;
  merged_content jsonb;
  detected_writer text;
begin
  previous_content := case
    when tg_op = 'UPDATE' then coalesce(old.content, '{}'::jsonb)
    else '{}'::jsonb
  end;
  incoming_content := coalesce(new.content, '{}'::jsonb);

  if jsonb_typeof(incoming_content) is distinct from 'object' then
    incoming_content := '{}'::jsonb;
  end if;

  if new.legacy_content is null and new.content is not null then
    if tg_op = 'UPDATE' then
      new.legacy_content := coalesce(old.legacy_content, old.content, new.content);
    else
      new.legacy_content := new.content;
    end if;
  end if;

  detected_writer := case
    when incoming_content ? 'schemaVersion'
      or incoming_content ? 'requirementSets'
      or incoming_content ? 'pendingRequirements'
      or incoming_content ? 'historyRecords'
      then 'web'
    else 'legacy_client'
  end;

  merged_content := previous_content || incoming_content;
  new.content := merged_content || jsonb_build_object(
    'schemaVersion', 2,
    'semesters', coalesce(incoming_content->'semesters', previous_content->'semesters', '[]'::jsonb),
    'targets', coalesce(incoming_content->'targets', previous_content->'targets', '{}'::jsonb),
    'settings', coalesce(incoming_content->'settings', previous_content->'settings', '{}'::jsonb),
    'requirementSets', coalesce(incoming_content->'requirementSets', previous_content->'requirementSets', '[]'::jsonb),
    'pendingRequirements', coalesce(incoming_content->'pendingRequirements', previous_content->'pendingRequirements', '[]'::jsonb),
    'historyRecords', coalesce(incoming_content->'historyRecords', previous_content->'historyRecords', '[]'::jsonb)
  );
  new.content_version := 2;
  new.migrated_at := coalesce(new.migrated_at, timezone('utc', now()));

  if tg_op = 'INSERT'
    or new.last_writer is null
    or (
      tg_op = 'UPDATE'
      and new.content is distinct from old.content
      and new.last_writer is not distinct from old.last_writer
    ) then
    new.last_writer := detected_writer;
  end if;

  return new;
end;
$$;

revoke execute on function public.normalize_user_data_content_v2() from public, anon, authenticated;

drop trigger if exists trg_user_data_normalize_content_v2 on public.user_data;
create trigger trg_user_data_normalize_content_v2
  before insert or update on public.user_data
  for each row execute function public.normalize_user_data_content_v2();

alter table public.user_data enable row level security;
drop policy if exists "使用者只能查閱自己的資料" on public.user_data;
drop policy if exists "使用者只能新增自己的資料" on public.user_data;
drop policy if exists "使用者只能更新自己的資料" on public.user_data;
create policy "使用者只能查閱自己的資料" on public.user_data for select to authenticated
  using ((select auth.uid()) = user_id);
create policy "使用者只能新增自己的資料" on public.user_data for insert to authenticated
  with check ((select auth.uid()) = user_id);
create policy "使用者只能更新自己的資料" on public.user_data for update to authenticated
  using ((select auth.uid()) = user_id) with check ((select auth.uid()) = user_id);

-- ---------------------------------------------------------------- sync snapshots (service role only)
create table if not exists public.schedule_sync_snapshots (
  profile_key text not null,
  school_account text not null,
  student_name text,
  payload jsonb not null,
  synced_at timestamptz default timezone('utc'::text, now()) not null,
  updated_at timestamptz default timezone('utc'::text, now()) not null,
  constraint schedule_sync_snapshots_pkey primary key (profile_key)
);
create index if not exists schedule_sync_snapshots_synced_at_idx on public.schedule_sync_snapshots using btree (synced_at desc);

create table if not exists public.history_import_snapshots (
  profile_key text not null,
  school_account text not null,
  student_name text,
  payload jsonb not null,
  imported_at timestamptz default timezone('utc'::text, now()) not null,
  updated_at timestamptz default timezone('utc'::text, now()) not null,
  constraint history_import_snapshots_pkey primary key (profile_key)
);
create index if not exists history_import_snapshots_imported_at_idx on public.history_import_snapshots using btree (imported_at desc);

create table if not exists public.moodle_assignment_snapshots (
  profile_key text not null,
  school_account text not null,
  payload jsonb not null,
  synced_at timestamptz default timezone('utc'::text, now()) not null,
  updated_at timestamptz default timezone('utc'::text, now()) not null,
  constraint moodle_assignment_snapshots_pkey primary key (profile_key)
);
create index if not exists moodle_assignment_snapshots_synced_at_idx on public.moodle_assignment_snapshots using btree (synced_at desc);

do $$
declare t text;
begin
  foreach t in array array['schedule_sync_snapshots','history_import_snapshots','moodle_assignment_snapshots'] loop
    execute format('alter table public.%I enable row level security', t);
    execute format('drop policy if exists "service role only" on public.%I', t);
    execute format('create policy "service role only" on public.%I for all using ((select auth.role()) = ''service_role'') with check ((select auth.role()) = ''service_role'')', t);
    execute format('drop trigger if exists trg_%s_updated_at on public.%I', t, t);
    execute format('create trigger trg_%s_updated_at before update on public.%I for each row execute function public.set_updated_at()', t, t);
    execute format('revoke all on public.%I from anon, authenticated', t);
  end loop;
end $$;

-- ---------------------------------------------------------------- app_private (service role only)
create schema if not exists app_private;
revoke all on schema app_private from public, anon, authenticated;
grant usage on schema app_private to service_role;

create table if not exists app_private.school_credentials (
  user_id uuid not null,
  school_account text not null,
  password_ciphertext text not null,
  key_version integer default 1 not null,
  last_verified_at timestamptz,
  created_at timestamptz default timezone('utc'::text, now()) not null,
  updated_at timestamptz default timezone('utc'::text, now()) not null,
  constraint school_credentials_pkey primary key (user_id),
  constraint school_credentials_user_id_fkey foreign key (user_id) references auth.users(id) on delete cascade
);

create table if not exists app_private.school_sessions (
  user_id uuid not null,
  school_account text not null,
  session_ciphertext text not null,
  key_version integer default 1 not null,
  expires_at timestamptz not null,
  last_keep_alive_at timestamptz,
  created_at timestamptz default timezone('utc'::text, now()) not null,
  updated_at timestamptz default timezone('utc'::text, now()) not null,
  constraint school_sessions_pkey primary key (user_id, school_account),
  constraint school_sessions_user_id_fkey foreign key (user_id) references auth.users(id) on delete cascade
);

alter table app_private.school_credentials enable row level security;
alter table app_private.school_sessions enable row level security;
drop policy if exists school_credentials_service_role_only on app_private.school_credentials;
create policy school_credentials_service_role_only on app_private.school_credentials for all
  using ((select auth.role()) = 'service_role') with check ((select auth.role()) = 'service_role');
drop policy if exists school_sessions_service_role_only on app_private.school_sessions;
create policy school_sessions_service_role_only on app_private.school_sessions for all
  using ((select auth.role()) = 'service_role') with check ((select auth.role()) = 'service_role');
drop trigger if exists trg_school_credentials_updated_at on app_private.school_credentials;
create trigger trg_school_credentials_updated_at before update on app_private.school_credentials
  for each row execute function public.set_updated_at();
drop trigger if exists trg_school_sessions_updated_at on app_private.school_sessions;
create trigger trg_school_sessions_updated_at before update on app_private.school_sessions
  for each row execute function public.set_updated_at();
revoke all on app_private.school_credentials, app_private.school_sessions from public, anon, authenticated;
grant select, insert, update, delete on app_private.school_credentials, app_private.school_sessions to service_role;

-- RPCs (execute restricted to service_role)
create or replace function public.get_school_credentials(p_user_id uuid)
returns table(school_account text, password_ciphertext text, key_version integer, last_verified_at timestamptz)
language sql set search_path to ''
as $$
  select c.school_account, c.password_ciphertext, c.key_version, c.last_verified_at
  from app_private.school_credentials as c
  where c.user_id = p_user_id
  limit 1;
$$;

create or replace function public.upsert_school_credentials(
  p_user_id uuid, p_school_account text, p_password_ciphertext text,
  p_key_version integer default 1, p_last_verified_at timestamptz default timezone('utc'::text, now()))
returns void language sql set search_path to ''
as $$
  insert into app_private.school_credentials (user_id, school_account, password_ciphertext, key_version, last_verified_at)
  values (p_user_id, p_school_account, p_password_ciphertext, coalesce(p_key_version, 1), p_last_verified_at)
  on conflict (user_id) do update
  set school_account = excluded.school_account,
      password_ciphertext = excluded.password_ciphertext,
      key_version = excluded.key_version,
      last_verified_at = excluded.last_verified_at;
$$;

create or replace function public.delete_school_credentials(p_user_id uuid)
returns void language sql set search_path to ''
as $$
  delete from app_private.school_credentials as c where c.user_id = p_user_id;
$$;

create or replace function public.get_school_session(p_user_id uuid, p_school_account text)
returns table(school_account text, session_ciphertext text, key_version integer, expires_at timestamptz, last_keep_alive_at timestamptz)
language sql set search_path to ''
as $$
  select s.school_account, s.session_ciphertext, s.key_version, s.expires_at, s.last_keep_alive_at
  from app_private.school_sessions as s
  where s.user_id = p_user_id
    and s.school_account = p_school_account
    and s.expires_at > timezone('utc', now())
  limit 1;
$$;

create or replace function public.upsert_school_session(
  p_user_id uuid, p_school_account text, p_session_ciphertext text,
  p_expires_at timestamptz, p_last_keep_alive_at timestamptz default timezone('utc'::text, now()))
returns void language sql set search_path to ''
as $$
  insert into app_private.school_sessions (user_id, school_account, session_ciphertext, key_version, expires_at, last_keep_alive_at)
  values (p_user_id, p_school_account, p_session_ciphertext, 1, p_expires_at, p_last_keep_alive_at)
  on conflict (user_id, school_account) do update
  set session_ciphertext = excluded.session_ciphertext,
      key_version = excluded.key_version,
      expires_at = excluded.expires_at,
      last_keep_alive_at = excluded.last_keep_alive_at;
$$;

create or replace function public.delete_school_session(p_user_id uuid, p_school_account text default null)
returns void language sql set search_path to ''
as $$
  delete from app_private.school_sessions as s
  where s.user_id = p_user_id
    and (p_school_account is null or s.school_account = p_school_account);
$$;

do $$
declare f text;
begin
  foreach f in array array[
    'public.get_school_credentials(uuid)',
    'public.upsert_school_credentials(uuid, text, text, integer, timestamptz)',
    'public.delete_school_credentials(uuid)',
    'public.get_school_session(uuid, text)',
    'public.upsert_school_session(uuid, text, text, timestamptz, timestamptz)',
    'public.delete_school_session(uuid, text)'
  ] loop
    execute format('revoke execute on function %s from public, anon, authenticated', f);
    execute format('grant execute on function %s to service_role', f);
  end loop;
end $$;
