-- A recurring budget_entries row is the series template. Edits are separate
-- month-specific values; deleting an occurrence sets the series end month.
create table public.entry_month_overrides (
    entry_id bigint not null references public.budget_entries(id) on delete cascade,
    household_id bigint not null references public.households(id) on delete cascade,
    month date not null check (month = date_trunc('month', month::timestamp)::date),
    person_id bigint not null references public.people(id),
    category_id bigint not null references public.categories(id),
    entry_type text not null check (entry_type in ('income','expense')),
    description text not null check (length(btrim(description)) > 0),
    amount numeric not null check (amount > 0 and amount <> 'NaN'::numeric and amount <> 'Infinity'::numeric),
    entry_date date not null,
    updated_at timestamptz not null default now(),
    primary key (entry_id, month),
    check (entry_date >= month and entry_date < (month + interval '1 month')::date)
);
create index entry_month_overrides_household_month_idx on public.entry_month_overrides(household_id,month);
create index entry_month_overrides_person_idx on public.entry_month_overrides(person_id);
create index entry_month_overrides_category_idx on public.entry_month_overrides(category_id);
alter table public.entry_month_overrides enable row level security;
revoke all on public.entry_month_overrides from public,anon,authenticated;
grant select,insert,update,delete on public.entry_month_overrides to service_role;

create function public.budget_entry_occurs_in_month(p_date date,p_recurring boolean,p_until date,p_month date)
returns boolean language sql immutable set search_path=public as $$
    select p_date < (p_month + interval '1 month')::date
      and (p_date >= p_month or p_recurring)
      and (not p_recurring or p_until is null or p_month <= p_until);
$$;

-- A versioned reader leaves the previous RPC available during deployment.
create function public.get_budget_dashboard_monthly(p_household_id bigint,p_month_start date,p_month_end date)
returns jsonb language sql stable security definer set search_path=public as $$
    select public.get_budget_dashboard(p_household_id,p_month_start,p_month_end) || jsonb_build_object(
        'entries',coalesce((
            select jsonb_agg(to_jsonb(e) || jsonb_build_object(
                'source_entry_date',e.entry_date,
                'entry_date',coalesce(o.entry_date,
                    p_month_start + (least(extract(day from e.entry_date)::int,
                        extract(day from (p_month_start + interval '1 month - 1 day'))::int) - 1)),
                'person_id',coalesce(o.person_id,e.person_id),
                'category_id',coalesce(o.category_id,e.category_id),
                'entry_type',coalesce(o.entry_type,e.entry_type),
                'description',coalesce(o.description,e.description),
                'amount',coalesce(o.amount,e.amount),
                'updated_at',coalesce(o.updated_at,e.updated_at),
                'people',jsonb_build_object('name',p.name),
                'categories',jsonb_build_object('name',c.name),
                'recurs_in_selected_month',e.recurring_monthly,
                'month_override',o.entry_id is not null,
                'completed',exists(select 1 from public.entry_completions ec where ec.entry_id=e.id
                    and ec.household_id=e.household_id and ec.month=p_month_start)
            ) order by e.id)
            from public.budget_entries e
            left join public.entry_month_overrides o on o.entry_id=e.id and o.household_id=e.household_id and o.month=p_month_start
            join public.people p on p.id=coalesce(o.person_id,e.person_id) and p.household_id=e.household_id
            join public.categories c on c.id=coalesce(o.category_id,e.category_id) and c.household_id=e.household_id
            where e.household_id=p_household_id
              and public.budget_entry_occurs_in_month(e.entry_date,e.recurring_monthly,e.recurring_until,p_month_start)
        ),'[]'::jsonb)
    );
$$;

