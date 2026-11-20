"""Private phone-controlled Playwright browser in GitHub Codespaces.

The forwarded port MUST remain private. Browser sessions stay inside the
Codespace's home directory, never in the public repository or GitHub Issues.
The assistant sends project prompts only through owner-authored GitHub Issues;
private account content is never returned in issue comments.
"""
import asyncio
import json
import os
import re
from pathlib import Path

import aiohttp
from aiohttp import web
from playwright.async_api import async_playwright

OWNER = "Photofiver"
REPO = "gumtree-console-crawler"
PREFIX = "[blueprint-project]"
URL = "https://www.blueprint.io/"
LED_PROMPT = ("Create a simple 9 V battery powered red LED lamp: one 9 V battery, "
              "one momentary normally-open pushbutton, one 470 ohm 0.25 W resistor, "
              "one red 5 mm LED. Series wiring: positive battery to button, then resistor, "
              "then LED anode, LED cathode to battery negative. Generate wiring diagram "
              "and a short bill of materials, no microcontroller and no mains wiring.")
WIDTH, HEIGHT = 1120, 800
STATE = Path.home() / ".local" / "state" / "blueprint-bridge"
PROFILE = Path.home() / ".local" / "share" / "blueprint-bridge" / "chromium"
PROCESSED = STATE / "processed.json"
PAGE = Path(__file__).with_name("index.html")

def login_prompt_visible(body_text: str) -> bool:
    """Detect actual SIGN IN controls, not just absence of an accessible button."""
    return bool(
        re.search(r"(?im)^\s*SIGN\s+IN\s*$", body_text)
        or re.search(r"(?im)^\s*CONTINUE WITH GITHUB\s*$", body_text)
        or re.search(r"(?im)^\s*CONTINUE WITH GOOGLE\s*$", body_text)
    )



class Bridge:
    def __init__(self):
        self.pw = None
        self.ctx = None
        self.lock = asyncio.Lock()
        self.worker = None
        self.worker_status = "starting"
        self.processed = set()

    async def start(self):
        STATE.mkdir(parents=True, exist_ok=True, mode=0o700)
        PROFILE.mkdir(parents=True, exist_ok=True, mode=0o700)
        if PROCESSED.exists():
            try:
                self.processed = set(json.loads(PROCESSED.read_text()))
            except (ValueError, OSError):
                self.processed = set()
        self.pw = await async_playwright().start()
        self.ctx = await self.pw.chromium.launch_persistent_context(
            str(PROFILE), headless=True, viewport={"width": WIDTH, "height": HEIGHT},
            accept_downloads=False, permissions=[], args=["--no-sandbox"]
        )
        if not self.ctx.pages:
            page = await self.ctx.new_page()
            await page.goto(URL, wait_until="domcontentloaded", timeout=45000)
        elif self.ctx.pages[0].url == "about:blank":
            await self.ctx.pages[0].goto(URL, wait_until="domcontentloaded", timeout=45000)
        if os.environ.get("BLUEPRINT_MANUAL_ONLY") == "1":
            self.worker_status = "manual_confirmation_required"
        else:
            self.worker = asyncio.create_task(self.poll_issues())

    def page(self):
        live = [page for page in self.ctx.pages if not page.is_closed()]
        return live[-1] if live else None

    async def stop(self):
        if self.worker:
            self.worker.cancel()
            try:
                await self.worker
            except asyncio.CancelledError:
                pass
        if self.ctx:
            await self.ctx.close()
        if self.pw:
            await self.pw.stop()

    async def signed_in(self):
        home = next((p for p in self.ctx.pages if not p.is_closed() and
                     p.url.startswith(("https://blueprint.io/", "https://www.blueprint.io/"))), None)
        if home is None:
            return False
        try:
            # Blueprint's SIGN IN may not be an accessible <button>.
            # Do not infer successful login merely from a missing button role.
            body_text = await home.locator("body").inner_text(timeout=7000)
            if login_prompt_visible(body_text):
                return False
            if await home.get_by_text("SIGN IN", exact=True).count():
                return False
            return True
        except Exception:
            return False

    async def create_project(self, prompt):
        async with self.lock:
            if not await self.signed_in():
                return "login_required"
            home = next((p for p in self.ctx.pages if not p.is_closed() and
                         p.url.startswith(("https://blueprint.io/", "https://www.blueprint.io/"))), None)
            if home is None:
                return "login_required"
            try:
                composer = home.locator("textarea[placeholder*='Ask blueprint']").first
                await composer.fill(prompt, timeout=12000)
                await composer.press("Enter")
                await home.wait_for_timeout(5500)
                if not await self.signed_in():
                    return "login_required"
                return "prompt_submitted_unverified"
            except Exception:
                return "submission_failed"

    async def post_comment(self, session, issue_number, body, headers):
        api = f"https://api.github.com/repos/{OWNER}/{REPO}/issues/{issue_number}/comments"
        async with session.post(api, json={"body": body}, headers=headers) as r:
            return r.status == 201

    async def poll_issues(self):
        token = os.environ.get("GITHUB_TOKEN") or os.environ.get("GH_TOKEN")
        if not token:
            self.worker_status = "no_github_token"
            return
        headers = {
            "Authorization": f"Bearer {token}",
            "Accept": "application/vnd.github+json",
            "X-GitHub-Api-Version": "2022-11-28",
        }
        url = f"https://api.github.com/repos/{OWNER}/{REPO}/issues"
        timeout = aiohttp.ClientTimeout(total=20)
        async with aiohttp.ClientSession(timeout=timeout) as session:
            while True:
                try:
                    async with session.get(
                        url, params={"state": "open", "sort": "created",
                                     "direction": "desc", "per_page": 50}, headers=headers
                    ) as r:
                        if r.status != 200:
                            self.worker_status = f"github_http_{r.status}"
                            await asyncio.sleep(15)
                            continue
                        issues = await r.json()
                    self.worker_status = "connected"
                    for issue in reversed(issues):
                        if issue.get("pull_request"):
                            continue
                        if not str(issue.get("title", "")).startswith(PREFIX):
                            continue
                        if issue.get("user", {}).get("login") != OWNER:
                            continue
                        number = issue.get("number")
                        if type(number) is not int or number in self.processed:
                            continue
                        try:
                            task = json.loads(issue.get("body") or "{}")
                            prompt = task.get("prompt")
                            if set(task) != {"prompt"} or not isinstance(prompt, str) or not 5 <= len(prompt) <= 800:
                                outcome = "invalid_request"
                            else:
                                outcome = await self.create_project(prompt)
                            if outcome == "login_required":
                                continue
                            # Never upload project screenshots, account details or cookies.
                            comment = "Blueprint bridge: " + outcome + ". Project saving is not confirmed."
                            posted = await self.post_comment(session, number, comment, headers)
                            if posted:
                                self.processed.add(number)
                                PROCESSED.write_text(json.dumps(sorted(self.processed)))
                                os.chmod(PROCESSED, 0o600)
                            else:
                                self.worker_status = "github_comment_permission_missing"
                        except (ValueError, TypeError, aiohttp.ClientError):
                            self.worker_status = "task_error"
                except (aiohttp.ClientError, asyncio.TimeoutError, ValueError):
                    self.worker_status = "github_network_error"
                await asyncio.sleep(12)


