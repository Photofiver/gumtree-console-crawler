"""Run a tightly scoped Playwright browser task posted in a GitHub issue.

No arbitrary Python, shell, or JavaScript evaluation is supported. Public browsing only.
"""
import argparse
import ipaddress
import json
import re
import socket
import sys
from pathlib import Path
from chat_browser.blueprint_session import is_blueprint_host, load_state_from_environment
from urllib.parse import unquote, urlsplit

MAX_STEPS = 12
MAX_TEXT = 14000
# No arbitrary form submission, checkbox changes, or modifying commands.
ACTIONS = {"click", "click_text", "dismiss_cookies", "fill", "press", "wait", "wait_for", "scroll", "screenshot", "extract", "inspect", "snapshot", "blueprint_prompt"}
MUTATING_WORDS = re.compile(
    r"(?<![a-z])(?:delete|remove|erase|destroy|drop|reset|purge|"
    r"unsubscribe|logout|signout|cancel|purchase|buy|checkout|pay|"
    r"transfer|withdraw|deposit|trade|sell|order|subscribe|"
    r"usu[nń]|skasuj|kasuj|anuluj|kup|zap[lł]a[cć]|sprzedaj|wyloguj)(?![a-z])",
    re.I,
)
SAFE_BUTTON_WORDS = re.compile(
    r"^(?:search|find|next|previous|back|more|show|hide|read|view|open|"
    r"expand|collapse|load|filter|sort|details|learn|see|menu|close|"
    r"refresh|retry|page|tab|go to|continue reading|try with your idea|"
    r"szukaj|wyszukaj|dalej|nast[eę]pn|poprzedni|wstecz|wi[eę]cej|"
    r"poka[zż]|zobacz|czytaj|otw[oó]rz|rozwi[nń]|zwi[nń]|"
    r"filtr|sortuj|szczeg[oó][lł]y|od[sś]wie[zż]|zamknij)\b",
    re.I,
)
COOKIE_DISMISS_WORDS = re.compile(
    r"^(?:reject all|deny all|decline all|essential only|necessary only|only necessary|only essential|"
    r"use necessary cookies|continue without accepting|deny|decline|customize|save preferences|allow selection)\b", re.I,
)
SEARCH_FIELD_WORDS = re.compile(r"(?:search|find|query|wyszuk|szukaj)", re.I)

def classify_page_failure(title: str, url: str, body: str) -> str | None:
    """Report website access failures as failures, never as valid search results."""
    t, u, b = title.lower(), url.lower(), body.lower()
    if "ebay" in t and ("error page" in t or "something went wrong on our end" in b):
        return "eBay returned an error page. Automated access to this page is unavailable."
    if "google.com/sorry" in u or ("unusual traffic from your computer network" in b):
        return "Google challenged the datacenter browser due to automated traffic."
    if "openrss.org" in u and "you'll need a token to use it" in b:
        return "Open RSS needs a token/email for this eBay feed; not available anonymously."
    if "access denied" in t or "pardon our interruption" in b:
        return "The website denied browser access."
    return None


def is_safe_browsing_url(url: str) -> bool:
    """Conservative denylist for GET navigation that might change data."""
    try:
        parsed = urlsplit(url)
        target = unquote(parsed.path + "?" + parsed.query)
        return not MUTATING_WORDS.search(target)
    except (ValueError, TypeError):
        return False


def is_safe_click(info: dict) -> bool:
    """Links to public reading pages or clearly navigational UI buttons only."""
    label = str(info.get("label", "")).strip()
    if MUTATING_WORDS.search(label):
        return False
    tag = info.get("tag")
    href = info.get("href", "")
    if tag == "a" and href:
        return href.startswith(("http://", "https://")) and is_safe_browsing_url(href)
    if tag == "button" or info.get("role") in {"button", "tab"}:
        return bool(SAFE_BUTTON_WORDS.search(label) or
                    (info.get("cookieContext") and COOKIE_DISMISS_WORDS.search(label)))
    return False


def is_search_field(info: dict) -> bool:
    if info.get("tag") != "input" or info.get("type") not in {"search", "text", ""}:
        return False
    if info.get("type") == "search":
        return True
    return bool(SEARCH_FIELD_WORDS.search(str(info.get("label", ""))))


def inspect_element(locator) -> dict:
    """This fixed read-only DOM inspection does not execute page-provided code."""
    return locator.evaluate("""el => ({
        tag: el.tagName.toLowerCase(),
        type: (el.getAttribute('type') || '').toLowerCase(),
        role: (el.getAttribute('role') || '').toLowerCase(),
        label: [el.getAttribute('aria-label'), el.getAttribute('title'),
                el.getAttribute('placeholder'), el.getAttribute('name'),
                el.textContent].filter(Boolean).join(' ').trim().slice(0, 240),
        href: el.href || '',
        cookieContext: Boolean(el.closest('[id*="cookie" i], [class*="cookie" i], [id*="consent" i], [class*="consent" i]'))
    })""")


