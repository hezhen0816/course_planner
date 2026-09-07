begin;

create schema if not exists app_private;

revoke all on schema app_private from public, anon, authenticated;
grant usage on schema app_private to service_role;

create table if not exists app_private.school_credentials (
  user_id uuid primary key references auth.users(id) on delete cascade,
  school_account text not null,
  password_ciphertext text not null,
  key_version integer not null default 1,
  last_verified_at timestamptz,
  created_at timestamptz not null default timezone('utc', now()),
  updated_at timestamptz not null default timezone('utc', now())
);

drop trigger if exists trg_school_credentials_updated_at on app_private.school_credentials;
create trigger trg_school_credentials_updated_at
before update on app_private.school_credentials
for each row
execute function public.set_updated_at();

alter table app_private.school_credentials enable row level security;

drop policy if exists school_credentials_service_role_only on app_private.school_credentials;
create policy school_credentials_service_role_only
  on app_private.school_credentials
  for all
  using ((select auth.role()) = 'service_role')
  with check ((select auth.role()) = 'service_role');

revoke all on table app_private.school_credentials from public, anon, authenticated;
grant select, insert, update, delete on table app_private.school_credentials to service_role;

insert into app_private.school_credentials (
  user_id,
  school_account,
  password_ciphertext,
  key_version,
  last_verified_at,
  created_at,
  updated_at
)
select
  user_id,
  school_account,
  password_ciphertext,
  key_version,
  last_verified_at,
  created_at,
  updated_at
from public.school_credentials
on conflict (user_id) do update
set
  school_account = excluded.school_account,
  password_ciphertext = excluded.password_ciphertext,
  key_version = excluded.key_version,
  last_verified_at = excluded.last_verified_at,
  updated_at = excluded.updated_at;

delete from public.school_credentials;

revoke all on table public.school_credentials from anon, authenticated, service_role;
comment on table public.school_credentials is 'Deprecated empty compatibility table. Credentials moved to app_private.school_credentials.';

create or replace function public.get_school_credentials(
  p_user_id uuid
)
returns table (
  school_account text,
  password_ciphertext text,
  key_version integer,
  last_verified_at timestamptz
)
language sql
security invoker
set search_path = ''
as $$
  select
    c.school_account,
    c.password_ciphertext,
    c.key_version,
    c.last_verified_at
  from app_private.school_credentials as c
  where c.user_id = p_user_id
  limit 1;
$$;

create or replace function public.upsert_school_credentials(
  p_user_id uuid,
  p_school_account text,
  p_password_ciphertext text,
  p_key_version integer default 1,
  p_last_verified_at timestamptz default timezone('utc', now())
)
returns void
language sql
security invoker
set search_path = ''
as $$
  insert into app_private.school_credentials (
    user_id,
    school_account,
    password_ciphertext,
    key_version,
    last_verified_at
  )
  values (
    p_user_id,
    p_school_account,
    p_password_ciphertext,
    coalesce(p_key_version, 1),
    p_last_verified_at
  )
  on conflict (user_id) do update
  set
    school_account = excluded.school_account,
    password_ciphertext = excluded.password_ciphertext,
    key_version = excluded.key_version,
    last_verified_at = excluded.last_verified_at;
$$;

create or replace function public.delete_school_credentials(
  p_user_id uuid
)
returns void
language sql
security invoker
set search_path = ''
as $$
  delete from app_private.school_credentials as c
  where c.user_id = p_user_id;
$$;

revoke all on function public.get_school_credentials(uuid) from public, anon, authenticated;
revoke all on function public.upsert_school_credentials(uuid, text, text, integer, timestamptz) from public, anon, authenticated;
revoke all on function public.delete_school_credentials(uuid) from public, anon, authenticated;

grant execute on function public.get_school_credentials(uuid) to service_role;
grant execute on function public.upsert_school_credentials(uuid, text, text, integer, timestamptz) to service_role;
grant execute on function public.delete_school_credentials(uuid) to service_role;

comment on table app_private.school_credentials is 'Encrypted school portal credentials for backend-only sync and official selection session recovery.';
comment on column app_private.school_credentials.password_ciphertext is 'Fernet ciphertext encrypted by the backend credentials secret; never returned to public clients.';

commit;
