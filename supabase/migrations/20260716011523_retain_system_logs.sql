-- Keep Live Console history bounded on the Free plan.
-- pg_cron evaluates this schedule in UTC: 03:15 UTC = 11:15 Asia/Taipei.
create extension if not exists pg_cron with schema pg_catalog;

grant usage on schema cron to postgres;
grant all privileges on all tables in schema cron to postgres;

select cron.schedule(
  'prune-system-logs',
  '15 3 * * *',
  $$
    delete from public.system_logs
    where created_at < now() - interval '7 days';

    delete from cron.job_run_details
    where end_time < now() - interval '30 days';
  $$
);

select cron.schedule(
  'analyze-system-logs',
  '30 3 * * *',
  'vacuum (analyze) public.system_logs'
);
