"""Browser regression checks with synthetic pages and intercepted requests; no DB access.

Run with Playwright installed and its Chromium browser available.
"""
import asyncio
import json
from pathlib import Path
from urllib.parse import urlparse, parse_qs

from jinja2 import Environment, FileSystemLoader, select_autoescape
from playwright.async_api import async_playwright, expect

ROOT = Path(__file__).resolve().parents[1]
env = Environment(loader=FileSystemLoader(ROOT / "templates"), autoescape=select_autoescape())
account = dict(id=1, household_id=1, username="sampleuser", role="owner")
person = dict(id=1, name="Alex Example")
category = dict(id=1, name="💡 Electricity")
entry = dict(id=1, description="Electricity bill for the household", amount=75,
             entry_date="2026-09-15", person_id=1, category_id=1, people=person,
             categories=category, completed=False, recurring_monthly=True,
             recurs_in_selected_month=True, entry_type="expense")
base = dict(account=account, csrf_token="sample-csrf", static_version="test")


def render(path, query=""):
    if path == "/":
        args = parse_qs(query)
        month = args.get("month", ["2026-09"])[0]
        return env.get_template("index.html").render(
            **base, active=dict(id=1, name="Example household"), people=[person], categories=[category],
            selected_month=month, selected_month_label="September 2026", selected_month_end="2026-09-30",
            current_month="2026-09", entry_default_date="2026-09-05", selected_person=1,
            entries=[entry, dict(entry, id=2, description="Already paid", completed=True)],
            income=0, expenses=150, balance=-150)
    if path == "/groceries":
        return env.get_template("groceries.html").render(**base, household=dict(id=1, name="Example household"), items=[
            dict(id=3, item_name="Wholegrain bread and a very long grocery item name", completed=False,
                 created_at="2026-09-05T12:00:00Z", display_date="Sep 5, 2026", accounts=account)])
    if path == "/invitation":
        return env.get_template("invitation.html").render(**base, token="sample-code", invite_url="http://localhost/register", expires="Tomorrow", signed_in=True)
    if path == "/register":
        return env.get_template("register.html").render(**base, invitation=None, code="", error=None)
    return env.get_template("login.html").render(**base, error=None)


