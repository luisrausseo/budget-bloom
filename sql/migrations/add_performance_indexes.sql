create index if not exists budget_entries_household_date_idx
    on public.budget_entries(household_id, entry_date desc);

create index if not exists people_household_name_idx
    on public.people(household_id, name);

create index if not exists account_invitations_used_by_account_idx
    on public.account_invitations(used_by_account_id);