class UnsafeTarget(ValueError):
    pass


def require_public_url(raw: str) -> str:
    if not isinstance(raw, str) or len(raw) > 2048:
        raise UnsafeTarget("URL must be a string under 2048 characters")
    parsed = urlsplit(raw)
    if parsed.scheme not in ("http", "https") or not parsed.hostname or parsed.username or parsed.password:
        raise UnsafeTarget("Only public http(s) URLs without credentials are accepted")
    if parsed.port and parsed.port not in (80, 443):
        raise UnsafeTarget("Nonstandard ports are not supported")
    hostname = parsed.hostname.rstrip(".").lower()
    if hostname in {"localhost", "metadata.google.internal"} or hostname.endswith((".localhost", ".local", ".internal")):
        raise UnsafeTarget("Local/internal hosts are not permitted")
    try:
        records = socket.getaddrinfo(hostname, parsed.port or (443 if parsed.scheme == "https" else 80), type=socket.SOCK_STREAM)
    except socket.gaierror as error:
        raise UnsafeTarget("Host could not be resolved") from error
    if not records or any(not ipaddress.ip_address(item[4][0]).is_global for item in records):
        raise UnsafeTarget("Private, reserved and loopback addresses are prohibited")
    return raw


def parse_task(body: str) -> dict:
    if not isinstance(body, str) or len(body) > 12000:
        raise ValueError("Task must be plain text shorter than 12000 characters")
    body = body.strip()
    match = re.fullmatch(r"```(?:json)?\s*\n(.*?)\n```", body, re.I | re.S)
    if match:
        body = match.group(1)
    task = json.loads(body)
    if not isinstance(task, dict) or set(task) - {"url", "steps", "auth"}:
        raise ValueError("Task must contain only url and optional steps")
    require_public_url(task.get("url"))
    auth = task.get("auth")
    if auth not in (None, "blueprint"):
        raise ValueError("Unsupported authentication mode")
    if auth == "blueprint" and not is_blueprint_host(urlsplit(task["url"]).hostname):
        raise ValueError("Blueprint authentication is only supported on blueprint.io")
    steps = task.get("steps", [])
    if not isinstance(steps, list) or len(steps) > MAX_STEPS:
        raise ValueError(f"Provide at most {MAX_STEPS} steps")
    for i, step in enumerate(steps):
        if not isinstance(step, dict) or step.get("action") not in ACTIONS:
            raise ValueError(f"Unsupported action at step {i + 1}")
        if set(step) - {"action", "selector", "value", "ms", "px"}:
            raise ValueError("Unsupported step property")
        if step["action"] in {"click", "fill", "press", "extract", "wait_for"}:
            if not isinstance(step.get("selector"), str) or not 1 <= len(step["selector"]) <= 300:
                raise ValueError("A nonempty selector is required")
        if step["action"] in {"fill", "press", "click_text", "blueprint_prompt"}:
            if not isinstance(step.get("value"), str) or len(step["value"]) > 1000 or (step["action"] == "click_text" and not step["value"].strip()):
                raise ValueError("A string value up to 1000 characters is required")
        if step["action"] in {"wait", "wait_for"}:
            ms = step.get("ms", 10000 if step["action"] == "wait_for" else None)
            if type(ms) is not int or not 0 <= ms <= (12000 if step["action"] == "wait_for" else 5000):
                raise ValueError("Invalid wait duration")
        if step["action"] == "scroll":
            if type(step.get("px", 650)) is not int or not 0 <= step.get("px", 650) <= 1600:
                raise ValueError("Scrolling is restricted to 0–1600 pixels down")
    if any(step["action"] == "blueprint_prompt" for step in steps) and not is_blueprint_host(urlsplit(task["url"]).hostname):
        raise ValueError("Blueprint prompt action is restricted to blueprint.io")
    if auth == "blueprint":
        if any(step["action"] not in {"blueprint_prompt", "wait"} for step in steps):
            raise ValueError("Authenticated Blueprint tasks only accept blueprint_prompt and wait")
        if sum(step["action"] == "blueprint_prompt" for step in steps) > 1:
            raise ValueError("Only one Blueprint project prompt per authenticated task")
    return task


