create table if not exists public.history_import_snapshots (
  profile_key text primary key,
  school_account text not null,
  student_name text,
  payload jsonb not null,
  imported_at timestamptz not null default timezone('utc', now()),
  updated_at timestamptz not null default timezone('utc', now())
);

create index if not exists history_import_snapshots_imported_at_idx
  on public.history_import_snapshots (imported_at desc);

drop trigger if exists trg_history_import_snapshots_updated_at on public.history_import_snapshots;
create trigger trg_history_import_snapshots_updated_at
before update on public.history_import_snapshots
for each row
execute function public.set_updated_at();

alter table public.history_import_snapshots enable row level security;

drop policy if exists "service role only" on public.history_import_snapshots;
create policy "service role only"
on public.history_import_snapshots
for all
using (auth.role() = 'service_role')
with check (auth.role() = 'service_role');
