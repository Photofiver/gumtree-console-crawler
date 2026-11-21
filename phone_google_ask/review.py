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


SOLAR_ROUTE_KEYS = {
    "direct_panel",         # one compatible panel and cold Voc check
    "parallel_panels",      # multiple panels and current protection
    "series_panels",        # voltage and converter requirements
    "regulated_converter",  # more PV through a proven DC-DC output limit
    "other_input",          # only ports and simultaneous charging supported by manual
    "buffer_or_hybrid",     # battery buffer or other allowed input, net energy check
    "market_comparison",    # competing actual Amazon UK / Argos offerings
}


def solar_search(data):
    text = ((data.get("question") or "") + " " + (data.get("requirements") or "")).lower()
    return "s700" in text and any(word in text for word in
                                    ("solar", "panel", "pv", "fotowolt"))


def valid_source(source):
    if not isinstance(source, str) or not source.strip():
        return False
    url = urlparse(source.strip())
    return url.scheme == "https" and bool(url.netloc and "." in url.netloc)


def research_audit_error(data):
    """Check logged coverage before accepting a negative product-search draft.

    A filled audit is evidence of a declared search, NOT independent proof that
    listed URLs exist, were opened, are up to date, or establish nonexistence.
    """
    if not negative_product_discovery(data):
        return None
    log = data.get("search_log")
    if not isinstance(log, list) or len(log) < 3:
        return ("Brak udokumentowanych co najmniej 3 drog. Dodaj search_log "
                "z polami route, finding, source po faktycznym sprawdzeniu.")
    routes = set()
    for item in log:
        if not isinstance(item, dict):
            return "Kazdy wpis search_log musi byc obiektem."
        route, finding, source = (item.get(x) for x in ("route", "finding", "source"))
        if not isinstance(route, str) or not route.strip():
            return "Kazdy wpis search_log musi podawac route."
        if not isinstance(finding, str) or len(finding.strip()) < 15:
            return "Kazdy wpis search_log musi opisywac konkretny wynik i ograniczenie."
        if not valid_source(source):
            return "Kazdy wpis search_log wymaga konkretnego linku HTTPS."
        routes.add(route.strip().lower())
    if len(routes) < 3:
        return "Wymagane co najmniej 3 rozne drogi techniczne."

    if solar_search(data):
        missing = SOLAR_ROUTE_KEYS - routes
        if missing:
            return ("Nie sprawdzono wszystkich klas rozwiazan S700; brakuje: "
                    + ", ".join(sorted(missing))
                    + ". Kazda droga wymaga wyniku i zrodla. Nie udawaj weryfikacji.")
        candidates = data.get("candidate_log")
        if not isinstance(candidates, list) or len(candidates) < 5:
            return ("Przed negatywnym werdyktem zweryfikuj co najmniej 5 "
                    "odrebnych modeli/ofert i dodaj candidate_log: "
                    "[{model,source,limitation},...].")
        models = set()
        for item in candidates:
            if not isinstance(item, dict):
                return "Niepoprawny candidate_log."
            model, source, limitation = (item.get(k) for k in
                                         ("model", "source", "limitation"))
            if not isinstance(model, str) or len(model.strip()) < 4:
                return "Brak konkretnego modelu w candidate_log."
            if not valid_source(source):
                return "Brak linku HTTPS do rzeczywistego modelu/oferty."
            if not isinstance(limitation, str) or len(limitation.strip()) < 12:
                return "Brak konkretnej przyczyny odrzucenia modelu."
            models.add(model.lower().strip())
        if len(models) < 5:
            return "Potrzeba 5 odrebnych modeli, nie pieciu wpisow o jednym."
        proof = data.get("feasibility")
        if not isinstance(proof, dict) or not all(
            isinstance(proof.get(k), str) and len(proof[k].strip()) >= 15
            for k in ("energy_balance", "port_limits", "weather_uncertainty",
                      "closest_option", "unmet_requirement")
        ):
            return ("Brak feasibility: energy_balance, port_limits, "
                    "weather_uncertainty, closest_option, unmet_requirement. "
                    "Rozroznij sredni uzysk od gwarancji dla kazdej pogody.")
        # A research audit does not establish market exhaustiveness. Claiming
        # universal non-existence needs a formal proof, not just missing listings.
        if any(phrase in (data.get("draft") or "").lower() for phrase in
               ("nie istnieje zaden", "nie istnieje żaden", "wszystkie mozliwosci",
                "wszystkie możliwości", "there are no possible")):
            return ("Nie twierdz, ze sprawdzono caly rynek lub udowodniono "
                    "nieistnienie produktu samym przegladem ofert.")
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
    # Keep extensive audit in the GitHub issue: the Google query is limited
    # to 2000 UTF-8 bytes. Passing all URLs would make substantial work fail
    # transport before the independent review can even start.
    payload = json.dumps(
        {k: data[k] for k in ("question", "requirements", "draft")},
        ensure_ascii=False, separators=(",", ":")
    )
    query = (
        "Review this JSON question, requirements and draft for correctness, "
        "independently checking unsupported claims. This review's status, duration "
        "and GitHub URL are post-review metadata, NOT draft omissions. "
        "If draft says no solution, actively seek counterexamples and question "
        "whether evidence proves infeasibility vs only unsuccessful search. "
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
