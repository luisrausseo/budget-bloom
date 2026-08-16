import calendar
import getpass
import hashlib
import hmac
import logging
import os
import re
import secrets
from datetime import UTC, date, datetime, timedelta
from decimal import Decimal, InvalidOperation
from pathlib import Path
from urllib.parse import urlencode

import httpx
from dotenv import load_dotenv
from fastapi import FastAPI, Form, HTTPException, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from jinja2 import Environment, FileSystemLoader, select_autoescape
from starlette.middleware.httpsredirect import HTTPSRedirectMiddleware
from starlette.middleware.trustedhost import TrustedHostMiddleware

BASE_DIR = Path(__file__).resolve().parent
load_dotenv(BASE_DIR / ".env")

app = FastAPI(title="Monthly Budget")
allowed_hosts = [item.strip() for item in os.getenv("ALLOWED_HOSTS", "localhost,127.0.0.1").split(",") if item.strip()]
pythonanywhere_domain = os.getenv("PYTHONANYWHERE_DOMAIN", "").strip()
if not pythonanywhere_domain:
    pythonanywhere_site = os.getenv("PYTHONANYWHERE_SITE", "").strip()
    pythonanywhere_domain = pythonanywhere_site.removeprefix("www.")
if pythonanywhere_domain:
    pythonanywhere_username = os.getenv("PYTHONANYWHERE_USERNAME", getpass.getuser()).strip()
    pythonanywhere_host = f"{pythonanywhere_username}.{pythonanywhere_domain}"
    if pythonanywhere_host not in allowed_hosts:
        allowed_hosts.append(pythonanywhere_host)
app.add_middleware(TrustedHostMiddleware, allowed_hosts=allowed_hosts)
if os.getenv("FORCE_HTTPS", "false").lower() == "true":
    app.add_middleware(HTTPSRedirectMiddleware)
app.mount("/static", StaticFiles(directory=BASE_DIR / "static"), name="static")
templates = Environment(
    loader=FileSystemLoader(BASE_DIR / "templates"),
    autoescape=select_autoescape(["html", "xml"]),
)


class Supabase:
    def __init__(self) -> None:
        self.url = os.getenv("SUPABASE_URL", "").rstrip("/")
        self.key = os.getenv("SUPABASE_SERVICE_ROLE_KEY", "")
        configured_proxy = os.getenv("OUTBOUND_HTTP_PROXY", "").strip()
        on_pythonanywhere = bool(
            os.getenv("PYTHONANYWHERE_DOMAIN") or os.getenv("PYTHONANYWHERE_SITE")
        )
        self.proxy = configured_proxy or (
            "http://proxy.server:3128" if on_pythonanywhere else None
        )

    def _headers(self, prefer: str | None = None) -> dict[str, str]:
        if not self.url or not self.key:
            raise RuntimeError("SUPABASE_URL and SUPABASE_SERVICE_ROLE_KEY must be set in .env")
        headers = {
            "apikey": self.key,
            "Authorization": f"Bearer {self.key}",
            "Content-Type": "application/json",
        }
        if prefer:
            headers["Prefer"] = prefer
        return headers

    async def request(self, method: str, table: str, *, params=None, json=None, prefer=None):
        # Use PythonAnywhere's required egress proxy only on that platform.
        # trust_env=False prevents an unrelated local shell proxy from changing app behavior.
        async with httpx.AsyncClient(timeout=15, proxy=self.proxy, trust_env=False) as client:
            response = await client.request(
                method,
                f"{self.url}/rest/v1/{table}",
                headers=self._headers(prefer),
                params=params,
                json=json,
            )
        if response.is_error:
            logger.error("Supabase request failed: %s %s returned %s", method, table, response.status_code)
            raise HTTPException(status_code=400, detail="The request could not be completed")
        return response.json() if response.content else None