async def main():
    async with async_playwright() as p:
        browser = await p.chromium.launch()
        context = await browser.new_context()
        state = dict(fail=False, delay=0, posts=0)

        async def route_request(route):
            request = route.request
            url = urlparse(request.url)
            if url.hostname != "localhost":
                await route.abort()
                return
            if url.path.startswith("/static/"):
                file = ROOT / url.path.lstrip("/")
                await route.fulfill(path=str(file), content_type="text/css" if file.suffix == ".css" else "application/javascript")
            elif request.method == "POST":
                state["posts"] += 1
                await asyncio.sleep(state["delay"])
                if state["fail"]:
                    await route.fulfill(status=401, json={"detail": "Sign in required"})
                elif url.path.endswith("/completion"):
                    # Browser serialization sends a multipart body.
                    completed = 'name="completed"\r\n\r\ntrue' in (request.post_data or "")
                    await route.fulfill(json={"completed": completed})
                elif url.path.endswith("/delete"):
                    await route.fulfill(json={"deleted": True})
                elif url.path == "/invitations":
                    await route.fulfill(content_type="text/html", body=render("/invitation"))
                elif url.path == "/register/code":
                    html = env.get_template("register.html").render(**base, invitation=dict(households=dict(name="Sample")), code="test", error=None)
                    await route.fulfill(content_type="text/html", body=html)
                else:
                    await route.fulfill(json={"redirect": "/?month=2026-09&person=1"})
            else:
                await route.fulfill(content_type="text/html", body=render(url.path, url.query))

        await context.route("**/*", route_request)
        page = await context.new_page()
        errors = []
        page.on("pageerror", lambda error: errors.append(str(error)))
        for width in (360, 390, 650, 768, 1280):
            await page.set_viewport_size(dict(width=width, height=900))
            await page.goto("http://localhost/?month=2026-09&person=1")
            await expect(page.locator(".completed-disclosure")).to_contain_text("Completed (1)")
            assert await page.evaluate("document.documentElement.scrollWidth <= innerWidth"), f"Overflow at {width}"
            if width <= 650:
                await expect(page.locator(".mobile-meta").first).to_be_visible()
                await expect(page.locator("td.type-column").first).to_be_hidden()
            for dark in (False, True):
                await page.evaluate("dark => document.documentElement.dataset.theme = dark ? 'dark' : 'light'", dark)
                if width in (390, 1280):
                    await page.screenshot(path=f"/tmp/budget-ux-{width}-{'dark' if dark else 'light'}.png", full_page=True)
        await page.set_viewport_size(dict(width=390, height=900))
        await page.locator(".completed-disclosure").click()
        await expect(page.locator('tr[data-entry-id="2"]')).to_be_hidden()
        await page.locator('tr[data-entry-id="1"] .complete-toggle').check()
        await expect(page.locator(".completed-disclosure")).to_contain_text("Completed (2)")
        await expect(page.locator('tr[data-entry-id="1"]')).to_be_hidden()
        await page.locator(".completed-disclosure").click()
        await page.locator('tr[data-entry-id="1"] .complete-toggle').uncheck()
        await expect(page.locator('tr[data-entry-id="1"]')).not_to_have_class("completed")
        # Explicit confirmation preserves recurrence scope; cancel does not POST.
        before = state["posts"]
        await page.locator('tr[data-entry-id="1"] [data-delete-entry] button').click()
        await expect(page.get_by_role("dialog", name="Stop recurring entry")).to_be_visible()
        await page.get_by_role("button", name="Cancel", exact=True).click()
        assert state["posts"] == before
        # Recurring edit retains values and permits retry after an expired session.
        await page.locator('tr[data-entry-id="1"] .edit').click()
        await expect(page.get_by_role("dialog", name="Edit this month")).to_be_visible()
        await page.locator('#entryForm [name="description"]').fill("Changed only this month")
        state.update(fail=True, delay=.3)
        await page.locator("#entrySubmit").click()
        await expect(page.locator("#entrySubmit")).to_be_disabled()
        await expect(page.locator("#entryForm .feedback")).to_contain_text("session has expired")
        await expect(page.locator('#entryForm [name="description"]')).to_have_value("Changed only this month")
        await expect(page.locator("#entrySubmit")).to_be_enabled()
        await page.locator('#entryDialog .close').click()
        state.update(fail=False, delay=0)
        # Navigation keeps the budget filter; logo still points to the reset route.
        await page.get_by_role("link", name="Grocery list", exact=True).click()
        await expect(page.locator("[data-budget-tab]")).to_have_attribute("href", "/?month=2026-09&person=1")
        await expect(page.locator(".brand-home")).to_have_attribute("href", "/")
        await expect(page.locator(".mobile-meta")).to_contain_text("sampleuser")
        assert await page.locator("#item_name").evaluate("input => input !== document.activeElement")
        await page.screenshot(path="/tmp/budget-ux-groceries.png", full_page=True)
        # Server-rendered invitation steps bootstrap controls again without script errors.
        await page.locator(".account-dropdown summary").click()
        await page.get_by_role("button", name="Invite user", exact=True).click()
        await expect(page.locator("[data-copy-invitation]")).to_be_visible()
        await page.evaluate("window.__copied = ''; Object.defineProperty(navigator, 'clipboard', {value: {writeText: async text => {window.__copied = text;}}})")
        await page.locator("[data-copy-invitation]").click()
        await expect(page.locator(".feedback")).to_contain_text("Invitation copied")
        assert "sample-code" in await page.evaluate("window.__copied")
        await page.goto("http://localhost/register")
        await page.locator('[name="code"]').fill("test")
        await page.get_by_role("button", name="Continue", exact=True).click()
        await expect(page.get_by_role("heading", name="Join Sample")).to_be_visible()
        await page.locator('[name="username"]').fill("newuser")
        await page.locator('[name="password"]').fill("example-password")
        state.update(fail=True)
        await page.get_by_role("button", name="Create account").click()
        await expect(page.locator(".feedback")).to_contain_text("session has expired")
        assert not errors, errors
        await browser.close()
        print("UX browser checks passed: responsive layouts, completion, confirmation, errors, navigation, and invitations.")


if __name__ == "__main__":
    asyncio.run(main())
