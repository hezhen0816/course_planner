drop policy if exists "service role only" on public.history_import_snapshots;
create policy "service role only"
on public.history_import_snapshots
for all
using ((select auth.role()) = 'service_role')
with check ((select auth.role()) = 'service_role');
