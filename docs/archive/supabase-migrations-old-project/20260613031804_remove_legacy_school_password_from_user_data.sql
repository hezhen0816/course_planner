begin;

update public.user_data
set
  content = jsonb_set(
    coalesce(content, '{}'::jsonb),
    '{settings}',
    (
      coalesce(content->'settings', '{}'::jsonb)
      - 'school_password'
      - 'schoolCredentials'
    ),
    true
  ),
  last_writer = 'migration-remove-legacy-school-password',
  updated_at = timezone('utc', now())
where content #>> '{settings,school_password}' is not null
   or content #> '{settings,schoolCredentials}' is not null;

update public.user_data
set legacy_content = jsonb_set(
  legacy_content,
  '{settings}',
  (
    coalesce(legacy_content->'settings', '{}'::jsonb)
    - 'school_password'
    - 'schoolCredentials'
  ),
  true
)
where legacy_content is not null
  and (
    legacy_content #>> '{settings,school_password}' is not null
    or legacy_content #> '{settings,schoolCredentials}' is not null
  );

commit;
