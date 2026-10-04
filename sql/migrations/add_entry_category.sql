alter table public.budget_entries
    add column if not exists category text not null default 'Uncategorized';

alter table public.budget_entries
    add constraint budget_entries_category_not_blank
    check (length(btrim(category)) > 0) not valid;

alter table public.budget_entries
    validate constraint budget_entries_category_not_blank;
