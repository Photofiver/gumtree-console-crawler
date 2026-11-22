"""Reuse a booted Android emulator for new Google AI issues; renew by scheduled Actions runs.

The worker keeps the emulator running for the configured window. The instrumented
WebView restarts per question: GitHub-hosted runners cannot transfer live tabs.
Only accept requests opened by the repository owner; never print issue bodies.
"""
import argparse
import base64
from datetime import datetime, timedelta, timezone
import json
import os
from pathlib import Path
import subprocess
import tempfile
import time
from urllib.error import HTTPError
from urllib.request import Request, urlopen

import review

REPO = os.environ["GITHUB_REPOSITORY"]
TOKEN = os.environ.get("GITHUB_TOKEN")
OWNER = REPO.split("/", 1)[0]
ROOT = "https://api.github.com/repos/" + REPO
APP_FILES = "/sdcard/Android/data/com.photofiver.phonebrowser/files/"
INSTRUMENT = [
    "adb", "shell", "am", "instrument", "-w", "-r",
    "-e", "class", "com.photofiver.phonebrowser.GoogleAskTest",
    "com.photofiver.phonebrowser.test/androidx.test.runner.AndroidJUnitRunner",
]


def api(method, path, payload=None):
    body = json.dumps(payload).encode() if payload is not None else None
    req = Request(
        ROOT + path,
        data=body,
        method=method,
        headers={
            "Authorization": "Bearer " + TOKEN,
            "Accept": "application/vnd.github+json",
            "X-GitHub-Api-Version": "2022-11-28",
            "User-Agent": "google-ai-warm-worker",
            **({"Content-Type": "application/json"} if body is not None else {}),
        },
    )
    with urlopen(req, timeout=20) as resp:
        data = resp.read()
    return json.loads(data) if data else None


def is_ours(issue, test_mode):
    if issue.get("user", {}).get("login", "").lower() != OWNER.lower():
        return False
    title = issue.get("title", "")
    return title.startswith("[google-warm-test]") if test_mode else title.startswith(("[google-ask]", "[consult]"))


def is_answered(number):
    comments = api("GET", "/issues/" + str(number) + "/comments?per_page=100")
    return any(c.get("user", {}).get("login") == "github-actions[bot]" for c in comments)


def format_question(issue):
    title, body = issue["title"], issue.get("body") or ""
    if title.startswith("[google-ask] [review]"):
        with tempfile.NamedTemporaryFile() as env_file:
            previous = os.environ.get("GITHUB_ENV")
            os.environ["GITHUB_ENV"] = env_file.name
            try:
                review.prepare({"issue": {"body": body}})
                req = json.loads(Path("review-request.json").read_text())
            finally:
                if previous is None:
                    os.environ.pop("GITHUB_ENV", None)
                else:
                    os.environ["GITHUB_ENV"] = previous
        return req["query"], req
    if len(body.encode("utf-8")) > 2000:
        raise ValueError("Question must fit in 2000 UTF-8 bytes")
    return body.strip(), None


def ask_emulator(question):
    encoded = base64.b64encode(question.encode("utf-8")).decode("ascii")
    path = APP_FILES + "google-ai-ask-result.json"
    subprocess.run(["adb", "shell", "rm", "-f", path], timeout=15, check=True)
    started = time.monotonic()
    command = INSTRUMENT[:6] + ["-e", "q_b64", encoded] + INSTRUMENT[6:]
    # Protect against the emulator hanging; retain a clear error instead of a fake answer.
    proc = subprocess.run(command, capture_output=True, text=True, timeout=125)
    elapsed = round(time.monotonic() - started, 1)
    if proc.returncode != 0 or "OK (1 test)" not in proc.stdout:
        raise RuntimeError("Android instrumentation failed after " + str(elapsed) + "s: " +
                           (proc.stderr + proc.stdout)[-550:])
    with tempfile.NamedTemporaryFile(suffix=".json") as f:
        subprocess.run(["adb", "pull", path, f.name], capture_output=True,
                       check=True, timeout=20)
        data = json.loads(Path(f.name).read_text())
    if data.get("question") != question:
        raise RuntimeError("Mismatched Google AI response question")
    page = data.get("page") or {}
    if not str(page.get("url", "")).startswith("https://www.google.com/search?") or "net::ERR_" in str(page.get("text", "")):
        raise RuntimeError("Google AI webpage did not load (Android DNS/network error)")
    print("Android answer read in", elapsed, "seconds", flush=True)
    return data