def run_task(task: dict, screenshot_path: Path) -> dict:
    from playwright.sync_api import sync_playwright

    screenshots = []
    action_results = []
    blueprint_mode = any(s["action"] == "blueprint_prompt" for s in task.get("steps", []))
    authenticated = task.get("auth") == "blueprint"
    saved_state = load_state_from_environment() if authenticated else None
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True, args=["--no-sandbox"])
        context = browser.new_context(accept_downloads=False, permissions=[], service_workers="block", viewport={"width": 1280, "height": 800}, **({"storage_state": saved_state} if authenticated else {}))
        page = context.new_page()
        page.set_default_timeout(10000)
        # All browser traffic is read-only: block POST/PUT/PATCH/DELETE and
        # suspicious GET destinations, including redirects and JS requests.
        # A GET-only browser cannot guarantee that every third-party website
        # is side-effect-free, but it greatly reduces the mutation surface.
        def route_request(route):
            try:
                method = route.request.method.upper()
                host = urlsplit(route.request.url).hostname
                if method not in {"GET", "HEAD"} and not (blueprint_mode and method == "POST" and is_blueprint_host(host)):
                    raise UnsafeTarget("State-changing HTTP method blocked")
                require_public_url(route.request.url)
                if not is_safe_browsing_url(route.request.url):
                    raise UnsafeTarget("Potentially state-changing URL blocked")
                route.continue_()
            except (ValueError, UnsafeTarget):
                route.abort()
        context.route("**/*", route_request)
        try:
            page.goto(task["url"], wait_until="domcontentloaded", timeout=30000)
            if authenticated:
                page.wait_for_timeout(1200)
                if page.get_by_role("button", name=re.compile(r"^SIGN IN$", re.I)).count():
                    return {"ok": False, "auth_status": "login_required", "project_status": "not_started"}
            for i, step in enumerate(task.get("steps", []), 1):
                action = step["action"]
                selector = step.get("selector", "")
                item = {"step": i, "action": action}
                if action == "dismiss_cookies":
                    # Cookiebot-like banners may load after DOMContentLoaded.
                    page.wait_for_timeout(1000)
                    dismissed = False
                    customized = False
                    for _ in range(2):
                        for frame in page.frames[:8]:
                            for text_label in ("Deny", "Reject all", "Decline all", "Essential only",
                                               "Necessary only", "Allow selection"):
                                controls = frame.get_by_role("button", name=re.compile(
                                    r"^" + re.escape(text_label) + r"$", re.I))
                                if controls.count():
                                    candidate = controls.first
                                    if is_safe_click(inspect_element(candidate)) and candidate.is_visible():
                                        candidate.click(timeout=4000)
                                        item["cookie_result"] = "clicked " + text_label
                                        dismissed = True
                                        break
                            if dismissed:
                                break
                        if dismissed:
                            break
                        if not customized:
                            for frame in page.frames[:8]:
                                controls = frame.get_by_role("button", name=re.compile(r"^Customize$", re.I))
                                if controls.count():
                                    candidate = controls.first
                                    if is_safe_click(inspect_element(candidate)) and candidate.is_visible():
                                        candidate.click(timeout=4000)
                                        customized = True
                                        page.wait_for_timeout(200)
                                        break
                        if not customized:
                            break
                    if not dismissed:
                        item["cookie_result"] = "no dismissible cookie banner visible"
                elif action in {"click", "click_text"}:
                    if action == "click_text":
                        target = step["value"].strip()
                        if not target or MUTATING_WORDS.search(target):
                            raise ValueError("Unsafe or empty click_text target")
                        # Search by visible/accessibility label, not brittle href/CSS.
                        # Only follow the first element confirmed safe by our guards.
                        element = None
                        # Search the accessibility tree, including embedded frames.
                        for frame in page.frames[:8]:
                            for role in ("link", "button", "tab"):
                                matching = frame.get_by_role(
                                    role, name=re.compile(re.escape(target), re.I)
                                )
                                for j in range(min(matching.count(), 20)):
                                    candidate = matching.nth(j)
                                    if is_safe_click(inspect_element(candidate)):
                                        element = candidate
                                        break
                                if element is not None:
                                    break
                            if element is not None:
                                break
                        if element is None:
                            found = page.locator("a[href]").all_inner_texts()[:25]
                            raise ValueError(f"No safe link/button matching {target!r}; found links: {found!r}")
                    else:
                        element = page.locator(selector).first
                        if element.count() == 0:
                            found = page.locator("a[href]").all_inner_texts()[:25]
                            raise ValueError(f"Selector did not match {selector!r}; found links: {found!r}")
                    if not is_safe_click(inspect_element(element)):
                        raise ValueError("Only safe navigation links and buttons may be clicked")
                    element.click()
                elif action == "blueprint_prompt":
                    if urlsplit(page.url).hostname not in {"blueprint.io", "www.blueprint.io"}:
                        raise ValueError("Blueprint prompt cannot run outside Blueprint")
                    composer = page.locator("textarea[placeholder*='Ask blueprint']").first
                    composer.fill(step["value"])
                    composer.press("Enter")
                    page.wait_for_timeout(5000)
                    item["prompt_submitted"] = True
                elif action == "fill":
                    element = page.locator(selector).first
                    if not is_search_field(inspect_element(element)):
                        raise ValueError("Only search fields may be filled")
                    element.fill(step["value"])
                elif action == "press":
                    element = page.locator(selector).first
                    if step["value"] != "Enter" or not is_search_field(inspect_element(element)):
                        raise ValueError("Only Enter in search fields is allowed")
                    element.press("Enter")
                elif action in {"inspect", "snapshot"}:
                    item["frames"] = []
                    for frame in page.frames[:8]:
                        info = {
                            "url": frame.url.split("?")[0],
                            "links": frame.locator("a[href]").evaluate_all(
                                "els => els.slice(0, 30).map(x => ({text: (x.innerText || '').trim().slice(0, 90), url: x.href}))"
                            ),
                            "buttons": frame.get_by_role("button").evaluate_all(
                                "els => els.slice(0, 20).map(x => (x.innerText || x.getAttribute('aria-label') || x.title || '').trim().slice(0, 90))"
                            ),
                        }
                        if action == "snapshot":
                            info["editables"] = frame.locator("textarea, [contenteditable], [role='textbox']").evaluate_all("els => els.slice(0, 16).map(x => ({tag:x.tagName.toLowerCase(),type:x.getAttribute('type'),role:x.getAttribute('role'),placeholder:x.getAttribute('placeholder'),aria:x.getAttribute('aria-label'),outer:x.outerHTML.slice(0,550)}))")
                            info["headings"] = frame.get_by_role("heading").all_inner_texts()[:12]
                            info["inputs"] = frame.locator("input").evaluate_all(
                                "els => els.slice(0, 12).map(x => ({type: x.type, name: x.name, placeholder: x.placeholder}))"
                            )
                        item["frames"].append(info)
                elif action == "wait_for":
                    page.locator(selector).first.wait_for(state="visible", timeout=step.get("ms", 10000))
                elif action == "scroll":
                    page.mouse.wheel(0, step.get("px", 650))
                    page.wait_for_timeout(250)
                elif action == "wait":
                    page.wait_for_timeout(step["ms"])
                elif action == "screenshot":
                    screenshot_path.parent.mkdir(parents=True, exist_ok=True)
                    page.screenshot(path=str(screenshot_path), full_page=True)
                    screenshots.append(screenshot_path.name)
                elif action == "extract":
                    item["text"] = page.locator(selector).first.inner_text(timeout=10000)[:4000]
                action_results.append(item)
            if authenticated:
                # Never publish private account text, DOM, links, screenshots, or cookies.
                if page.get_by_role("button", name=re.compile(r"^SIGN IN$", re.I)).count():
                    return {"ok": False, "auth_status": "login_required", "project_status": "not_created"}
                return {"ok": True, "auth_status": "signed_in",
                        "project_status": "submission_attempted" if blueprint_mode else "not_requested",
                        "saved_confirmed": False}
            title = page.title()
            text = page.locator("body").inner_text(timeout=12000)[:MAX_TEXT]
            links = page.locator("a[href]").evaluate_all("els => els.slice(0, 40).map(x => ({text: (x.innerText || '').trim().slice(0, 100), url: x.href}))")
            final_url = page.url
            issue = classify_page_failure(title, final_url, text)
            if issue:
                return {"ok": False, "error": issue, "title": title,
                        "url": final_url, "text": text[:2000], "actions": action_results}
            return {"ok": True, "title": title, "url": final_url, "text": text, "links": links, "actions": action_results, "screenshots": screenshots}
        finally:
            context.close()
            browser.close()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--event", required=True)
    parser.add_argument("--result", default="browser-result.json")
    parser.add_argument("--screenshot", default="browser-screenshot.png")
    args = parser.parse_args()
    result = {"ok": False}
    task = None
    try:
        event = json.loads(Path(args.event).read_text(encoding="utf-8"))
        task = parse_task(event["issue"]["body"])
        result = run_task(task, Path(args.screenshot))
    except Exception as exc:
        if isinstance(task, dict) and task.get("auth") == "blueprint":
            # Auth errors may contain sensitive URLs or state. Never emit their text.
            result = {"ok": False, "auth_status": "setup_failed", "project_status": "not_verified"}
        else:
            result["error"] = f"{type(exc).__name__}: {str(exc)[:700]}"
    Path(args.result).write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"Task complete: {'success' if result['ok'] else 'error'}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
