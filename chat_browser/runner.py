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
from urllib.parse import unquote, urlsplit

MAX_STEPS = 12
MAX_TEXT = 14000
# No arbitrary form submission, checkbox changes, or modifying commands.
ACTIONS = {"click", "click_text", "fill", "press", "wait", "screenshot", "extract", "inspect"}
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
    r"refresh|retry|page|tab|go to|continue reading|"
    r"szukaj|wyszukaj|dalej|nast[eę]pn|poprzedni|wstecz|wi[eę]cej|"
    r"poka[zż]|zobacz|czytaj|otw[oó]rz|rozwi[nń]|zwi[nń]|"
    r"filtr|sortuj|szczeg[oó][lł]y|od[sś]wie[zż]|zamknij)\b",
    re.I,
)
SEARCH_FIELD_WORDS = re.compile(r"(?:search|find|query|wyszuk|szukaj)", re.I)


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
        return bool(SAFE_BUTTON_WORDS.search(label))
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
        href: el.href || ''
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
    if not isinstance(task, dict) or set(task) - {"url", "steps"}:
        raise ValueError("Task must contain only url and optional steps")
    require_public_url(task.get("url"))
    steps = task.get("steps", [])
    if not isinstance(steps, list) or len(steps) > MAX_STEPS:
        raise ValueError(f"Provide at most {MAX_STEPS} steps")
    for i, step in enumerate(steps):
        if not isinstance(step, dict) or step.get("action") not in ACTIONS:
            raise ValueError(f"Unsupported action at step {i + 1}")
        if set(step) - {"action", "selector", "value", "ms"}:
            raise ValueError("Unsupported step property")
        if step["action"] in {"click", "fill", "press", "extract"}:
            if not isinstance(step.get("selector"), str) or not 1 <= len(step["selector"]) <= 300:
                raise ValueError("A nonempty selector is required")
        if step["action"] in {"fill", "press", "click_text"}:
            if not isinstance(step.get("value"), str) or len(step["value"]) > 1000 or (step["action"] == "click_text" and not step["value"].strip()):
                raise ValueError("A string value up to 1000 characters is required")
        if step["action"] == "wait":
            if not isinstance(step.get("ms"), int) or not 0 <= step["ms"] <= 5000:
                raise ValueError("Wait must be between 0 and 5000 milliseconds")
    return task


def run_task(task: dict, screenshot_path: Path) -> dict:
    from playwright.sync_api import sync_playwright

    screenshots = []
    action_results = []
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True, args=["--no-sandbox"])
        context = browser.new_context(accept_downloads=False, permissions=[], viewport={"width": 1280, "height": 800})
        page = context.new_page()
        page.set_default_timeout(10000)
        # All browser traffic is read-only: block POST/PUT/PATCH/DELETE and
        # suspicious GET destinations, including redirects and JS requests.
        # A GET-only browser cannot guarantee that every third-party website
        # is side-effect-free, but it greatly reduces the mutation surface.
        def route_request(route):
            try:
                if route.request.method.upper() not in {"GET", "HEAD"}:
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
            for i, step in enumerate(task.get("steps", []), 1):
                action = step["action"]
                selector = step.get("selector", "")
                item = {"step": i, "action": action}
                if action in {"click", "click_text"}:
                    if action == "click_text":
                        target = step["value"].strip()
                        if not target or MUTATING_WORDS.search(target):
                            raise ValueError("Unsafe or empty click_text target")
                        # Search by visible/accessibility label, not brittle href/CSS.
                        # Only follow the first element confirmed safe by our guards.
                        candidates = (
                            page.get_by_role("link", name=re.compile(re.escape(target), re.I)),
                            page.get_by_role("button", name=re.compile(re.escape(target), re.I)),
                            page.get_by_role("tab", name=re.compile(re.escape(target), re.I)),
                        )
                        element = None
                        for matching in candidates:
                            for j in range(min(matching.count(), 20)):
                                item_locator = matching.nth(j)
                                if is_safe_click(inspect_element(item_locator)):
                                    element = item_locator
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
                elif action == "inspect":
                    item["links"] = page.locator("a[href]").evaluate_all(
                        "els => els.slice(0, 40).map(x => ({text: (x.innerText || '').trim().slice(0, 100), url: x.href}))"
                    )
                    item["buttons"] = page.get_by_role("button").evaluate_all(
                        "els => els.slice(0, 30).map(x => (x.innerText || x.getAttribute('aria-label') || x.title || '').trim().slice(0, 100))"
                    )
                elif action == "wait":
                    page.wait_for_timeout(step["ms"])
                elif action == "screenshot":
                    screenshot_path.parent.mkdir(parents=True, exist_ok=True)
                    page.screenshot(path=str(screenshot_path), full_page=True)
                    screenshots.append(screenshot_path.name)
                elif action == "extract":
                    item["text"] = page.locator(selector).first.inner_text(timeout=10000)[:4000]
                action_results.append(item)
            title = page.title()
            text = page.locator("body").inner_text(timeout=12000)[:MAX_TEXT]
            links = page.locator("a[href]").evaluate_all("els => els.slice(0, 40).map(x => ({text: (x.innerText || '').trim().slice(0, 100), url: x.href}))")
            final_url = page.url
            if (
                ("error page" in title.lower() and ("ebay" in title.lower()))
                or "something went wrong on our end" in text.lower()
                or ("access denied" in title.lower())
                or ("unusual traffic" in text.lower() and "automated" in text.lower())
            ):
                return {"ok": False, "error": "Website returned an error or access-blocking page",
                        "title": title, "url": final_url, "text": text[:2000], "actions": action_results}
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
    try:
        event = json.loads(Path(args.event).read_text(encoding="utf-8"))
        task = parse_task(event["issue"]["body"])
        result = run_task(task, Path(args.screenshot))
    except Exception as exc:
        result["error"] = f"{type(exc).__name__}: {str(exc)[:700]}"
    Path(args.result).write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"Task complete: {'success' if result['ok'] else 'error'}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