db = Supabase()
SESSION_DAYS = 30
COOKIE_SECURE = os.getenv("COOKIE_SECURE", "false").lower() == "true"
SESSION_COOKIE = "__Host-budget_bloom_session" if COOKIE_SECURE else "budget_bloom_session"
CSRF_COOKIE = "__Host-budget_bloom_csrf" if COOKIE_SECURE else "budget_bloom_csrf"
logger = logging.getLogger("budget_bloom")


@app.middleware("http")
async def security_headers(request: Request, call_next):
    response = await call_next(request)
    response.headers["Content-Security-Policy"] = (
        "default-src 'self'; script-src 'self'; "
        "style-src 'self' https://fonts.googleapis.com; "
        "font-src 'self' https://fonts.gstatic.com; img-src 'self' data:; "
        "frame-ancestors 'none'; base-uri 'self'; form-action 'self'"
    )
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["Referrer-Policy"] = "no-referrer"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["Permissions-Policy"] = "camera=(), microphone=(), geolocation=()"
    if COOKIE_SECURE:
        response.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"
    return response


def password_hash(password: str, salt: bytes | None = None) -> str:
    salt = salt or secrets.token_bytes(16)
    digest = hashlib.scrypt(password.encode(), salt=salt, n=2**14, r=8, p=1)
    return f"scrypt$16384$8$1${salt.hex()}${digest.hex()}"


def password_matches(password: str, encoded: str) -> bool:
    try:
        algorithm, n, r, p, salt, expected = encoded.split("$")
        if algorithm != "scrypt":
            return False
        actual = hashlib.scrypt(
            password.encode(), salt=bytes.fromhex(salt), n=int(n), r=int(r), p=int(p)
        )
        return hmac.compare_digest(actual, bytes.fromhex(expected))
    except (ValueError, TypeError):
        return False


