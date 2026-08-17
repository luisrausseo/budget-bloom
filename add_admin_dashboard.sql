create or replace function public.get_admin_dashboard_metrics()
returns jsonb language sql stable security definer set search_path = public as $$
select jsonb_build_object(
  'summary', jsonb_build_object(
    'households', (select count(*) from households),
    'accounts', (select count(*) from accounts),
    'active_accounts', (select count(*) from accounts where disabled_at is null),
    'disabled_accounts', (select count(*) from accounts where disabled_at is not null),
    'owners', (select count(*) from accounts where role='owner'),
    'members', (select count(*) from accounts where role='member'),
    'active_sessions', (select count(*) from account_sessions where expires_at > now()),
    'people', (select count(*) from people),
    'entries', (select count(*) from budget_entries),
    'recurring_entries', (select count(*) from budget_entries where recurring_monthly),
    'completed_this_month', (select count(*) from entry_completions where entry_completions.month=date_trunc('month',current_date)::date),
    'active_invitations', (select count(*) from account_invitations where used_at is null and expires_at>now()),
    'used_invitations', (select count(*) from account_invitations where used_at is not null),
    'expired_invitations', (select count(*) from account_invitations where used_at is null and expires_at<=now())
  ),
  'households', coalesce((select jsonb_agg(to_jsonb(x) order by x.entries desc,x.name) from (
    select h.id,h.name,count(distinct a.id) accounts,count(distinct p.id) people,
      count(distinct e.id) entries,count(distinct e.id) filter(where e.recurring_monthly) recurring,
      max(e.updated_at) last_activity
    from households h left join accounts a on a.household_id=h.id
    left join people p on p.household_id=h.id left join budget_entries e on e.household_id=h.id
    group by h.id,h.name
  ) x),'[]'::jsonb),
  'monthly_activity', coalesce((select jsonb_agg(to_jsonb(x) order by x.month_start) from (
    select series.month_start,to_char(series.month_start,'Mon YY') as label,count(e.id) as entries
    from generate_series(date_trunc('month',current_date)-interval '11 months',date_trunc('month',current_date),interval '1 month') as series(month_start)
    left join budget_entries e on date_trunc('month',e.entry_date)=series.month_start group by series.month_start
  ) x),'[]'::jsonb),
  'categories', coalesce((select jsonb_agg(to_jsonb(x) order by x.entries desc,x.name) from (
    select c.name,count(e.id) entries from categories c join budget_entries e on e.category_id=c.id
    group by c.name order by count(e.id) desc limit 10
  ) x),'[]'::jsonb),
  'security_events', coalesce((select jsonb_agg(to_jsonb(x) order by x.events desc) from (
    select event_type,count(*) events from security_audit_events
    where created_at>=now()-interval '30 days' group by event_type
  ) x),'[]'::jsonb)
);
$$;

create or replace function public.admin_create_household_account(
  p_household_name text,p_username text,p_password_hash text
) returns jsonb language plpgsql security definer set search_path=public as $$
declare new_household_id bigint; new_account_id bigint;
begin
  if exists(select 1 from households where lower(name)=lower(btrim(p_household_name))) then raise exception 'Household already exists'; end if;
  insert into households(name) values(btrim(p_household_name)) returning id into new_household_id;
  insert into accounts(household_id,username,password_hash,role)
  values(new_household_id,lower(btrim(p_username)),p_password_hash,'owner') returning id into new_account_id;
  return jsonb_build_object('household_id',new_household_id,'account_id',new_account_id);
end;
$$;

create or replace function public.admin_cleanup_expired_auth_data()
returns jsonb language plpgsql security definer set search_path=public as $$
declare removed_count integer:=0; affected integer;
begin
  delete from account_sessions where expires_at<=now(); get diagnostics affected=row_count; removed_count:=removed_count+affected;
  delete from account_invitations where used_at is null and expires_at<=now()-interval '30 days'; get diagnostics affected=row_count; removed_count:=removed_count+affected;
  delete from auth_rate_limits where window_started_at<=now()-interval '1 day'; get diagnostics affected=row_count; removed_count:=removed_count+affected;
  return jsonb_build_object('removed',removed_count);
end;
$$;

revoke execute on function public.get_admin_dashboard_metrics() from public,anon,authenticated;
revoke execute on function public.admin_create_household_account(text,text,text) from public,anon,authenticated;
revoke execute on function public.admin_cleanup_expired_auth_data() from public,anon,authenticated;
grant execute on function public.get_admin_dashboard_metrics() to service_role;
grant execute on function public.admin_create_household_account(text,text,text) to service_role;
grant execute on function public.admin_cleanup_expired_auth_data() to service_role;
