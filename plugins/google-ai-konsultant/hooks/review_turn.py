"""Wait for the authenticated workflow receipt for this issue and exact body."""
import argparse
import hashlib
import json
import re
import os
import tempfile
from pathlib import Path
import sys
import time
from urllib.request import Request, urlopen

REPO = "Photofiver/gumtree-console-crawler"
LINK = "https://github.com/" + REPO + "/issues/"
FLOW = "google-ai-ask.yml"


def fetch(path):
    req = Request("https://api.github.com/repos/" + REPO + path,
                  headers={"User-Agent": "Google-AI-Konsultant"})
    with urlopen(req, timeout=8) as response:
        return json.load(response)


def lookup(number, read=fetch):
    path = "/issues/" + str(number)
    issue = read(path)
    if issue["user"]["login"] != "Photofiver" or not issue["title"].startswith("[consult]"):
        raise ValueError("Unexpected issue owner or title")
    expected = hashlib.sha256(issue["body"].encode()).hexdigest()
    runs = read("/actions/workflows/" + FLOW + "/runs?event=issues&per_page=100")["workflow_runs"]
    run = next((r for r in runs if r["display_title"] == "Google AI issue #" + str(number)), None)
    if not run:
        return {"pending": "queued", "title": issue["title"]}
    for comment in reversed(read(path + "/comments?per_page=100")):
        if comment["user"]["login"] != "github-actions[bot]" or not comment["body"].startswith("Konsultant/2 "):
            continue
        result = json.loads(comment["body"].split(" ", 1)[1])
        if result.get("sha256") == expected and result.get("run") == run["id"] and result.get("issue") == number:
            return dict(result, title=issue["title"])
    if run["status"] == "completed":
        return {"status":"NIEPOTWIERDZONE", "reason":"Workflow completed without a matching receipt: " + str(run["conclusion"]), "title":issue["title"]}
    return {"pending":run["status"], "title":issue["title"]}


def wait(number, lookup_fn=lookup, timeout=1620, clock=time.monotonic, sleep=time.sleep):
    end = clock() + timeout
    last = "queued"
    while clock() < end:
        try:
            result = lookup_fn(number)
            if "pending" not in result:
                return result
            last = result["pending"]
        except (ValueError, OSError, KeyError) as exc:
            last = str(exc)
        sleep(min(30, max(0, end-clock())))
    return {"status":"NIEPOTWIERDZONE", "reason":"Timeout: "+last}


def evaluate(event, read=fetch):
    tag = hashlib.sha256((str(event.get("session_id","")) + "\0" + str(event.get("turn_id",""))).encode()).hexdigest()[:24]
    title = "[consult] " + tag
    stamp = Path(tempfile.gettempdir()) / ("konsultant-" + str(os.getuid()) + "-" + tag)

    instruction = ("Utwórz issue o tytule " + title + ". Użyj protokołu 1.7.1 z SKILL.md. "
                   "Odbierz końcowy wynik, sprawdź dowody i wymagania. Podaj link do issue.")
    if event.get("hook_event_name") == "UserPromptSubmit":
        try:
            with stamp.open("x") as handle:
                handle.write(str(time.time()))
        except FileExistsError:
            pass
        return {"hookSpecificOutput":{"hookEventName":"UserPromptSubmit","additionalContext":instruction}}
    message = event.get("last_assistant_message") or ""
    matches = re.findall(re.escape(LINK) + r"([1-9]\d*)",message)
    match = matches[-1] if matches else None
    if message.startswith("NIEPOTWIERDZONE"):
        if not match and "Brak dostępu:" in message:
            return {}
        try:
            if "Timeout:" in message and time.time() - float(stamp.read_text()) >= 1620:
                return {}
        except (OSError, ValueError):
            pass
    if match:
        try:
            receipt = lookup(int(match), read)
            current = re.fullmatch(re.escape(title) + r"(?: /([23]))?", receipt.get("title", ""))
            if current:
                attempt = int(current[1] or "1")
                if "pending" in receipt:
                    return {"decision":"block","reason":f"Trwa workflow issue #{match}. Oczekuj na to samo zgłoszenie przez --wait {match}."}
                if receipt.get("review") == "DO POPRAWY" and attempt < 3 and len(receipt.get("history", [])) < 3:
                    return {"decision":"block","reason":("Sprawdź uzasadnienie: " + receipt.get("reason","")
                            + f". Popraw analizę i wyślij zmieniony szkic jako {title} /{attempt+1}, parent_issue={match}.")}
                status = receipt.get("status")
                if status in ("POTWIERDZONE","NIEPOTWIERDZONE") and status in message.split():
                    if status == "POTWIERDZONE" and receipt.get("draft","").strip() not in message:
                        return {"decision":"block","reason":"Dołącz dokładny zatwierdzony szkic do odpowiedzi."}
                    return {}
        except (ValueError, KeyError, OSError):
            pass
    return {"decision":"block","reason":instruction}


if __name__ == "__main__":
    if len(sys.argv) == 1:
        print(json.dumps(evaluate(json.load(sys.stdin)), ensure_ascii=False))
    else:
        parser = argparse.ArgumentParser()
        parser.add_argument("--wait", type=int, required=True)
        args = parser.parse_args()
        print(json.dumps(wait(args.wait), ensure_ascii=False))
