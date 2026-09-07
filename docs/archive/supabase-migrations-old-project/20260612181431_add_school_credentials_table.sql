begin;

create table if not exists public.school_credentials (
  user_id uuid primary key references auth.users(id) on delete cascade,
  school_account text not null,
  password_ciphertext text not null,
  key_version integer not null default 1,
  last_verified_at timestamptz,
  created_at timestamptz not null default timezone('utc', now()),
  updated_at timestamptz not null default timezone('utc', now())
);

create index if not exists school_credentials_school_account_idx
  on public.school_credentials (school_account);

drop trigger if exists trg_school_credentials_updated_at on public.school_credentials;
create trigger trg_school_credentials_updated_at
before update on public.school_credentials
for each row
execute function public.set_updated_at();

alter table public.school_credentials enable row level security;

drop policy if exists school_credentials_service_role_only on public.school_credentials;
create policy school_credentials_service_role_only
  on public.school_credentials
  for all
  using ((select auth.role()) = 'service_role')
  with check ((select auth.role()) = 'service_role');

revoke all on table public.school_credentials from anon, authenticated;
grant select, insert, update, delete on table public.school_credentials to service_role;

insert into public.school_credentials (
  user_id,
  school_account,
  password_ciphertext,
  key_version,
  last_verified_at
)
select
  user_id,
  coalesce(
    nullif(content #>> '{settings,schoolCredentials,username}', ''),
    nullif(content #>> '{settings,school_account}', '')
  ) as school_account,
  content #>> '{settings,schoolCredentials,passwordCiphertext}' as password_ciphertext,
  case
    when (content #>> '{settings,schoolCredentials,version}') ~ '^\d+$'
      then (content #>> '{settings,schoolCredentials,version}')::integer
    else 1
  end as key_version,
  nullif(content #>> '{settings,schoolCredentials,updatedAt}', '')::timestamptz as last_verified_at
from public.user_data
where nullif(content #>> '{settings,schoolCredentials,passwordCiphertext}', '') is not null
  and coalesce(
    nullif(content #>> '{settings,schoolCredentials,username}', ''),
    nullif(content #>> '{settings,school_account}', '')
  ) is not null
on conflict (user_id) do update
set
  school_account = excluded.school_account,
  password_ciphertext = excluded.password_ciphertext,
  key_version = excluded.key_version,
  last_verified_at = excluded.last_verified_at;

update public.user_data
set
  content = jsonb_set(
    coalesce(content, '{}'::jsonb),
    '{settings}',
    (
      coalesce(content->'settings', '{}'::jsonb)
      - 'schoolCredentials'
    ),
    true
  ),
  last_writer = 'migration'
where content ? 'settings'
  and content->'settings' ? 'schoolCredentials';

-- Legacy settings.school_password is plaintext and cannot be safely converted
-- inside SQL because the backend encryption key is intentionally not in the DB.
-- The backend promotes and removes it on the next authenticated credential use.

comment on table public.school_credentials is 'Encrypted school portal credentials for backend-only sync and official selection session recovery.';
comment on column public.school_credentials.password_ciphertext is 'Fernet ciphertext encrypted by the backend credentials secret; never returned to public clients.';

commit;
