-- myNTUST GPA API token 原本明文存在 public.user_data.content.settings.gpaApi（前端可讀）。
-- 改為與校務帳密相同的做法：密文存 app_private，只有 service_role 可經 RPC 存取。
create table if not exists app_private.gpa_api_keys (
  user_id uuid not null,
  api_key_ciphertext text not null,
  enabled boolean default true not null,
  key_version integer default 1 not null,
  created_at timestamptz default timezone('utc'::text, now()) not null,
  updated_at timestamptz default timezone('utc'::text, now()) not null,
  constraint gpa_api_keys_pkey primary key (user_id),
  constraint gpa_api_keys_user_id_fkey foreign key (user_id) references auth.users(id) on delete cascade
);

alter table app_private.gpa_api_keys enable row level security;
drop policy if exists gpa_api_keys_service_role_only on app_private.gpa_api_keys;
create policy gpa_api_keys_service_role_only on app_private.gpa_api_keys for all
  using ((select auth.role()) = 'service_role') with check ((select auth.role()) = 'service_role');
drop trigger if exists trg_gpa_api_keys_updated_at on app_private.gpa_api_keys;
create trigger trg_gpa_api_keys_updated_at before update on app_private.gpa_api_keys
  for each row execute function public.set_updated_at();
revoke all on app_private.gpa_api_keys from public, anon, authenticated;
grant select, insert, update, delete on app_private.gpa_api_keys to service_role;

create or replace function public.get_gpa_api_key(p_user_id uuid)
returns table(api_key_ciphertext text, enabled boolean, key_version integer, updated_at timestamptz)
language sql set search_path to ''
as $$
  select k.api_key_ciphertext, k.enabled, k.key_version, k.updated_at
  from app_private.gpa_api_keys as k
  where k.user_id = p_user_id
  limit 1;
$$;

create or replace function public.upsert_gpa_api_key(
  p_user_id uuid, p_api_key_ciphertext text, p_enabled boolean default true, p_key_version integer default 1)
returns void language sql set search_path to ''
as $$
  insert into app_private.gpa_api_keys (user_id, api_key_ciphertext, enabled, key_version)
  values (p_user_id, p_api_key_ciphertext, coalesce(p_enabled, true), coalesce(p_key_version, 1))
  on conflict (user_id) do update
  set api_key_ciphertext = excluded.api_key_ciphertext,
      enabled = excluded.enabled,
      key_version = excluded.key_version;
$$;

create or replace function public.delete_gpa_api_key(p_user_id uuid)
returns void language sql set search_path to ''
as $$
  delete from app_private.gpa_api_keys as k where k.user_id = p_user_id;
$$;

do $$
declare f text;
begin
  foreach f in array array[
    'public.get_gpa_api_key(uuid)',
    'public.upsert_gpa_api_key(uuid, text, boolean, integer)',
    'public.delete_gpa_api_key(uuid)'
  ] loop
    execute format('revoke execute on function %s from public, anon, authenticated', f);
    execute format('grant execute on function %s to service_role', f);
  end loop;
end $$;
