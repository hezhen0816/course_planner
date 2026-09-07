-- Tighten table-level grants. RLS already blocks anon (no policies) and scopes
-- authenticated users to their own rows; this removes privileges the app never
-- needs so a future policy mistake cannot expose writes to anonymous clients.
-- The worker uses the service role and is unaffected.

revoke insert, update, delete, truncate, references, trigger
  on public.user_settings, public.monitored_courses, public.system_logs, public.email_test_requests
  from anon;

revoke truncate, references, trigger
  on public.user_settings, public.monitored_courses, public.system_logs, public.email_test_requests
  from authenticated;