bridge = Bridge()


def json_result(data):
    return web.json_response(data, headers={"Cache-Control": "no-store"})


@web.middleware
async def guard(request, handler):
    if request.method == "POST":
        origin = request.headers.get("Origin")
        host = request.headers.get("Host")
        if origin not in (f"https://{host}", f"http://{host}"):
            return web.Response(status=403, text="Invalid origin")
        if request.content_length is not None and request.content_length > 4096:
            return web.Response(status=413, text="Request too large")
    result = await handler(request)
    result.headers["Cache-Control"] = "no-store"
    result.headers["X-Frame-Options"] = "DENY"
    result.headers["X-Content-Type-Options"] = "nosniff"
    return result


async def homepage(request):
    return web.Response(text=PAGE.read_text(encoding="utf-8"), content_type="text/html")


async def screenshot(request):
    async with bridge.lock:
        page = bridge.page()
        if not page:
            return web.Response(status=503, text="Browser unavailable")
        data = await page.screenshot(type="jpeg", quality=70, timeout=15000)
    return web.Response(body=data, content_type="image/jpeg")


async def status(request):
    async with bridge.lock:
        page = bridge.page()
        if not page:
            return json_result({"ready": False, "worker": bridge.worker_status})
        signed_in = await bridge.signed_in()
        return json_result({"ready": True, "url": page.url, "signed_in": signed_in,
                            "worker": bridge.worker_status})


async def control(request):
    action = request.match_info["action"]
    if action not in {"click", "type", "key", "scroll", "home", "submit"}:
        return web.Response(status=404)
    try:
        payload = await request.json()
    except (json.JSONDecodeError, ValueError):
        return web.Response(status=400, text="Invalid JSON")
    if action == "submit":
        if os.environ.get("BLUEPRINT_MANUAL_ONLY") != "1":
            return web.Response(status=403)
        outcome = await bridge.create_project(LED_PROMPT)
        bridge.worker_status = "last_submission_" + outcome
        return json_result({"outcome": outcome})
    async with bridge.lock:
        page = bridge.page()
        if not page:
            return web.Response(status=503)
        if action == "click":
            x, y = payload.get("x"), payload.get("y")
            if type(x) is not int or type(y) is not int or not 0 <= x < WIDTH or not 0 <= y < HEIGHT:
                return web.Response(status=400, text="Invalid coordinates")
            await page.mouse.click(x, y)
        elif action == "type":
            value = payload.get("value")
            if not isinstance(value, str) or len(value) > 1200:
                return web.Response(status=400)
            await page.keyboard.insert_text(value)
        elif action == "key":
            value = payload.get("value")
            if value not in {"Enter", "Tab", "Escape", "Backspace", "ArrowDown", "ArrowUp"}:
                return web.Response(status=400)
            await page.keyboard.press(value)
        elif action == "scroll":
            direction = payload.get("direction")
            if direction not in {"up", "down"}:
                return web.Response(status=400)
            await page.mouse.wheel(0, 550 if direction == "down" else -550)
        elif action == "home":
            page = next((p for p in bridge.ctx.pages if not p.is_closed() and
                         p.url.startswith(("https://blueprint.io/", "https://www.blueprint.io/"))), None)
            if page is None:
                page = await bridge.ctx.new_page()
            await page.goto(URL, wait_until="domcontentloaded", timeout=30000)
        await asyncio.sleep(0.35)
    return json_result({"ok": True})


async def make_app():
    await bridge.start()
    app = web.Application(middlewares=[guard], client_max_size=4096)
    app.add_routes([web.get("/", homepage), web.get("/screen", screenshot),
                    web.get("/status", status), web.post("/{action}", control)])
    async def cleanup(_):
        await bridge.stop()
    app.on_cleanup.append(cleanup)
    return app


if __name__ == "__main__":
    web.run_app(make_app(), host="0.0.0.0", port=8765, access_log=None)