create function public.edit_budget_entry_month(
    p_entry_id bigint,p_household_id bigint,p_month date,p_person_id bigint,p_category_id bigint,
    p_entry_type text,p_description text,p_amount numeric,p_entry_date date,p_recurring_monthly boolean
) returns boolean language plpgsql security definer set search_path=public as $$
declare e public.budget_entries; m date:=date_trunc('month',p_month::timestamp)::date;
begin
    select * into e from public.budget_entries where id=p_entry_id and household_id=p_household_id for update;
    if not found or not public.budget_entry_occurs_in_month(e.entry_date,e.recurring_monthly,e.recurring_until,m) then return false; end if;
    if p_entry_type not in ('income','expense') or p_entry_type is null
       or p_description is null or length(btrim(p_description))=0
       or p_amount is null or p_amount<=0 or p_amount in ('NaN'::numeric,'Infinity'::numeric)
       or p_entry_date is null or p_recurring_monthly is null
       or not exists(select 1 from public.people where id=p_person_id and household_id=p_household_id)
       or not exists(select 1 from public.categories where id=p_category_id and household_id=p_household_id)
    then raise exception 'Invalid entry details'; end if;
    if e.recurring_monthly then
        if p_entry_date < m or p_entry_date >= (m+interval '1 month')::date then
            raise exception 'The occurrence date must stay in the selected month';
        end if;
        insert into public.entry_month_overrides(entry_id,household_id,month,person_id,category_id,entry_type,description,amount,entry_date)
        values(e.id,p_household_id,m,p_person_id,p_category_id,p_entry_type,btrim(p_description),p_amount,p_entry_date)
        on conflict(entry_id,month) do update set person_id=excluded.person_id,category_id=excluded.category_id,
            entry_type=excluded.entry_type,description=excluded.description,amount=excluded.amount,
            entry_date=excluded.entry_date,updated_at=now();
        -- Never change the template or recurrence end when editing an occurrence.
    else
        update public.budget_entries set person_id=p_person_id,category_id=p_category_id,entry_type=p_entry_type,
            description=btrim(p_description),amount=p_amount,entry_date=p_entry_date,
            recurring_monthly=p_recurring_monthly,recurring_until=null,updated_at=now() where id=e.id;
    end if;
    return true;
end;
$$;

create function public.delete_budget_entry_from_month(p_entry_id bigint,p_household_id bigint,p_month date)
returns boolean language plpgsql security definer set search_path=public as $$
declare e public.budget_entries; m date:=date_trunc('month',p_month::timestamp)::date;
begin
    select * into e from public.budget_entries where id=p_entry_id and household_id=p_household_id for update;
    if not found or not public.budget_entry_occurs_in_month(e.entry_date,e.recurring_monthly,e.recurring_until,m) then return false; end if;
    if e.recurring_monthly then
        -- Keep earlier occurrences, overrides and completions. Later overrides
        -- remain stored but cannot appear beyond this cutoff (including month 1).
        update public.budget_entries set recurring_until=(m-interval '1 month')::date,updated_at=now() where id=e.id;
    else
        delete from public.budget_entries where id=e.id;
    end if;
    return true;
end;
$$;

create function public.set_budget_month_completion(p_entry_id bigint,p_household_id bigint,p_month date,p_completed boolean)
returns boolean language plpgsql security definer set search_path=public as $$
declare e public.budget_entries; m date:=date_trunc('month',p_month::timestamp)::date;
begin
    select * into e from public.budget_entries where id=p_entry_id and household_id=p_household_id for update;
    if not found or not public.budget_entry_occurs_in_month(e.entry_date,e.recurring_monthly,e.recurring_until,m) then return false; end if;
    return public.set_budget_entry_completion(p_entry_id,p_household_id,m,p_completed);
end;
$$;

revoke execute on function public.budget_entry_occurs_in_month(date,boolean,date,date) from public,anon,authenticated;
revoke execute on function public.get_budget_dashboard_monthly(bigint,date,date) from public,anon,authenticated;
revoke execute on function public.edit_budget_entry_month(bigint,bigint,date,bigint,bigint,text,text,numeric,date,boolean) from public,anon,authenticated;
revoke execute on function public.delete_budget_entry_from_month(bigint,bigint,date) from public,anon,authenticated;
revoke execute on function public.set_budget_month_completion(bigint,bigint,date,boolean) from public,anon,authenticated;
grant execute on function public.budget_entry_occurs_in_month(date,boolean,date,date),
    public.get_budget_dashboard_monthly(bigint,date,date),
    public.edit_budget_entry_month(bigint,bigint,date,bigint,bigint,text,text,numeric,date,boolean),
    public.delete_budget_entry_from_month(bigint,bigint,date),
    public.set_budget_month_completion(bigint,bigint,date,boolean) to service_role;
