# Budget Bloom

A FastAPI + Supabase household budget dashboard.

## Repository layout

```text
app.py                 Main FastAPI application
admin.py               Local admin application
translations.py        Language strings and helpers
assets/                Source artwork, including the logo
sql/migrations/        Database setup and upgrade scripts
sql/tests/             Database regression checks
static/                Browser JavaScript and CSS
templates/             Jinja templates
tests/                 Python and browser tests
```

## Run locally

1. Activate the prepared environment: `conda activate budget-bloom`
2. Copy `.env.example` to `.env` and add your Supabase service-role key.
3. Start the app: `uvicorn app:app --reload`
4. Open `http://127.0.0.1:8000`

## Database setup

For a fresh database, run these SQL files in order in the Supabase SQL editor:

1. `sql/migrations/supabase_migration.sql`
2. `sql/migrations/add_entry_category.sql`
3. `sql/migrations/normalize_entry_categories.sql`
4. `sql/migrations/add_recurrence_end_month.sql`
5. `sql/migrations/add_category_emojis.sql`
6. `sql/migrations/add_accounts_and_sessions.sql`
7. `sql/migrations/add_household_invitations.sql`
8. `sql/migrations/harden_authentication.sql`
9. `sql/migrations/add_dashboard_rpc.sql`
10. `sql/migrations/add_performance_indexes.sql`
11. `sql/migrations/add_admin_dashboard.sql`
12. `sql/migrations/add_household_grocery_list.sql`
13. `sql/migrations/add_monthly_entry_overrides.sql`
14. `sql/migrations/add_account_language.sql`

They create month-specific completion records and the normalized category list.

Recurring entries use the original values in each following month. Editing one
occurrence changes only the selected month (including its amount, description,
person, category, type, or day). Deleting a recurring entry removes the selected
month and all following months, preserving earlier occurrences and completions.
Apply `sql/migrations/add_monthly_entry_overrides.sql` before deploying this version, then reload
the app. It adds monthly overrides and new RPCs without rewriting existing entries.
Previously overwritten or deleted history cannot be reconstructed by this change.

## Tests

Run the Python tests from the repository root:

```sh
python -m unittest discover -s tests -p 'test_*.py'
```

After applying the migrations, run `sql/tests/monthly_recurrence.sql` in the
Supabase SQL editor to check recurring-entry behavior. It uses synthetic data
and rolls back its transaction. SQL files in `sql/tests/` are tests, not migrations.

## Outbound proxy

Supabase requests connect directly during local development. On PythonAnywhere,
the app detects the platform environment and automatically uses
`http://proxy.server:3128`. Set `OUTBOUND_HTTP_PROXY` only to override this
behavior for another hosting environment.

## Language preference

Run `sql/migrations/add_account_language.sql` in Supabase before deploying this version, then
reload the app. Choose **Account → Language → English / Español → Apply**.
The preference is stored on the account and applies across sessions and devices;
existing and new accounts default to English. A non-sensitive cookie also keeps
the sign-in screen in the last selected language on that browser. Account data
always takes priority after signing in. User-entered names and content are not translated.

Rollback: deploy the previous app code. The additional database column can safely
remain; its optional removal is documented in the migration file.

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

## Install Budget Bloom

Use your deployed **HTTPS** site (localhost also supports development).

- **Android:** Open the site in Chrome, then choose **Install app** or
  **Add to Home screen** from the browser menu and follow the prompts.
- **iPhone:** Open the site in Safari, tap **Share → Add to Home Screen**,
  enable **Open as Web App** if offered, then tap **Add**.

Launch the Budget Bloom icon to open the app in standalone mode. Sign in as
usual. Budget data, account settings, and groceries still require an internet
connection. Offline editing is outside this change: losing connectivity shows
a generic offline message and clears the visible page rather than retaining
financial information. Reconnect and choose **Try again** to reload from the
server. Unsaved form input is lost when going offline.

The root `/manifest.webmanifest` and `/sw.js` routes must reach FastAPI on your
existing deployment. The worker has scope `/`; no hosting or database changes
are required. Only explicitly listed public CSS, JavaScript, icons and the
static offline page enter a versioned cache. Authentication changes notify other
open tabs to fetch a fresh page, without sharing account data. Dynamic responses use
`Cache-Control: no-store, private`. Asset content changes generate a new cache
version; activation deletes older Budget Bloom static caches. There is no
background sync, persistent budget storage, or Supabase access in the worker.

Additional regression checks (Node and Playwright are development tools only):

```sh
node tests/pwa_worker.cjs
node tests/monthly_entry_form.cjs
python tests/ux_browser.py
python tests/pwa_browser.py
```

Install Playwright and its Chromium browser locally if needed:
`python -m pip install playwright && python -m playwright install chromium`.
The browser checks use synthetic accounts and mocked database responses;
they do not access Supabase. To regenerate icons from the original artwork,
install Pillow locally and run `python scripts/build_pwa_icons.py`.

Before accepting on the deployed HTTPS domain, check Android and iPhone
installation, standalone launch, and icon cropping; confirm worker scope `/`
and manifest/worker content types in developer tools. View a budget and account
page, go offline, and try reload and Back: only the offline message should be
shown. Reconnect, log out, sign in to a different account, and check Back and
other open tabs. Cache Storage must contain only public assets; no dynamic
pages, financial data, cookies, or tokens. Ensure your reverse proxy/CDN honors
`no-store` on dynamic responses and does not override the existing CSP.
