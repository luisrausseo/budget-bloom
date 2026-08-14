import calendar
import os
from datetime import UTC, date, datetime
from decimal import Decimal, InvalidOperation
from pathlib import Path
from urllib.parse import urlencode

import httpx
from dotenv import load_dotenv
from fastapi import FastAPI, Form, HTTPException, Request
from fastapi.responses import RedirectResponse
from fastapi.staticfiles import StaticFiles
from jinja2 import Environment, FileSystemLoader, select_autoescape

BASE_DIR = Path(__file__).resolve().parent
load_dotenv(BASE_DIR / ".env")

app = FastAPI(title="Monthly Budget")
app.mount("/static", StaticFiles(directory=BASE_DIR / "static"), name="static")
templates = Environment(
    loader=FileSystemLoader(BASE_DIR / "templates"),
    autoescape=select_autoescape(["html", "xml"]),
)


class Supabase:
    def __init__(self) -> None:
        self.url = os.getenv("SUPABASE_URL", "").rstrip("/")
        self.key = os.getenv("SUPABASE_SERVICE_ROLE_KEY", "")

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
        async with httpx.AsyncClient(timeout=15) as client:
            response = await client.request(
                method,
                f"{self.url}/rest/v1/{table}",
                headers=self._headers(prefer),
                params=params,
                json=json,
            )
        if response.is_error:
            detail = response.json().get("message", response.text)
            raise HTTPException(status_code=400, detail=detail)
        return response.json() if response.content else None


db = Supabase()


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
    try:
        selected_person = int(person) if person else None
    except ValueError:
        selected_person = None
    start, end = month_bounds(month or date.today().strftime("%Y-%m"))
    selected_month = start.strftime("%Y-%m")
    households = await db.request("GET", "households", params={"select": "*", "order": "name"})
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
            if source_date >= start or item["recurring_monthly"]:
                item["source_entry_date"] = item["entry_date"]
                item["entry_date"] = date_in_month(source_date, start.year, start.month).isoformat()
                item["completed"] = item["id"] in completed_entry_ids
                entries.append(item)
        entries.sort(key=lambda item: (item["entry_date"], item["id"]), reverse=True)

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
    )
    from fastapi.responses import HTMLResponse
    return HTMLResponse(html)


@app.post("/households")
async def create_household(name: str = Form(...)):
    name = name.strip()
    if not name:
        raise HTTPException(400, "Household name is required")
    rows = await db.request("POST", "households", json={"name": name}, prefer="return=representation")
    return redirect_home(rows[0]["id"])


@app.post("/people")
async def create_person(household_id: int = Form(...), name: str = Form(...), month: str = Form(...)):
    name = name.strip()
    if not name:
        raise HTTPException(400, "Person name is required")
    await db.request("POST", "people", json={"household_id": household_id, "name": name})
    return redirect_home(household_id, month)


@app.post("/entries")
async def create_entry(
    household_id: int = Form(...), person_id: int = Form(...), entry_type: str = Form(...),
    description: str = Form(...), category_id: int = Form(...), amount: str = Form(...),
    entry_date: date = Form(...), month: str = Form(...),
    recurring_monthly: bool = Form(False),
):
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
    entry_id: int, household_id: int = Form(...), person_id: int = Form(...), entry_type: str = Form(...),
    description: str = Form(...), category_id: int = Form(...), amount: str = Form(...),
    entry_date: date = Form(...), month: str = Form(...),
    recurring_monthly: bool = Form(False),
):
    if (entry_type not in {"income", "expense"}
            or not await person_in_household(person_id, household_id)
            or not await category_in_household(category_id, household_id)):
        raise HTTPException(400, "Invalid entry details")
    if not description.strip():
        raise HTTPException(400, "Description is required")
    await db.request("PATCH", "budget_entries", params={"id": f"eq.{entry_id}", "household_id": f"eq.{household_id}"}, json={
        "person_id": person_id, "entry_type": entry_type, "description": description.strip(),
        "category_id": category_id,
        "amount": str(money(amount)), "entry_date": entry_date.isoformat(), "updated_at": datetime.now(UTC).isoformat(),
        "recurring_monthly": recurring_monthly,
    })
    return redirect_home(household_id, month)


@app.post("/entries/{entry_id}/delete")
async def delete_entry(entry_id: int, household_id: int = Form(...), month: str = Form(...)):
    await db.request("DELETE", "budget_entries", params={"id": f"eq.{entry_id}", "household_id": f"eq.{household_id}"})
    return redirect_home(household_id, month)


@app.post("/entries/{entry_id}/completion")
async def set_entry_completion(
    entry_id: int, household_id: int = Form(...), month: str = Form(...),
    completed: bool = Form(False),
):
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
