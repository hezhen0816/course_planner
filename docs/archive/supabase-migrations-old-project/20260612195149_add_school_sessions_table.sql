begin;

create schema if not exists app_private;

revoke all on schema app_private from public, anon, authenticated;
grant usage on schema app_private to service_role;

create table if not exists app_private.school_sessions (
  user_id uuid not null references auth.users(id) on delete cascade,
  school_account text not null,
  session_ciphertext text not null,
  key_version integer not null default 1,
  expires_at timestamptz not null,
  last_keep_alive_at timestamptz,
  created_at timestamptz not null default timezone('utc', now()),
  updated_at timestamptz not null default timezone('utc', now()),
  primary key (user_id, school_account)
);

create index if not exists school_sessions_expires_at_idx
  on app_private.school_sessions (expires_at);

drop trigger if exists trg_school_sessions_updated_at on app_private.school_sessions;
create trigger trg_school_sessions_updated_at
before update on app_private.school_sessions
for each row
execute function public.set_updated_at();

alter table app_private.school_sessions enable row level security;

drop policy if exists school_sessions_service_role_only on app_private.school_sessions;
create policy school_sessions_service_role_only
  on app_private.school_sessions
  for all
  using ((select auth.role()) = 'service_role')
  with check ((select auth.role()) = 'service_role');

revoke all on table app_private.school_sessions from public, anon, authenticated;
grant select, insert, update, delete on table app_private.school_sessions to service_role;

create or replace function public.get_school_session(
  p_user_id uuid,
  p_school_account text
)
returns table (
  school_account text,
  session_ciphertext text,
  key_version integer,
  expires_at timestamptz,
  last_keep_alive_at timestamptz
)
language sql
security invoker
set search_path = ''
as $$
  select
    s.school_account,
    s.session_ciphertext,
    s.key_version,
    s.expires_at,
    s.last_keep_alive_at
  from app_private.school_sessions as s
  where s.user_id = p_user_id
    and s.school_account = p_school_account
    and s.expires_at > timezone('utc', now())
  limit 1;
$$;

create or replace function public.upsert_school_session(
  p_user_id uuid,
  p_school_account text,
  p_session_ciphertext text,
  p_expires_at timestamptz,
  p_last_keep_alive_at timestamptz default timezone('utc', now())
)
returns void
language sql
security invoker
set search_path = ''
as $$
  insert into app_private.school_sessions (
    user_id,
    school_account,
    session_ciphertext,
    key_version,
    expires_at,
    last_keep_alive_at
  )
  values (
    p_user_id,
    p_school_account,
    p_session_ciphertext,
    1,
    p_expires_at,
    p_last_keep_alive_at
  )
  on conflict (user_id, school_account) do update
  set
    session_ciphertext = excluded.session_ciphertext,
    key_version = excluded.key_version,
    expires_at = excluded.expires_at,
    last_keep_alive_at = excluded.last_keep_alive_at;
$$;

create or replace function public.delete_school_session(
  p_user_id uuid,
  p_school_account text default null
)
returns void
language sql
security invoker
set search_path = ''
as $$
  delete from app_private.school_sessions as s
  where s.user_id = p_user_id
    and (
      p_school_account is null
      or s.school_account = p_school_account
    );
$$;

revoke all on function public.get_school_session(uuid, text) from public, anon, authenticated;
revoke all on function public.upsert_school_session(uuid, text, text, timestamptz, timestamptz) from public, anon, authenticated;
revoke all on function public.delete_school_session(uuid, text) from public, anon, authenticated;

grant execute on function public.get_school_session(uuid, text) to service_role;
grant execute on function public.upsert_school_session(uuid, text, text, timestamptz, timestamptz) to service_role;
grant execute on function public.delete_school_session(uuid, text) to service_role;

comment on schema app_private is 'Backend-only storage for sensitive Course Compass state.';
comment on table app_private.school_sessions is 'Encrypted official school portal session cookies/state for foreground keep-alive and recovery.';
comment on column app_private.school_sessions.session_ciphertext is 'Fernet ciphertext produced by the backend credentials secret; never returned to public clients.';

commit;
