create table if not exists public.moodle_assignment_snapshots (
  profile_key text primary key,
  school_account text not null,
  payload jsonb not null,
  synced_at timestamptz not null default timezone('utc', now()),
  updated_at timestamptz not null default timezone('utc', now())
);

create index if not exists moodle_assignment_snapshots_synced_at_idx
  on public.moodle_assignment_snapshots (synced_at desc);

drop trigger if exists trg_moodle_assignment_snapshots_updated_at on public.moodle_assignment_snapshots;
create trigger trg_moodle_assignment_snapshots_updated_at
before update on public.moodle_assignment_snapshots
for each row
execute function public.set_updated_at();

alter table public.moodle_assignment_snapshots enable row level security;

drop policy if exists "service role only" on public.moodle_assignment_snapshots;
create policy "service role only"
on public.moodle_assignment_snapshots
for all
using ((select auth.role()) = 'service_role')
with check ((select auth.role()) = 'service_role');
