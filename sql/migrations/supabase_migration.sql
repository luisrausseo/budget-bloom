create table if not exists public.entry_completions (
    entry_id bigint not null references public.budget_entries(id) on delete cascade,
    household_id bigint not null references public.households(id) on delete cascade,
    month date not null check (month = date_trunc('month', month)::date),
    created_at timestamptz not null default now(),
    primary key (entry_id, month)
);

create index if not exists entry_completions_household_month_idx
    on public.entry_completions (household_id, month);

alter table public.entry_completions enable row level security;
