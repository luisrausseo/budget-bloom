create or replace function public.get_budget_dashboard(
    p_household_id bigint, p_month_start date, p_month_end date
) returns jsonb
language sql stable security definer set search_path = public as $$
    select jsonb_build_object(
        'household', (
            select to_jsonb(h) from public.households h where h.id = p_household_id
        ),
        'people', coalesce((
            select jsonb_agg(to_jsonb(p) order by p.name)
            from public.people p where p.household_id = p_household_id
        ), '[]'::jsonb),
        'categories', coalesce((
            select jsonb_agg(to_jsonb(c) order by c.sort_order, c.name)
            from public.categories c where c.household_id = p_household_id
        ), '[]'::jsonb),
        'entries', coalesce((
            select jsonb_agg(
                to_jsonb(e) || jsonb_build_object(
                    'people', jsonb_build_object('name', p.name),
                    'categories', jsonb_build_object('name', c.name)
                ) order by e.entry_date desc, e.id desc
            )
            from public.budget_entries e
            join public.people p on p.id = e.person_id
            join public.categories c on c.id = e.category_id
            where e.household_id = p_household_id and e.entry_date <= p_month_end
        ), '[]'::jsonb),
        'completions', coalesce((
            select jsonb_agg(jsonb_build_object('entry_id', ec.entry_id))
            from public.entry_completions ec
            where ec.household_id = p_household_id and ec.month = p_month_start
        ), '[]'::jsonb)
    );
$$;

revoke execute on function public.get_budget_dashboard(bigint, date, date)
from public, anon, authenticated;
grant execute on function public.get_budget_dashboard(bigint, date, date) to service_role;

create or replace function public.set_budget_entry_completion(
    p_entry_id bigint, p_household_id bigint, p_month date, p_completed boolean
) returns boolean
language plpgsql security definer set search_path = public as $$
begin
    if not exists (
        select 1 from public.budget_entries
        where id = p_entry_id and household_id = p_household_id
    ) then return false; end if;
    if p_completed then
        insert into public.entry_completions (entry_id, household_id, month)
        values (p_entry_id, p_household_id, date_trunc('month', p_month)::date)
        on conflict (entry_id, month) do nothing;
    else
        delete from public.entry_completions
        where entry_id = p_entry_id and household_id = p_household_id
          and month = date_trunc('month', p_month)::date;
    end if;
    return true;
end;
$$;

revoke execute on function public.set_budget_entry_completion(bigint, bigint, date, boolean)
from public, anon, authenticated;
grant execute on function public.set_budget_entry_completion(bigint, bigint, date, boolean) to service_role;
