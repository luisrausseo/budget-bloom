alter table public.budget_entries
    add column if not exists recurring_until date;

alter table public.budget_entries
    add constraint budget_entries_recurring_until_month_start
    check (recurring_until is null or recurring_until = date_trunc('month', recurring_until)::date);
