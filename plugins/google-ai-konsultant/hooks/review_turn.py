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
        if (result.get("sha256") == expected and result.get("issue") == number
                and result.get("run", run["id"]) == run["id"]):
            return dict(result, title=issue["title"], issue_created_at=issue.get("created_at"))
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

    instruction = ("To CHATGPT, a NIE GitHub, analizuje problem, wyszukuje produkty i "
                   "źródła, poprawia szkic po uwagach Google AI i wysyła nowy [consult]. "
                   "GitHub tylko przesiewa konfiguracje, wysyła pytania do Google AI i "
                   "oddaje uwagi. Dla bieżącej tury utwórz issue o tytule " + title +
                   " z aktualnym pytaniem, szkicem i checklistą dowodów. "
                   "Po utworzeniu issue NATYCHMIAST odczytuj status tego samego " +
                   "issue w tej samej aktywnej turze; jeśli workflow jeszcze trwa, " +
                   "polluj ponownie, nie kończ tury na samym linku do GitHub. " +
                   "Odczytaj faktyczne Google AI feedback; w przypadku DO POPRAWY "
                   "lub NIEPOTWIERDZONE SAMODZIELNIE sprawdź źródła, zmień szkic "
                   "i wyślij nowe issue z parent_issue. Nie proś GitHub o pisanie "
                   "lub wymyślanie poprawek. Nie deklaruj POTWIERDZONE bez "
                   "pozytywnego audytu Google AI i prawdziwych dowodów.")
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
    if not match:
        return {"decision":"block","reason":instruction+" Brak zgłoszenia GitHub dla bieżącej tury."}
    if match:
        try:
            receipt = lookup(int(match), read)
            current = re.fullmatch(re.escape(title) + r"(?: /([1-9]\\d*))?", receipt.get("title", ""))
            if current:
                attempt = int(current[1] or "1")
                if "pending" in receipt:
                    # Give the already-running Google workflow time to post its
                    # authenticated answer before ChatGPT is allowed to stop.
                    # Stay below the 40-second host Stop-hook limit.
                    if read is fetch and getattr(lookup, "__name__", None) == "lookup":
                        receipt = wait(int(match), timeout=16)
                    if "pending" in receipt or receipt.get("reason", "").startswith("Timeout:"):
                        return {"decision":"block","reason":(
                            f"Google AI dla issue #{match} nadal pracuje. TO NIE JEST "
                            "ODPOWIEDŹ KOŃCOWA. Kontynuuj TĘ SAMĄ turę ChatGPT: "
                            f"odczytaj GitHub issue #{match} i komentarze Konsultant/2, "
                            "ponawiaj sprawdzanie do otrzymania uwierzytelnionego "
                            "wyniku albo jawnej awarii workflow. Nie kończ tury "
                            "tylko dlatego, że Google jeszcze nie odpowiedziało. "
                            f"Dostępna funkcja oczekiwania: --wait {match}.")}
                correction_needed = (receipt.get("review") == "DO POPRAWY" or
                                     receipt.get("next_action") == "chatgpt_research_revise_and_resubmit")
                if correction_needed:
                    exhausted = receipt.get("resolution_status") in ("physically_impossible", "evidence_exhausted")
                    cited = receipt.get("exhaustion_evidence") or []
                    can_close = (attempt >= 2 and exhausted and isinstance(cited, list)
                                 and len({u for u in cited if isinstance(u, str)
                                          and u.startswith("https://")}) >= 2)
                    if can_close and "NIEPOTWIERDZONE" in message.split() and "POTWIERDZONE" not in message.split():
                        return {}
                    # DO POPRAWY never becomes final just because a fixed
                    # counter was reached. Demand real evidence or next round.
                    feedback = (receipt.get("reason") or "Brak pełnego dowodu")[:2200]
                    missing = ", ".join(receipt.get("blocked", [])[:10])
                    return {"decision":"block","reason":(
                        "TO CHATGPT MUSI WYKONAĆ KOREKTĘ, NIE GITHUB. "
                        "Nie kończ teraz odpowiedzi — zrób to w tej samej turze. "
                        "Odczytaj uwagi Google AI: " + feedback +
                        ". Niespełnione wymagania: " + missing +
                        ". Samodzielnie wyszukaj brakujące dane w wiarygodnych "
                        "źródłach, sprawdź je, popraw cały szkic zachowując "
                        "wszystkie wymagania i wyślij nowy [consult] o tytule " +
                        f"{title} /{attempt+1}, parent_issue={match}. "
                        "Odbierz nowy wynik Google AI, nie uznawaj niezweryfikowanych "
                        "produktów ani pozornych poprawek za sukces.")}
                status = receipt.get("status")
                if status == "POTWIERDZONE":
                    if receipt.get("review") != "SPRAWDZONE" or receipt.get("google_ai_responses_received",0) < 1:
                        return {"decision":"block","reason":"Brak rzeczywistego pozytywnego werdyktu Google AI."}
                    if status not in message.split() or "NIEPOTWIERDZONE" in message.split():
                        return {"decision":"block","reason":"Niezgodny status końcowy."}
                    if receipt.get("draft","").strip() not in message:
                        return {"decision":"block","reason":"Dołącz dokładny zatwierdzony szkic do odpowiedzi."}
                    return {}
                if (not correction_needed and status == "NIEPOTWIERDZONE"
                        and status in message.split() and "POTWIERDZONE" not in message.split()):
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