def format_result(result, req):
    if req is not None:
        return "Google AI: " + review.decide(req, result)
    page = result.get("page") or {}
    if not result.get("aiResponseReady"):
        return "Google AI: NIEPOTWIERDZONE\\n\\nGoogle AI response not ready or unavailable.".replace("\\n","\n")
    return (
        "Google AI Mode answer (unverified, may contain mistakes):\n\n"
        + "QUESTION: " + str(result.get("question", ""))
        + "\n\nPAGE: " + str(page.get("url") or result.get("loadUrl", ""))
        + "\n\nTEXT:\n" + str(page.get("text") or "NO TEXT")
        + "\n\nSOURCE LINKS: " + json.dumps(page.get("sourceLinks") or [], ensure_ascii=False)
        + "\n\nAI RESPONSE READY: " + str(bool(result.get("aiResponseReady")))
    )


_ATTENTION_MODEL = None


def review_consult(issue):
    """Review a [consult] packet in the already-booted emulator.

    Keep the source screening and trained Attention separate from the actual
    Google AI verdict. No GitHub-side edits or invented verified products.
    """
    global _ATTENTION_MODEL
    from consult import review_for_chatgpt
    from attention_guard import build_focus, MODEL_ID
    from explore import screen

    data = json.loads(issue.get("body") or "{}")
    if not isinstance(data, dict):
        raise ValueError("Consultation body must be a JSON object")
    attention = {"status": "unavailable", "reason": "model_not_ready"}
    try:
        from sentence_transformers import SentenceTransformer
        if _ATTENTION_MODEL is None:
            _ATTENTION_MODEL = SentenceTransformer(MODEL_ID, trust_remote_code=False)
        attention = build_focus(data, _ATTENTION_MODEL)
    except Exception as exc:
        attention = {"status": "unavailable", "reason": type(exc).__name__,
                     "error_detail": str(exc)[:200]}
    data["attention"] = attention

    exploration = None
    exploration_error = None
    if data.get("idea_target") in (100, 1000):
        try:
            exploration = screen(data, data["idea_target"])["summary"]
        except (ValueError, TypeError, KeyError) as exc:
            exploration_error = str(exc)[:350]

    result = review_for_chatgpt(data, ask_emulator)
    result["issue"] = issue["number"]
    result["attention"] = {k: v for k, v in attention.items()
                           if k in ("status", "model", "reason", "error_detail", "ranked_indices")}
    if exploration is not None:
        result["exploration"] = exploration
    if exploration_error is not None:
        result["exploration_error"] = exploration_error

    # A failed warm transport is not a completed review. Let the ordinary
    # issue workflow provide the cold fallback rather than post a fake receipt.
    if result.get("google_ai_responses_received", 0) == 0:
        print("Warm consult had no Google AI response; cold fallback retained", flush=True)
        return None
    payload = json.dumps(result, ensure_ascii=False)
    if len(payload.encode("utf-8")) > 57000:
        # Original draft and evidence remain in the issue; do not cut a reason
        # or fabricate a success to fit GitHub's comment size limit.
        result.pop("history", None)
        result.pop("draft", None)
        result.pop("checks", None)
        payload = json.dumps(result, ensure_ascii=False)
    if len(payload.encode("utf-8")) > 57000:
        result.pop("google_ai_audit", None)
        if "exploration" in result:
            result["exploration"].pop("shortlist", None)
        payload = json.dumps(result, ensure_ascii=False)
    if len(payload.encode("utf-8")) > 57000:
        raise ValueError("Consultation receipt too large; cold fallback required")
    return "Konsultant/2 " + payload


