import hashlib
import hmac
import logging
import os
import re
import secrets
from pathlib import Path

import httpx
from dotenv import load_dotenv
from fastapi import FastAPI, Form, HTTPException, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from jinja2 import Environment, FileSystemLoader, select_autoescape
from starlette.middleware.trustedhost import TrustedHostMiddleware

BASE_DIR = Path(__file__).resolve().parent
load_dotenv(BASE_DIR / ".env")
logger = logging.getLogger("budget_bloom_admin")
ADMIN_CSRF_COOKIE = "budget_bloom_admin_csrf"

admin_app = FastAPI(title="Budget Bloom Admin", docs_url=None, redoc_url=None, openapi_url=None)
admin_app.add_middleware(TrustedHostMiddleware, allowed_hosts=["localhost", "127.0.0.1", "[::1]"])
admin_app.mount("/static", StaticFiles(directory=BASE_DIR / "static"), name="static")
templates = Environment(
    loader=FileSystemLoader(BASE_DIR / "templates"),
    autoescape=select_autoescape(["html", "xml"]),
)
templates.globals["static_version"] = str(int(max(
    (BASE_DIR / "static" / "admin.css").stat().st_mtime,
    (BASE_DIR / "static" / "theme.js").stat().st_mtime,
)))


class AdminDatabase:
    def __init__(self):
        self.url = os.getenv("SUPABASE_URL", "").rstrip("/")
        self.key = os.getenv("SUPABASE_SERVICE_ROLE_KEY", "")
        self.client = httpx.AsyncClient(timeout=20, trust_env=False)

    async def request(self, method: str, resource: str, *, params=None, json=None):
        if not self.url or not self.key:
            raise RuntimeError("Supabase credentials are missing")
        response = await self.client.request(
            method, f"{self.url}/rest/v1/{resource}", params=params, json=json,
            headers={
                "apikey": self.key, "Authorization": f"Bearer {self.key}",
                "Content-Type": "application/json",
            },
        )
        if response.is_error:
            logger.error("Admin database request %s %s failed with %s", method, resource, response.status_code)
            raise HTTPException(400, "The database operation could not be completed")
        return response.json() if response.content else None


db = AdminDatabase()


@admin_app.on_event("shutdown")
async def close_admin_client():
    await db.client.aclose()


@admin_app.middleware("http")
async def localhost_only(request: Request, call_next):
    client_host = request.client.host if request.client else ""
    if os.getenv("PYTHONANYWHERE_DOMAIN") or os.getenv("PYTHONANYWHERE_SITE"):
        return HTMLResponse("Not found", status_code=404)
    if client_host not in {"127.0.0.1", "::1"}:
        return HTMLResponse("Not found", status_code=404)
    response = await call_next(request)
    response.headers["Cache-Control"] = "no-store"
    response.headers["Content-Security-Policy"] = "default-src 'self'; script-src 'self'; style-src 'self' https://fonts.googleapis.com; font-src 'self' https://fonts.gstatic.com; img-src 'self' data:; frame-ancestors 'none'; base-uri 'self'; form-action 'self'"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["Referrer-Policy"] = "no-referrer"
    return response


def hash_password(password: str) -> str:
    salt = secrets.token_bytes(16)
    digest = hashlib.scrypt(password.encode(), salt=salt, n=2**14, r=8, p=1)
    return f"scrypt$16384$8$1${salt.hex()}${digest.hex()}"


def require_csrf(request: Request, supplied: str):
    expected = request.cookies.get(ADMIN_CSRF_COOKIE)
    if not expected or not hmac.compare_digest(expected, supplied):
        raise HTTPException(403, "Invalid form token")


@admin_app.get("/")
async def admin_dashboard(request: Request, message: str | None = None):
    metrics = await db.request("POST", "rpc/get_admin_dashboard_metrics", json={})
    csrf_token = secrets.token_urlsafe(32)
    monthly = metrics.get("monthly_activity", [])
    html = templates.get_template("admin.html").render(
        metrics=metrics, monthly=monthly,
        max_monthly=max((item["entries"] for item in monthly), default=1) or 1,
        csrf_token=csrf_token, message=message,
    )
    response = HTMLResponse(html)
    response.set_cookie(ADMIN_CSRF_COOKIE, csrf_token, httponly=True, samesite="strict", path="/")
    return response


@admin_app.post("/households")
async def create_household_account(
    request: Request, household_name: str = Form(...), username: str = Form(...),
    password: str = Form(...), csrf_token: str = Form(...),
):
    require_csrf(request, csrf_token)
    household_name, username = household_name.strip(), username.strip().lower()
    if not household_name or len(household_name) > 100:
        raise HTTPException(400, "Household name must be 1-100 characters")
    if not re.fullmatch(r"[a-z0-9._-]{3,50}", username):
        raise HTTPException(400, "Username must be 3-50 valid characters")
    if not 12 <= len(password) <= 128:
        raise HTTPException(400, "Password must be 12-128 characters")
    await db.request("POST", "rpc/admin_create_household_account", json={
        "p_household_name": household_name, "p_username": username,
        "p_password_hash": hash_password(password),
    })
    return RedirectResponse("/?message=Household+and+owner+account+created", status_code=303)


@admin_app.post("/maintenance/cleanup")
async def cleanup_expired_data(request: Request, csrf_token: str = Form(...)):
    require_csrf(request, csrf_token)
    result = await db.request("POST", "rpc/admin_cleanup_expired_auth_data", json={})
    removed = (result or {}).get("removed", 0)
    return RedirectResponse(f"/?message=Removed+{removed}+expired+records", status_code=303)