def session_token_hash(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()


DUMMY_PASSWORD_HASH = password_hash(secrets.token_urlsafe(24))


def request_ip_hash(request: Request) -> str:
    address = request.client.host if request.client else "unknown"
    return hashlib.sha256(address.encode()).hexdigest()


async def enforce_rate_limit(request: Request, bucket: str, identity: str, limit: int = 8, window: int = 900):
    key = f"{bucket}:{request_ip_hash(request)}:{hashlib.sha256(identity.encode()).hexdigest()}"
    allowed = await db.request("POST", "rpc/check_auth_rate_limit", json={
        "p_key_hash": hashlib.sha256(key.encode()).hexdigest(), "p_limit": limit,
        "p_window_seconds": window,
    })
    if not allowed:
        raise HTTPException(429, "Too many attempts. Try again later.", headers={"Retry-After": str(window)})


def anonymous_csrf_token(request: Request) -> str | None:
    return request.cookies.get(CSRF_COOKIE)


def session_csrf_token(request: Request) -> str | None:
    token = request.cookies.get(SESSION_COOKIE)
    return hashlib.sha256(f"csrf:{token}".encode()).hexdigest() if token else None


def require_csrf(request: Request, supplied: str, authenticated: bool = True):
    expected = session_csrf_token(request) if authenticated else anonymous_csrf_token(request)
    if not expected or not hmac.compare_digest(expected, supplied):
        raise HTTPException(403, "Invalid form token")


def set_anonymous_csrf(response: HTMLResponse, token: str):
    response.set_cookie(
        CSRF_COOKIE, token, max_age=3600, httponly=True, samesite="strict", secure=COOKIE_SECURE, path="/",
    )


async def audit_event(request: Request, event_type: str, account: dict | None = None, metadata: dict | None = None):
    try:
        await db.request("POST", "security_audit_events", json={
            "account_id": account.get("id") if account else None,
            "household_id": account.get("household_id") if account else None,
            "event_type": event_type, "ip_hash": request_ip_hash(request), "metadata": metadata or {},
        })
    except HTTPException:
        logger.exception("Unable to store security audit event %s", event_type)


async def current_account(request: Request) -> dict | None:
    token = request.cookies.get(SESSION_COOKIE)
    if not token:
        return None
    sessions = await db.request(
        "GET", "account_sessions", params={
            "select": "account_id,expires_at,accounts(id,username,household_id,role,disabled_at)",
            "token_hash": f"eq.{session_token_hash(token)}",
            "expires_at": f"gt.{datetime.now(UTC).isoformat()}",
            "limit": "1",
        },
    )
    account = sessions[0]["accounts"] if sessions else None
    return account if account and not account["disabled_at"] else None


async def require_household(request: Request, household_id: int) -> dict:
    account = await current_account(request)
    if not account:
        raise HTTPException(401, "Sign in required")
    if account["household_id"] != household_id:
        raise HTTPException(403, "This account cannot access that household")
    return account


def login_page(request: Request, error: str | None = None) -> HTMLResponse:
    csrf_token = secrets.token_urlsafe(32)
    response = HTMLResponse(templates.get_template("login.html").render(error=error, csrf_token=csrf_token))
    set_anonymous_csrf(response, csrf_token)
    return response


async def valid_invitation(token: str) -> dict | None:
    if not token:
        return None
    rows = await db.request(
        "GET", "account_invitations", params={
            "select": "id,household_id,expires_at,used_at,households(name)",
            "token_hash": f"eq.{session_token_hash(token)}", "used_at": "is.null",
            "expires_at": f"gt.{datetime.now(UTC).isoformat()}", "limit": "1",
        },
    )
    return rows[0] if rows else None


def month_bounds(month: str) -> tuple[date, date]:
    try:
        year, number = (int(part) for part in month.split("-"))
        last_day = calendar.monthrange(year, number)[1]
        return date(year, number, 1), date(year, number, last_day)
    except (ValueError, TypeError):
        today = date.today()
        return date(today.year, today.month, 1), date(
            today.year, today.month, calendar.monthrange(today.year, today.month)[1]
        )


def date_in_month(source: date, year: int, month: int) -> date:
    """Move a date into a month, clamping dates such as the 31st to month-end."""
    return date(year, month, min(source.day, calendar.monthrange(year, month)[1]))


def previous_month_start(source: date) -> date:
    if source.month == 1:
        return date(source.year - 1, 12, 1)
    return date(source.year, source.month - 1, 1)


def recurrence_in_month(source: date, selected: date, recurring: bool, recurring_until: date | None) -> bool:
    return recurring and source < selected and (recurring_until is None or selected <= recurring_until)


def money(value: str) -> Decimal:
    try:
        amount = Decimal(value).quantize(Decimal("0.01"))
    except InvalidOperation as exc:
        raise HTTPException(400, "Enter a valid amount") from exc
    if amount <= 0:
        raise HTTPException(400, "Amount must be greater than zero")
    return amount


def redirect_home(household_id: int | None = None, month: str | None = None):
    query = {k: v for k, v in {"household": household_id, "month": month}.items() if v}
    return RedirectResponse(f"/?{urlencode(query)}" if query else "/", status_code=303)


async def person_in_household(person_id: int, household_id: int) -> bool:
    rows = await db.request(
        "GET", "people", params={"select": "id", "id": f"eq.{person_id}", "household_id": f"eq.{household_id}"}
    )
    return bool(rows)


async def category_in_household(category_id: int, household_id: int) -> bool:
    rows = await db.request(
        "GET", "categories",
        params={"select": "id", "id": f"eq.{category_id}", "household_id": f"eq.{household_id}"},
    )
    return bool(rows)


@app.get("/")
async def dashboard(request: Request, household: int | None = None, person: str | None = None, month: str | None = None):
    account = await current_account(request)
    if not account:
        return RedirectResponse("/login", status_code=303)
    household = account["household_id"]
    try:
        selected_person = int(person) if person else None
    except ValueError:
        selected_person = None
    start, end = month_bounds(month or date.today().strftime("%Y-%m"))
    selected_month = start.strftime("%Y-%m")
    households = await db.request(
        "GET", "households", params={"select": "*", "id": f"eq.{household}", "limit": "1"}
    )
    active = next((item for item in households if item["id"] == household), None)
    if not active and households:
        active = households[0]

    people, categories, entries = [], [], []
    if active:
        people = await db.request(
            "GET", "people", params={"select": "*", "household_id": f"eq.{active['id']}", "order": "name"}
        )
        categories = await db.request(
            "GET", "categories",
            params={"select": "*", "household_id": f"eq.{active['id']}", "order": "sort_order,name"},
        )
        params = {
            "select": "*,people(name),categories(name)",
            "household_id": f"eq.{active['id']}",
            "entry_date": f"lte.{end.isoformat()}",
            "order": "entry_date.desc,id.desc",
        }
        if selected_person and any(item["id"] == selected_person for item in people):
            params["person_id"] = f"eq.{selected_person}"
        else:
            selected_person = None
        rows = await db.request("GET", "budget_entries", params=params)
        completion_rows = await db.request(
            "GET", "entry_completions", params={
                "select": "entry_id", "household_id": f"eq.{active['id']}",
                "month": f"eq.{start.isoformat()}",
            }
        )
        completed_entry_ids = {item["entry_id"] for item in completion_rows}
        entries = []
        for item in rows:
            source_date = date.fromisoformat(item["entry_date"])
            recurring_until = date.fromisoformat(item["recurring_until"]) if item["recurring_until"] else None
            recurs_in_selected_month = recurrence_in_month(
                source_date, start, item["recurring_monthly"], recurring_until
            )
            if source_date >= start or recurs_in_selected_month:
                item["source_entry_date"] = item["entry_date"]
                item["entry_date"] = date_in_month(source_date, start.year, start.month).isoformat()
                item["completed"] = item["id"] in completed_entry_ids
                item["recurs_in_selected_month"] = item["recurring_monthly"] and (
                    recurring_until is None or start <= recurring_until
                )
                entries.append(item)
        # Keep upcoming work easy to scan: newest incomplete entries first,
        # followed by completed entries in the same newest-first order.
        entries.sort(key=lambda item: (item["entry_date"], item["id"]), reverse=True)
        entries.sort(key=lambda item: item["completed"])

    income = sum((Decimal(str(item["amount"])) for item in entries if item["entry_type"] == "income"), Decimal())
    expenses = sum((Decimal(str(item["amount"])) for item in entries if item["entry_type"] == "expense"), Decimal())
    html = templates.get_template("index.html").render(
        request=request,
        households=households,
        active=active,
        people=people,
        categories=categories,
        selected_person=selected_person,
        selected_month=selected_month,
        entries=entries,
        income=income,
        expenses=expenses,
        balance=income - expenses,
        today=date.today().isoformat(),
        account=account,
        csrf_token=session_csrf_token(request),
    )
    return HTMLResponse(html)


@app.get("/login")
async def login_form(request: Request):
    if await current_account(request):
        return RedirectResponse("/", status_code=303)
    return login_page(request)


@app.post("/login")
async def login(request: Request, username: str = Form(...), password: str = Form(...), csrf_token: str = Form(...)):
    require_csrf(request, csrf_token, authenticated=False)
    username = username.strip().lower()
    await enforce_rate_limit(request, "login", username)
    rows = []
    if re.fullmatch(r"[a-z0-9._-]{3,50}", username):
        rows = await db.request(
            "GET", "accounts", params={
                "select": "id,password_hash,household_id,role,disabled_at",
                "username": f"eq.{username}", "limit": "1",
            }
        )
    encoded = rows[0]["password_hash"] if rows else DUMMY_PASSWORD_HASH
    valid_password = password_matches(password, encoded)
    if not rows or not valid_password or rows[0]["disabled_at"]:
        await audit_event(request, "login_failed", metadata={"username_hash": hashlib.sha256(username.encode()).hexdigest()})
        return login_page(request, "Invalid username or password")
    token = secrets.token_urlsafe(32)
    expires = datetime.now(UTC) + timedelta(days=SESSION_DAYS)
    await db.request("POST", "account_sessions", json={
        "account_id": rows[0]["id"], "token_hash": session_token_hash(token),
        "expires_at": expires.isoformat(),
    })
    response = RedirectResponse("/", status_code=303)
    response.set_cookie(
        SESSION_COOKIE, token, max_age=SESSION_DAYS * 86400, httponly=True,
        samesite="lax", secure=COOKIE_SECURE, path="/",
    )
    await audit_event(request, "login_succeeded", rows[0])
    return response


@app.get("/register")
async def register_form(request: Request):
    if await current_account(request):
        return RedirectResponse("/", status_code=303)
    csrf_token = secrets.token_urlsafe(32)
    response = HTMLResponse(templates.get_template("register.html").render(
        code="", invitation=None, error=None, csrf_token=csrf_token,
    ))
    set_anonymous_csrf(response, csrf_token)
    return response


@app.post("/register/code")
async def check_registration_code(request: Request, code: str = Form(...), csrf_token: str = Form(...)):
    require_csrf(request, csrf_token, authenticated=False)
    await enforce_rate_limit(request, "invitation", "code", limit=12)
    invitation = await valid_invitation(code)
    next_csrf = secrets.token_urlsafe(32)
    response = HTMLResponse(templates.get_template("register.html").render(
        code=code if invitation else "", invitation=invitation,
        error=None if invitation else "That invitation code is invalid, expired, or already used",
        csrf_token=next_csrf,
    ))
    set_anonymous_csrf(response, next_csrf)
    return response


@app.post("/register")
async def register(
    request: Request, username: str = Form(...), password: str = Form(...),
    invitation_token: str = Form(...), csrf_token: str = Form(...),
):
    require_csrf(request, csrf_token, authenticated=False)
    username = username.strip().lower()
    await enforce_rate_limit(request, "register", username, limit=6)
    if not re.fullmatch(r"[a-z0-9._-]{3,50}", username) or not 12 <= len(password) <= 128:
        invitation = await valid_invitation(invitation_token)
        next_csrf = secrets.token_urlsafe(32)
        response = HTMLResponse(templates.get_template("register.html").render(
            code=invitation_token, invitation=invitation,
            error="Use a 3–50 character username (letters, numbers, . _ -) and a 12–128 character password",
            csrf_token=next_csrf,
        ))
        set_anonymous_csrf(response, next_csrf)
        return response
    try:
        await db.request("POST", "rpc/redeem_household_invitation", json={
            "p_token_hash": session_token_hash(invitation_token), "p_username": username,
            "p_password_hash": password_hash(password),
        })
    except HTTPException:
        invitation = await valid_invitation(invitation_token)
        next_csrf = secrets.token_urlsafe(32)
        response = HTMLResponse(templates.get_template("register.html").render(
            code=invitation_token, invitation=invitation,
            error="That code is invalid or used, or the username is unavailable",
            csrf_token=next_csrf,
        ))
        set_anonymous_csrf(response, next_csrf)
        await audit_event(request, "registration_failed")
        return response
    await audit_event(request, "invitation_redeemed")
    return RedirectResponse("/login", status_code=303)


@app.post("/invitations")
async def create_invitation(request: Request, csrf_token: str = Form(...)):
    require_csrf(request, csrf_token)
    account = await current_account(request)
    if not account:
        raise HTTPException(401, "Sign in to generate an invitation")
    if account["role"] != "owner":
        raise HTTPException(403, "Only household owners can invite users")
    household_id = account["household_id"]
    token = secrets.token_urlsafe(24)
    expires = datetime.now(UTC) + timedelta(days=7)
    await db.request("POST", "account_invitations", json={
        "household_id": household_id, "token_hash": session_token_hash(token),
        "expires_at": expires.isoformat(),
    })
    invite_url = f"{str(request.base_url).rstrip('/')}/register"
    await audit_event(request, "invitation_created", account)
    return HTMLResponse(templates.get_template("invitation.html").render(
        token=token, invite_url=invite_url, expires=expires.strftime("%B %d, %Y at %H:%M UTC"),
        signed_in=True,
    ))


@app.post("/logout")
async def logout(request: Request, csrf_token: str = Form(...)):
    require_csrf(request, csrf_token)
    account = await current_account(request)
    token = request.cookies.get(SESSION_COOKIE)
    if token:
        await db.request("DELETE", "account_sessions", params={"token_hash": f"eq.{session_token_hash(token)}"})
    response = RedirectResponse("/login", status_code=303)
    response.delete_cookie(SESSION_COOKIE)
    if account:
        await audit_event(request, "logout", account)
    return response


@app.get("/security")
async def security_page(request: Request, message: str | None = None):
    account = await current_account(request)
    if not account:
        return RedirectResponse("/login", status_code=303)
    members = await db.request(
        "GET", "accounts", params={
            "select": "id,username,role,disabled_at,created_at",
            "household_id": f"eq.{account['household_id']}", "order": "created_at",
        },
    )
    invitations = await db.request(
        "GET", "account_invitations", params={
            "select": "id,expires_at,created_at", "household_id": f"eq.{account['household_id']}",
            "used_at": "is.null", "expires_at": f"gt.{datetime.now(UTC).isoformat()}", "order": "created_at.desc",
        },
    )
    return HTMLResponse(templates.get_template("security.html").render(
        account=account, members=members, invitations=invitations,
        csrf_token=session_csrf_token(request), message=message,
    ))


@app.post("/security/password")
async def change_password(
    request: Request, current_password: str = Form(...), new_password: str = Form(...),
    csrf_token: str = Form(...),
):
    require_csrf(request, csrf_token)
    account = await current_account(request)
    if not account:
        raise HTTPException(401, "Sign in required")
    await enforce_rate_limit(request, "password_change", str(account["id"]), limit=5)
    rows = await db.request(
        "GET", "accounts", params={"select": "password_hash", "id": f"eq.{account['id']}", "limit": "1"},
    )
    if not rows or not password_matches(current_password, rows[0]["password_hash"]):
        await audit_event(request, "password_change_failed", account)
        return RedirectResponse("/security?message=Current+password+is+incorrect", status_code=303)
    if len(new_password) < 12 or len(new_password) > 128:
        return RedirectResponse("/security?message=New+password+must+be+12-128+characters", status_code=303)
    await db.request("PATCH", "accounts", params={"id": f"eq.{account['id']}"}, json={
        "password_hash": password_hash(new_password), "password_changed_at": datetime.now(UTC).isoformat(),
    })
    await db.request("DELETE", "account_sessions", params={"account_id": f"eq.{account['id']}"})
    await audit_event(request, "password_changed", account)
    response = RedirectResponse("/login", status_code=303)
    response.delete_cookie(SESSION_COOKIE, path="/")
    return response


@app.post("/security/sessions/revoke")
async def revoke_sessions(request: Request, csrf_token: str = Form(...)):
    require_csrf(request, csrf_token)
    account = await current_account(request)
    if not account:
        raise HTTPException(401, "Sign in required")
    await db.request("DELETE", "account_sessions", params={"account_id": f"eq.{account['id']}"})
    await audit_event(request, "sessions_revoked", account)
    response = RedirectResponse("/login", status_code=303)
    response.delete_cookie(SESSION_COOKIE, path="/")
    return response


@app.post("/security/members/{member_id}/disable")
async def disable_member(member_id: int, request: Request, csrf_token: str = Form(...)):
    require_csrf(request, csrf_token)
    account = await current_account(request)
    if not account or account["role"] != "owner":
        raise HTTPException(403, "Owner access required")
    if member_id == account["id"]:
        raise HTTPException(400, "Owners cannot disable their own account")
    members = await db.request(
        "GET", "accounts", params={
            "select": "id", "id": f"eq.{member_id}",
            "household_id": f"eq.{account['household_id']}", "limit": "1",
        },
    )
    if not members:
        raise HTTPException(404, "Member not found")
    await db.request("PATCH", "accounts", params={"id": f"eq.{member_id}"}, json={"disabled_at": datetime.now(UTC).isoformat()})
    await db.request("DELETE", "account_sessions", params={"account_id": f"eq.{member_id}"})
    await audit_event(request, "member_disabled", account, {"member_id": member_id})
    return RedirectResponse("/security?message=Member+disabled", status_code=303)


@app.post("/security/members/{member_id}/enable")
async def enable_member(member_id: int, request: Request, csrf_token: str = Form(...)):
    require_csrf(request, csrf_token)
    account = await current_account(request)
    if not account or account["role"] != "owner":
        raise HTTPException(403, "Owner access required")
    members = await db.request(
        "GET", "accounts", params={
            "select": "id", "id": f"eq.{member_id}",
            "household_id": f"eq.{account['household_id']}", "limit": "1",
        },
    )
    if not members:
        raise HTTPException(404, "Member not found")
    await db.request("PATCH", "accounts", params={"id": f"eq.{member_id}"}, json={"disabled_at": None})
    await audit_event(request, "member_enabled", account, {"member_id": member_id})
    return RedirectResponse("/security?message=Member+enabled", status_code=303)


@app.post("/security/invitations/{invitation_id}/revoke")
async def revoke_invitation(invitation_id: int, request: Request, csrf_token: str = Form(...)):
    require_csrf(request, csrf_token)
    account = await current_account(request)
    if not account or account["role"] != "owner":
        raise HTTPException(403, "Owner access required")
    await db.request("DELETE", "account_invitations", params={
        "id": f"eq.{invitation_id}", "household_id": f"eq.{account['household_id']}", "used_at": "is.null",
    })
    await audit_event(request, "invitation_revoked", account, {"invitation_id": invitation_id})
    return RedirectResponse("/security?message=Invitation+revoked", status_code=303)


@app.post("/households")
async def create_household(request: Request, name: str = Form(...), csrf_token: str = Form(...)):
    require_csrf(request, csrf_token)
    account = await current_account(request)
    if not account:
        raise HTTPException(401, "Sign in required")
    name = name.strip()
    if not name:
        raise HTTPException(400, "Household name is required")
    raise HTTPException(400, "This account is already linked to a household")


@app.post("/people")
async def create_person(
    request: Request, household_id: int = Form(...), name: str = Form(...),
    month: str = Form(...), csrf_token: str = Form(...),
):
    require_csrf(request, csrf_token)
    await require_household(request, household_id)
    name = name.strip()
    if not name:
        raise HTTPException(400, "Person name is required")
    await db.request("POST", "people", json={"household_id": household_id, "name": name})
    return redirect_home(household_id, month)


@app.post("/entries")
async def create_entry(
    request: Request, household_id: int = Form(...), person_id: int = Form(...), entry_type: str = Form(...),
    description: str = Form(...), category_id: int = Form(...), amount: str = Form(...),
    entry_date: date = Form(...), month: str = Form(...),
    recurring_monthly: bool = Form(False), csrf_token: str = Form(...),
):
    require_csrf(request, csrf_token)
    await require_household(request, household_id)
    if (entry_type not in {"income", "expense"}
            or not await person_in_household(person_id, household_id)
            or not await category_in_household(category_id, household_id)):
        raise HTTPException(400, "Invalid entry details")
    if not description.strip():
        raise HTTPException(400, "Description is required")
    await db.request("POST", "budget_entries", json={
        "household_id": household_id, "person_id": person_id, "entry_type": entry_type,
        "description": description.strip(), "category_id": category_id,
        "amount": str(money(amount)), "entry_date": entry_date.isoformat(),
        "recurring_monthly": recurring_monthly,
    })
    return redirect_home(household_id, month)


@app.post("/entries/{entry_id}/edit")
async def edit_entry(
    entry_id: int, request: Request, household_id: int = Form(...), person_id: int = Form(...), entry_type: str = Form(...),
    description: str = Form(...), category_id: int = Form(...), amount: str = Form(...),
    entry_date: date = Form(...), month: str = Form(...),
    recurring_monthly: bool = Form(False), csrf_token: str = Form(...),
):
    require_csrf(request, csrf_token)
    await require_household(request, household_id)
    if (entry_type not in {"income", "expense"}
            or not await person_in_household(person_id, household_id)
            or not await category_in_household(category_id, household_id)):
        raise HTTPException(400, "Invalid entry details")
    if not description.strip():
        raise HTTPException(400, "Description is required")

    existing_rows = await db.request(
        "GET", "budget_entries",
        params={
            "select": "id,entry_date,recurring_monthly,recurring_until",
            "id": f"eq.{entry_id}", "household_id": f"eq.{household_id}",
        },
    )
    if not existing_rows:
        raise HTTPException(404, "Entry not found")
    existing = existing_rows[0]
    selected_start, _ = month_bounds(month)
    source_date = date.fromisoformat(existing["entry_date"])

    recurrence_payload = {"recurring_monthly": recurring_monthly, "recurring_until": None}
    if not recurring_monthly and existing["recurring_monthly"] and selected_start > source_date.replace(day=1):
        # Stopping a recurrence affects this month forward, not its prior history.
        recurrence_payload = {
            "recurring_monthly": True,
            "recurring_until": previous_month_start(selected_start).isoformat(),
        }
    elif recurring_monthly and existing["recurring_monthly"] and existing["recurring_until"]:
        # Editing an earlier occurrence must not silently reactivate a stopped recurrence.
        recurrence_payload["recurring_until"] = existing["recurring_until"]

    await db.request("PATCH", "budget_entries", params={"id": f"eq.{entry_id}", "household_id": f"eq.{household_id}"}, json={
        "person_id": person_id, "entry_type": entry_type, "description": description.strip(),
        "category_id": category_id,
        "amount": str(money(amount)), "entry_date": entry_date.isoformat(), "updated_at": datetime.now(UTC).isoformat(),
        **recurrence_payload,
    })
    return redirect_home(household_id, month)


@app.post("/entries/{entry_id}/delete")
async def delete_entry(
    entry_id: int, request: Request, household_id: int = Form(...), month: str = Form(...),
    csrf_token: str = Form(...),
):
    require_csrf(request, csrf_token)
    await require_household(request, household_id)
    await db.request("DELETE", "budget_entries", params={"id": f"eq.{entry_id}", "household_id": f"eq.{household_id}"})
    return redirect_home(household_id, month)


@app.post("/entries/{entry_id}/completion")
async def set_entry_completion(
    entry_id: int, request: Request, household_id: int = Form(...), month: str = Form(...),
    completed: bool = Form(False), csrf_token: str = Form(...),
):
    require_csrf(request, csrf_token)
    await require_household(request, household_id)
    start, _ = month_bounds(month)
    entry_rows = await db.request(
        "GET", "budget_entries",
        params={"select": "id", "id": f"eq.{entry_id}", "household_id": f"eq.{household_id}"},
    )
    if not entry_rows:
        raise HTTPException(404, "Entry not found")

    if completed:
        await db.request(
            "POST", "entry_completions",
            json={"entry_id": entry_id, "household_id": household_id, "month": start.isoformat()},
            prefer="resolution=merge-duplicates",
        )
    else:
        await db.request("DELETE", "entry_completions", params={
            "entry_id": f"eq.{entry_id}", "household_id": f"eq.{household_id}",
            "month": f"eq.{start.isoformat()}",
        })
    return redirect_home(household_id, start.strftime("%Y-%m"))