def handle(issue):
    number = issue["number"]
    if is_answered(number):
        return False
    if issue["title"].startswith("[consult]"):
        try:
            text = review_consult(issue)
        except Exception as exc:
            print("Warm consultation error for issue #", number, ":",
                  type(exc).__name__, str(exc)[:250], flush=True)
            return False
        if text is None:
            return False
        if is_answered(number):
            return True
        api("POST", "/issues/" + str(number) + "/comments", {"body": text})
        print("Posted warm Google AI consultation for issue #", number, flush=True)
        return True
    try:
        question, req = format_question(issue)
        if not question:
            raise ValueError("Question body is empty")
        for attempt in range(2):
            try:
                answer = ask_emulator(question)
                text = format_result(answer, req)
                # Google AI may not follow the exact reviewer token on one load.
                # Retry once; do not expose an intermediate unconfirmed result.
                if text.startswith("Google AI: NIEPOTWIERDZONE") and attempt == 0:
                    print("Google AI review incomplete; retrying once", flush=True)
                    time.sleep(4)
                    continue
                break
            except RuntimeError:
                if attempt == 1:
                    raise
                print("Warm Android answer failed, retrying once", flush=True)
                time.sleep(5)
    except Exception as exc:
        text = "Google AI: NIEPOTWIERDZONE\n\nWarm browser error: " + type(exc).__name__ + ": " + str(exc)[:700]
    # In production a warm-session failure is provisional. The per-issue cold
    # workflow remains the final fallback and MUST own the unconfirmed verdict.
    # Posting early would make ChatGPT stop before the fallback finishes.
    if text.startswith("Google AI: NIEPOTWIERDZONE") and not issue["title"].startswith("[google-warm-test]"):
        print("Warm result unconfirmed for issue #", number,
              "; withholding provisional comment and leaving cold fallback active", flush=True)
        return False
    # Recheck to avoid duplicating a reply while the original per-issue workflow runs.
    if is_answered(number):
        return True
    api("POST", "/issues/" + str(number) + "/comments", {"body": text[:58000]})
    print("Posted Google AI result to issue #", number, flush=True)
    return True


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--runtime-minutes", type=int, default=315)
    parser.add_argument("--test-issue", type=int, default=0)
    args = parser.parse_args()
    deadline = time.monotonic() + args.runtime_minutes * 60
    started = datetime.now(timezone.utc)
    seen = set()
    last_ping = 0
    print("Google AI warm Android session started, max duration", args.runtime_minutes, "minutes", flush=True)
    while time.monotonic() < deadline:
        try:
            if args.test_issue:
                issue = api("GET", "/issues/" + str(args.test_issue))
                if is_ours(issue, True):
                    handle(issue)
                else:
                    print("Test issue not created by owner or wrong prefix", flush=True)
                break
            issues = api("GET", "/issues?state=open&sort=created&direction=desc&per_page=50")
            cutoff = started - timedelta(minutes=15)
            for issue in reversed(issues):
                if not is_ours(issue, False) or "pull_request" in issue:
                    continue
                number = issue["number"]
                if number in seen:
                    continue
                created = datetime.fromisoformat(issue["created_at"].replace("Z", "+00:00"))
                if created < cutoff:
                    continue
                # Check comments before the expensive browser call.
                if is_answered(number):
                    seen.add(number)
                    continue
                if time.monotonic() + 150 >= deadline:
                    break
                seen.add(number)
                print("Serving issue #", number, "using warm emulator", flush=True)
                handle(issue)
            if time.monotonic() - last_ping >= 300:
                print("Warm browser watchdog heartbeat", datetime.now(timezone.utc).isoformat(), flush=True)
                last_ping = time.monotonic()
        except (HTTPError, OSError, subprocess.SubprocessError, ValueError) as exc:
            print("Warm browser watchdog check error:", repr(exc)[:550], flush=True)
        # Poll often enough for quick questions without exceeding the usual
        # per-repository GITHUB_TOKEN API hourly budget (~600 polls/hour).
        time.sleep(6)
    print("Warm session finished normally; next scheduled run starts a fresh emulator.", flush=True)


if __name__ == "__main__":
    main()
