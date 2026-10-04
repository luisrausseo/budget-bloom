-- Synthetic data only. The entire test transaction rolls back.
begin;
do $$
declare h bigint; other_h bigint; p bigint; p2 bigint; c bigint; c2 bigint; e bigint; single_id bigint;
    item jsonb; m date; ok boolean;
begin
    insert into public.households(name) values('Recurrence test '||gen_random_uuid()) returning id into h;
    insert into public.households(name) values('Other recurrence test '||gen_random_uuid()) returning id into other_h;
    insert into public.people(household_id,name) values(h,'Person A') returning id into p;
    insert into public.people(household_id,name) values(h,'Person B') returning id into p2;
    insert into public.categories(household_id,name) values(h,'Test category A') returning id into c;
    insert into public.categories(household_id,name) values(h,'Test category B') returning id into c2;
    insert into public.budget_entries(household_id,person_id,category_id,entry_type,description,amount,entry_date,recurring_monthly)
        values(h,p,c,'expense','Original',60,'2026-01-31',true) returning id into e;
    perform public.set_budget_month_completion(e,h,'2026-01-01',true);
    perform public.set_budget_month_completion(e,h,'2026-03-01',true);

    ok:=public.edit_budget_entry_month(e,h,'2026-03-01',p2,c2,'income','March only',75,'2026-03-20',false);
    if not ok then raise exception 'Edit failed'; end if;
    foreach m in array array['2026-01-01'::date,'2026-02-01'::date,'2026-03-01'::date,'2026-04-01'::date] loop
        select value into item from jsonb_array_elements(public.get_budget_dashboard_monthly(h,m,(m+interval '1 month - 1 day')::date)->'entries') where (value->>'id')::bigint=e;
        if item is null then raise exception 'Missing occurrence %',m; end if;
        if m='2026-03-01' then
            if item->>'description'<>'March only' or (item->>'amount')::numeric<>75 or (item->>'person_id')::bigint<>p2
                or item->>'entry_type'<>'income' or item->'people'->>'name'<>'Person B'
                or item->'categories'->>'name'<>'Test category B' or item->>'entry_date'<>'2026-03-20'
                or not (item->>'completed')::boolean then raise exception 'Monthly override not resolved'; end if;
        else
            if item->>'description'<>'Original' or (item->>'amount')::numeric<>60 or (item->>'person_id')::bigint<>p
                then raise exception 'Edit leaked into another month %',m; end if;
        end if;
        if m='2026-02-01' and item->>'entry_date'<>'2026-02-28' then raise exception 'Month-end date not clamped'; end if;
        if m='2026-04-01' and item->>'entry_date'<>'2026-04-30' then raise exception 'Month-end date not clamped'; end if;
    end loop;
    -- Editing the first occurrence must not change the template for later months.
    perform public.edit_budget_entry_month(e,h,'2026-01-01',p,c,'expense','January only',10,'2026-01-15',true);
    if (select amount from public.budget_entries where id=e)<>60 then raise exception 'Template changed'; end if;
    -- A second edit updates the same override instead of creating a duplicate.
    perform public.edit_budget_entry_month(e,h,'2026-03-01',p2,c2,'income','March only',76,'2026-03-21',true);
    if (select count(*) from public.entry_month_overrides where entry_id=e and month='2026-03-01')<>1 then raise exception 'Duplicate overrides'; end if;
    perform public.edit_budget_entry_month(e,h,'2026-04-01',p,c,'expense','Future override',88,'2026-04-10',true);

    if public.edit_budget_entry_month(e,other_h,'2026-03-01',p,c,'expense','Cross household',1,'2026-03-10',true)
       or public.delete_budget_entry_from_month(e,other_h,'2026-03-01')
       or public.set_budget_month_completion(e,other_h,'2026-03-01',false) then raise exception 'Cross-household access'; end if;
    begin
        perform public.edit_budget_entry_month(e,h,'2026-03-01',p,c,'expense','Wrong date',1,'2026-04-01',true);
        raise exception 'Wrong month allowed';
    exception when others then
        if SQLERRM<>'The occurrence date must stay in the selected month' then raise; end if;
    end;

    if not public.delete_budget_entry_from_month(e,h,'2026-03-01') then raise exception 'Delete failed'; end if;
    foreach m in array array['2026-03-01'::date,'2026-04-01'::date,'2027-01-01'::date] loop
        if exists(select 1 from jsonb_array_elements(public.get_budget_dashboard_monthly(h,m,(m+interval '1 month - 1 day')::date)->'entries') where (value->>'id')::bigint=e)
            then raise exception 'Deleted occurrence still visible %',m; end if;
    end loop;
    select value into item from jsonb_array_elements(public.get_budget_dashboard_monthly(h,'2026-01-01','2026-01-31')->'entries') where (value->>'id')::bigint=e;
    if (item->>'amount')::numeric<>10 or not (item->>'completed')::boolean then raise exception 'Earlier history changed'; end if;
    if public.edit_budget_entry_month(e,h,'2026-04-01',p,c,'expense','Resurrect',1,'2026-04-01',true)
       or public.set_budget_month_completion(e,h,'2026-04-01',true) then raise exception 'Deleted occurrence can be modified'; end if;
    perform public.edit_budget_entry_month(e,h,'2026-02-01',p,c,'expense','Earlier edit',55,'2026-02-10',true);
    if (select recurring_until from public.budget_entries where id=e)<>'2026-02-01' then raise exception 'Earlier edit restarted series'; end if;
    perform public.delete_budget_entry_from_month(e,h,'2026-01-01');
    if jsonb_array_length(public.get_budget_dashboard_monthly(h,'2026-01-01','2026-01-31')->'entries')<>0 then raise exception 'Deleting first month failed'; end if;

    insert into public.budget_entries(household_id,person_id,category_id,entry_type,description,amount,entry_date,recurring_monthly)
        values(h,p,c,'expense','One off',9,'2026-07-16',false) returning id into single_id;
    if public.delete_budget_entry_from_month(single_id,h,'2026-08-01') then raise exception 'Deleted non-occurrence'; end if;
    perform public.edit_budget_entry_month(single_id,h,'2026-07-01',p,c,'expense','One off edited',12,'2026-07-17',false);
    if (select amount from public.budget_entries where id=single_id)<>12 then raise exception 'Nonrecurring edit failed'; end if;
    perform public.delete_budget_entry_from_month(single_id,h,'2026-07-01');
    if exists(select 1 from public.budget_entries where id=single_id) then raise exception 'Nonrecurring delete failed'; end if;
    if has_function_privilege('anon','public.edit_budget_entry_month(bigint,bigint,date,bigint,bigint,text,text,numeric,date,boolean)','execute')
       or has_function_privilege('authenticated','public.delete_budget_entry_from_month(bigint,bigint,date)','execute')
       or has_table_privilege('anon','public.entry_month_overrides','select') then raise exception 'Public access to overrides'; end if;
end $$;
select 'Monthly edits, cutoff deletion, history, dates, completion, and isolation passed' as result;
rollback;
