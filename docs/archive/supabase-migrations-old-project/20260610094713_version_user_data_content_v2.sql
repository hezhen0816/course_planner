alter table public.user_data
  add column if not exists content_version integer not null default 2,
  add column if not exists legacy_content jsonb,
  add column if not exists migrated_at timestamptz,
  add column if not exists last_writer text;

update public.user_data
set legacy_content = content
where legacy_content is null
  and content is not null;

update public.user_data
set
  content = coalesce(content, '{}'::jsonb) || jsonb_build_object(
    'schemaVersion', 2,
    'semesters', coalesce(content->'semesters', '[]'::jsonb),
    'targets', coalesce(content->'targets', '{}'::jsonb),
    'settings', coalesce(content->'settings', '{}'::jsonb),
    'requirementSets', coalesce(content->'requirementSets', '[]'::jsonb),
    'pendingRequirements', coalesce(content->'pendingRequirements', '[]'::jsonb),
    'historyRecords', coalesce(content->'historyRecords', '[]'::jsonb)
  ),
  content_version = 2,
  migrated_at = coalesce(migrated_at, timezone('utc', now())),
  last_writer = coalesce(last_writer, 'migration')
where content is not null;

create or replace function public.normalize_user_data_content_v2()
returns trigger
language plpgsql
security definer
set search_path = public
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

drop trigger if exists trg_user_data_normalize_content_v2 on public.user_data;
create trigger trg_user_data_normalize_content_v2
before insert or update of content on public.user_data
for each row
execute function public.normalize_user_data_content_v2();

comment on column public.user_data.content_version is 'Version of the planner JSON contract stored in content.';
comment on column public.user_data.legacy_content is 'First backup of pre-v2 planner content before migration or first normalized write.';
comment on column public.user_data.last_writer is 'Best-effort writer label used to audit mixed Web/iOS clients.';
