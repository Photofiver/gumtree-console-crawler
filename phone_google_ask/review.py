"""Strict Google AI review mode for google-ai-ask.yml (Python standard library)."""
import base64
import hashlib
import json
import os
from pathlib import Path
import secrets
import sys
from urllib.parse import parse_qs, urlparse



def negative_product_discovery(data):
    """True if a product-finding task is being closed with no confirmed solution."""
    q = (data.get("question") or "").lower()
    draft = (data.get("draft") or "").lower()
    discovery = ("znajd", "szukaj", "czy istnieje", "zestaw", "kupic",
                 "kupić", "find ", "buy ", "shopping", "purchase")
    negative = ("nie znaleziono", "nie znalaz", "nie ma zestawu",
                "nie udało się znaleźć", "brak potwierdzonego zestawu",
                "nie mozna potwierdzic kompletnego", "nie można potwierdzić kompletnego",
                "no verified kit", "no suitable kit", "cannot find")
    return any(term in q for term in discovery) and any(term in draft for term in negative)


def research_audit_error(data):
    """Require documented, distinct discovery routes before accepting 'none found'.

    This is an evidence-of-work gate, not proof that a product is impossible.
    """
    if not negative_product_discovery(data):
        return None
    log = data.get("search_log")
    if not isinstance(log, list) or len(log) < 3:
        return ("Przed negatywnym werdyktem sprawdz minimum 3 rozne drogi "
                "rozwiazania i dodaj search_log: [{route, finding, source}, ...].")
    routes = set()
    for item in log:
        if not isinstance(item, dict):
            return "Kazdy wpis search_log musi byc obiektem route/finding/source."
        route, finding, source = (item.get(x) for x in ("route", "finding", "source"))
        if not all(isinstance(x, str) and x.strip() for x in (route, finding, source)):
            return "W kazdym wpisie search_log podaj niepuste route, finding i source."
        url = urlparse(source)
        if url.scheme != "https" or not url.netloc or "." not in url.netloc:
            return "Kazdy wpis search_log musi zawierac rzeczywisty link HTTPS do zrodla."
        routes.add(route.strip().lower())
    if len(routes) < 3:
        return "Search_log musi obejmowac minimum 3 rozne drogi techniczne."
    return None


def prepare(event):
    data = json.loads(event["issue"]["body"])
    for key in ("question", "requirements", "draft"):
        if not isinstance(data.get(key), str) or not data[key].strip():
            raise ValueError("Missing " + key)
    audit_problem = research_audit_error(data)
    if audit_problem:
        Path("review-research-error.txt").write_text(audit_problem, encoding="utf-8")
        raise ValueError("Research audit incomplete: " + audit_problem)
    tag = secrets.token_hex(8)
    payload = json.dumps(
        {**{k: data[k] for k in ("question", "requirements", "draft")},
         **({"search_log": data["search_log"]} if negative_product_discovery(data) else {})},
        ensure_ascii=False, separators=(",", ":")
    )
    query = (
        "Review this JSON question, requirements and draft for correctness, "
        "independently checking unsupported claims. This review's status, duration "
        "and GitHub URL are post-review metadata, NOT draft omissions. "
        "If draft says no solution, challenge it using alternate technical routes "
        "and require specific sourced checks; do not PASS mere lack of a finding. "
        "Give a concise reason; end with exactly PASS or REVISE, a space, and token "
        + tag + " on its own line.\\n" + payload
    )
    if len(query.encode("utf-8")) > 2000:
        Path("review-transport-error.txt").write_text(
            "Zapytanie ma " + str(len(query.encode("utf-8")))
            + " bajtow, limit wynosi 2000; recenzja nie zostala uruchomiona."
        )
        raise ValueError("Review exceeds the transport limit of 2000 bytes")
    Path("review-request.json").write_text(json.dumps(dict(query=query, tag=tag, draft=data["draft"])))
    with open(os.environ["GITHUB_ENV"], "a") as env:
        print("QUESTION_B64=" + base64.b64encode(query.encode()).decode(), file=env)


def decide(req, result):
    page = result["page"]
    url = urlparse(page["url"])
    params = parse_qs(url.query)
    if (url.scheme != "https" or url.hostname != "www.google.com" or url.path != "/search"
            or params.get("q") != [req["query"]] or params.get("udm") != ["50"]
            or result.get("question") != req["query"]):
        return "NIEPOTWIERDZONE"
    lines = [line.strip() for line in page["text"].splitlines()]
    votes = [line for line in lines if line in ("PASS " + req["tag"], "REVISE " + req["tag"])]
    if votes == ["PASS " + req["tag"]]:
        digest = hashlib.sha256(req["draft"].encode()).hexdigest()
        return "SPRAWDZONE · SHA-256 " + digest + "\n\n" + req["draft"]
    if votes == ["REVISE " + req["tag"]]:
        i = lines.index(votes[0])
        # Ignore the echoed search prompt and Google navigation above the answer.
        echoed = [part.strip() for part in req["query"].splitlines() if part.strip()]
        boundary = max((j for j, line in enumerate(lines[:i])
                        if any(part in line for part in echoed)), default=-1)
        reason = "\n".join(lines[boundary + 1:i]).strip()
        return "DO POPRAWY\n\n" + (reason[-1500:] or "Brak odczytanego uzasadnienia.")
    return "NIEPOTWIERDZONE"


if __name__ == "__main__":
    if sys.argv[1] == "prepare":
        prepare(json.loads(Path(os.environ["GITHUB_EVENT_PATH"]).read_text()))
    else:
        try:
            print(decide(json.loads(Path("review-request.json").read_text()),
                         json.loads(Path("google-ai-ask-result.json").read_text())))
        except (OSError, ValueError, KeyError, TypeError, AttributeError):
            print("NIEPOTWIERDZONE")
