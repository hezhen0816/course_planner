begin;

create index if not exists course_meetings_user_id_idx
  on public.course_meetings (user_id);

create index if not exists course_meetings_course_id_idx
  on public.course_meetings (course_id);

drop policy if exists "使用者只能查閱自己的資料" on public.user_data;
create policy "使用者只能查閱自己的資料"
  on public.user_data
  for select
  using ((select auth.uid()) = user_id);

drop policy if exists "使用者只能新增自己的資料" on public.user_data;
create policy "使用者只能新增自己的資料"
  on public.user_data
  for insert
  with check ((select auth.uid()) = user_id);

drop policy if exists "使用者只能更新自己的資料" on public.user_data;
create policy "使用者只能更新自己的資料"
  on public.user_data
  for update
  using ((select auth.uid()) = user_id)
  with check ((select auth.uid()) = user_id);

drop policy if exists school_accounts_select_own on public.school_accounts;
create policy school_accounts_select_own
  on public.school_accounts
  for select
  using ((select auth.uid()) = user_id);

drop policy if exists school_accounts_insert_own on public.school_accounts;
create policy school_accounts_insert_own
  on public.school_accounts
  for insert
  with check ((select auth.uid()) = user_id);

drop policy if exists school_accounts_update_own on public.school_accounts;
create policy school_accounts_update_own
  on public.school_accounts
  for update
  using ((select auth.uid()) = user_id)
  with check ((select auth.uid()) = user_id);

drop policy if exists sync_states_select_own on public.sync_states;
create policy sync_states_select_own
  on public.sync_states
  for select
  using ((select auth.uid()) = user_id);

drop policy if exists sync_states_insert_own on public.sync_states;
create policy sync_states_insert_own
  on public.sync_states
  for insert
  with check ((select auth.uid()) = user_id);

drop policy if exists sync_states_update_own on public.sync_states;
create policy sync_states_update_own
  on public.sync_states
  for update
  using ((select auth.uid()) = user_id)
  with check ((select auth.uid()) = user_id);

drop policy if exists courses_select_own on public.courses;
create policy courses_select_own
  on public.courses
  for select
  using ((select auth.uid()) = user_id);

drop policy if exists courses_insert_own on public.courses;
create policy courses_insert_own
  on public.courses
  for insert
  with check ((select auth.uid()) = user_id);

drop policy if exists courses_update_own on public.courses;
create policy courses_update_own
  on public.courses
  for update
  using ((select auth.uid()) = user_id)
  with check ((select auth.uid()) = user_id);

drop policy if exists courses_delete_own on public.courses;
create policy courses_delete_own
  on public.courses
  for delete
  using ((select auth.uid()) = user_id);

drop policy if exists course_meetings_select_own on public.course_meetings;
create policy course_meetings_select_own
  on public.course_meetings
  for select
  using ((select auth.uid()) = user_id);

drop policy if exists course_meetings_insert_own on public.course_meetings;
create policy course_meetings_insert_own
  on public.course_meetings
  for insert
  with check ((select auth.uid()) = user_id);

drop policy if exists course_meetings_update_own on public.course_meetings;
create policy course_meetings_update_own
  on public.course_meetings
  for update
  using ((select auth.uid()) = user_id)
  with check ((select auth.uid()) = user_id);

drop policy if exists course_meetings_delete_own on public.course_meetings;
create policy course_meetings_delete_own
  on public.course_meetings
  for delete
  using ((select auth.uid()) = user_id);

commit;
