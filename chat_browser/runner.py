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
from urllib.parse import urlsplit

MAX_STEPS = 12
MAX_TEXT = 14000
ACTIONS = {"click", "fill", "press", "select", "check", "uncheck", "wait", "screenshot", "extract"}


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
    match = re.fullmatch(r"```(?:json)?\\s*\\n(.*?)\\n```", body, re.I | re.S)
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
        if step["action"] in {"click", "fill", "press", "select", "check", "uncheck", "extract"}:
            if not isinstance(step.get("selector"), str) or not 1 <= len(step["selector"]) <= 300:
                raise ValueError("A nonempty selector is required")
        if step["action"] in {"fill", "press", "select"}:
            if not isinstance(step.get("value"), str) or len(step["value"]) > 1000:
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
        # Validate all browser requests, including redirects, to block access to private networks.
        def route_request(route):
            try:
                require_public_url(route.request.url)
                route.continue_()
            except (ValueError, UnsafeTarget):
                route.abort()
        context.route("**/*", route_request)
        try:
            page.goto(task["url"], wait_until="domcontentloaded", timeout=30000)
            for i, step in enumerate(task["steps"], 1):
                action = step["action"]
                selector = step.get("selector", "")
                item = {"step": i, "action": action}
                if action == "click":
                    page.locator(selector).first.click()
                elif action == "fill":
                    page.locator(selector).first.fill(step["value"])
                elif action == "press":
                    page.locator(selector).first.press(step["value"])
                elif action == "select":
                    page.locator(selector).first.select_option(step["value"])
                elif action == "check":
                    page.locator(selector).first.check()
                elif action == "uncheck":
                    page.locator(selector).first.uncheck()
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
