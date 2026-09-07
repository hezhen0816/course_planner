begin;

revoke all on function public.normalize_user_data_content_v2() from public;
revoke execute on function public.normalize_user_data_content_v2() from anon, authenticated;
grant execute on function public.normalize_user_data_content_v2() to service_role;

commit;
