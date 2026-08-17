# Budget Bloom

A FastAPI + Supabase household budget dashboard.

## Run locally

1. Activate the prepared environment: `conda activate budget-bloom`
2. Copy `.env.example` to `.env` and add your Supabase service-role key.
3. Start the app: `uvicorn app:app --reload`
4. Open `http://127.0.0.1:8000`

## Database setup

For a fresh database, run these SQL files in order in the Supabase SQL editor:

1. `supabase_migration.sql`
2. `add_entry_category.sql`
3. `normalize_entry_categories.sql`
4. `add_recurrence_end_month.sql`
5. `add_category_emojis.sql`
6. `add_accounts_and_sessions.sql`
7. `add_household_invitations.sql`
8. `harden_authentication.sql`
9. `add_dashboard_rpc.sql`
10. `add_performance_indexes.sql`
11. `add_admin_dashboard.sql`

They create month-specific completion records and the normalized category list.

## Outbound proxy

Supabase requests connect directly during local development. On PythonAnywhere,
the app detects the platform environment and automatically uses
`http://proxy.server:3128`. Set `OUTBOUND_HTTP_PROXY` only to override this
behavior for another hosting environment.

## Local admin application

Run the separate admin UI on loopback only:

`uvicorn admin:admin_app --host 127.0.0.1 --port 8001`

Then open `http://127.0.0.1:8001`. The admin app returns 404 for non-loopback
clients and whenever it detects PythonAnywhere.

The PythonAnywhere hostname is also added automatically to the trusted-host
list. Custom domains must be added to `ALLOWED_HOSTS` as comma-separated names.
`FORCE_HTTPS` is automatically bypassed on PythonAnywhere to avoid a redirect
loop behind its TLS-terminating load balancer; secure cookies and HSTS remain
enabled when `COOKIE_SECURE=true`.

The service-role key is used only by the FastAPI server. Never expose it to browser code or commit `.env`.
