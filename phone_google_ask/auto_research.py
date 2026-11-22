"""Resumable, no-paid-API research using the existing warm Google AI browser.

Only source leads verified from a real HTTPS page are recorded. A source
quotation does NOT prove that a complete electrical/purchase setup works.
This agent cannot restart a ChatGPT turn; it works independently in Actions.
"""
import hashlib
import json
from datetime import datetime, timezone, timedelta
from consult import google_source_research, source_text

PREFIX = "AutoResearch/1 "
ARCHIVE_PREFIX = "AutoResearchArchive/1 "
ROUTES = (
    "primary manufacturer technical specifications",
    "actual Amazon UK offer, exact model and price",
    "actual Argos UK offer, exact model and price",
    "compatible DC-DC MPPT and regulated output",
    "cold-weather Voc and current limits",
    "outdoor waterproof rigid mounting and cabling",
    "low-irradiance winter generation and losses",
    "alternative safe architecture without changing requirements",
    "independent user experience and technical discussion",
    "complete bill of materials and safety accessories",
)


def checksum(issue):
    return hashlib.sha256((issue.get("body") or "").encode("utf-8")).hexdigest()


def initial_state(issue):
    data = json.loads(issue.get("body") or "{}")
    if not isinstance(data, dict) or not isinstance(data.get("checks"), list):
        raise ValueError("Auto-research issue needs JSON with checks")
    if not data["checks"] or not isinstance(data.get("question"), str) or not data["question"].strip():
        raise ValueError("Missing original question or checks")
    if not isinstance(data.get("draft"), str) or not data["draft"].strip():
        raise ValueError("Missing initial draft")
    for check in data["checks"]:
        if not isinstance(check, dict) or not isinstance(check.get("requirement"), str):
            raise ValueError("Each check needs a requirement")
    return dict(version=1, issue=issue["number"], sha256=checksum(issue),
                question=data["question"], draft=data["draft"],
                checks=data["checks"], rounds=0, sources=[], status="RESEARCHING",
                last_note="New autonomous research task", next_after="")


def load(issue, comments):
    target = checksum(issue)
    for comment in reversed(comments):
        if (comment.get("user", {}).get("login") != "github-actions[bot]" or
                not (comment.get("body") or "").startswith(PREFIX)):
            continue
        try:
            state = json.loads(comment["body"][len(PREFIX):])
        except (ValueError, TypeError):
            continue
        if (state.get("sha256") == target and state.get("issue") == issue["number"] and
                state.get("version") == 1):
            return state, comment["id"]
    return initial_state(issue), None


def ready(state, now):
    if state.get("status") == "POTWIERDZONE":
        return False
    gate = state.get("next_after")
    if gate:
        try:
            if now < datetime.fromisoformat(gate):
                return False
        except (ValueError, TypeError):
            pass
    return True


def propose_candidate(state, ask):
    """Request a *labeled unverified proposal*, never certify it as a solution."""
    references = state.get("sources", [])[-5:]
    if not references:
        return None
    facts = [{"url": x["url"], "quote": x["quote"][:135]}
             for x in references]
    question = state["question"][:310]
    query = (
        "Using ONLY the independently retrieved web excerpts below, suggest "
        "one SPECIFIC equipment configuration or say it cannot be proven. "
        "Preserve every original requirement. Never invent a price, voltage, "
        "accessory or source. Output ONLY JSON with draft (<=650 chars), "
        "urls (list of exact source URLs), missing (list of unproven constraints). "
        "A draft is a LEAD, not an approved purchase. "
        + json.dumps({"task": question, "sources": facts},
                     ensure_ascii=False, separators=(",", ":"))
    )
    if len(query.encode("utf-8")) > 2000:
        return None
    try:
        response = ask(query)
        if response.get("question") != query or not response.get("aiResponseReady"):
            return None
        page = response.get("page") or {}
        from urllib.parse import urlsplit, parse_qs
        url = urlsplit(page.get("url") or "")
        if (url.scheme != "https" or url.hostname != "www.google.com" or
                url.path != "/search" or parse_qs(url.query).get("q") != [query] or
                parse_qs(url.query).get("udm") != ["50"]):
            return None
        text = page.get("text") or ""
        decoder = json.JSONDecoder(strict=False)
        permitted = {x["url"] for x in state["sources"]}
        for pos, ch in enumerate(text):
            if ch != "{":
                continue
            try:
                proposal, _ = decoder.raw_decode(text[pos:])
            except (ValueError, TypeError):
                continue
            if not isinstance(proposal, dict):
                continue
            draft = proposal.get("draft")
            urls = proposal.get("urls")
            missing = proposal.get("missing", [])
            if (not isinstance(draft, str) or not draft.strip() or
                    len(draft) > 650 or not isinstance(urls, list) or
                    not urls or not all(u in permitted for u in urls) or
                    not isinstance(missing, list)):
                continue
            return {"draft": draft.strip(), "source_urls": urls,
                    "missing": [str(v)[:180] for v in missing[:15]],
                    "status": "UNVERIFIED_CANDIDATE"}
    except (OSError, ValueError, RuntimeError, TypeError):
        return None
    return None


def next_step(issue, state, ask, read=source_text, now=None):
    """Advance one independent lead search, not an unsupported PASS."""
    now = now or datetime.now(timezone.utc)
    if not ready(state, now):
        return state, False
    state = dict(state)
    state["checks"] = [dict(c) for c in state["checks"]]
    state["sources"] = list(state.get("sources", []))
    round_index = int(state.get("rounds", 0))
    idx = round_index % len(state["checks"])
    route = ROUTES[(round_index // len(state["checks"])) % len(ROUTES)]
    original = state["checks"][idx]["requirement"]

    # Re-search known requirements on different routes; don't pretend that
    # one quotation establishes compliance or stop after a failed query.
    probe_check = dict(requirement=original + "; research route: " + route,
                       status="unknown")
    probe = dict(question=state["question"], draft=state["draft"],
                 checks=[probe_check])
    delay = 45
    try:
        result = google_source_research(probe, dict(reason=probe_check["requirement"]),
                                        ask, read=read)
        if result and result.get("research_trace"):
            item = result["research_trace"][-1]
            url, quote = item["url"], item["verified_quote"]
            existing = {(x["requirement_index"], x["url"], x["quote"])
                        for x in state["sources"]}
            key = (idx, url, quote)
            if key not in existing:
                state["sources"].append(dict(requirement_index=idx,
                                             requirement=original, route=route,
                                             url=url, quote=quote,
                                             found_at=now.isoformat()))
                # Record the independently observed quotation, NOT "met".
                state["checks"][idx].update(source=url, quote=quote,
                                             status="unknown",
                                             finding="Source quotation verified; complete requirement not yet proven")
                state["last_note"] = "Verified a new source excerpt for requirement " + str(idx+1)
            else:
                state["last_note"] = "Already known source; switching research route"
        else:
            state["last_note"] = "No independently verifiable lead; continue with another route"
    except Exception as exc:
        state["last_note"] = "Research transport/source error: " + type(exc).__name__
        delay = 180
    state["rounds"] = round_index + 1
    state["last_route"] = route
    # Search distinct components first; after each complete cycle, ask Google
    # for a new concrete candidate grounded exclusively in saved source URLs.
    # Candidate suggestions never change check statuses to "met".
    if (state["rounds"] % len(state["checks"]) == 0 and state["sources"]):
        proposal = propose_candidate(state, ask)
        if proposal:
            proposal["proposed_at"] = now.isoformat()
            state["candidate"] = proposal
    state["next_after"] = (now + timedelta(seconds=delay)).isoformat()
    # A real PASS requires per-component engineering validation AND a separate
    # Google AI review. Lead collection alone deliberately never claims it.
    state["status"] = "RESEARCHING"
    # Never discard verified sources merely because the current run ended.
    # run_once archives older chunks before shrinking the live progress comment.
    return state, True


def run_once(issue, ask, api, read=source_text, now=None):
    """Persist after EACH step, so runner timeouts cannot erase progress."""
    comments = api("GET", "/issues/" + str(issue["number"]) + "/comments?per_page=100")
    state, comment_id = load(issue, comments)
    updated, changed = next_step(issue, state, ask, read, now)
    if not changed:
        return False
    body = PREFIX + json.dumps(updated, ensure_ascii=False, separators=(",", ":"))
    if len(body.encode("utf-8")) > 54000:
        # Archive FIRST with append-only bot comments; only then compact the
        # mutable progress comment. Retry is idempotent using archive digests.
        older = updated["sources"][:-30]
        count = int(updated.get("archived_sources", 0))
        for start in range(0, len(older), 30):
            batch = older[start:start+30]
            stamp = hashlib.sha256(json.dumps(batch, ensure_ascii=False,
                      sort_keys=True).encode("utf-8")).hexdigest()
            if not any((c.get("body") or "").startswith(ARCHIVE_PREFIX + stamp + " ")
                       for c in comments):
                archive = ARCHIVE_PREFIX + stamp + " " + json.dumps(
                    {"issue": issue["number"], "sha256": checksum(issue),
                     "offset": count, "sources": batch},
                    ensure_ascii=False, separators=(",", ":"))
                api("POST", "/issues/" + str(issue["number"]) + "/comments",
                    {"body": archive})
            count += len(batch)
        updated["archived_sources"] = count
        updated["sources"] = updated["sources"][-30:]
        body = PREFIX + json.dumps(updated, ensure_ascii=False, separators=(",", ":"))
    if comment_id is not None:
        api("PATCH", "/issues/comments/" + str(comment_id), {"body": body})
    else:
        api("POST", "/issues/" + str(issue["number"]) + "/comments", {"body": body})
    return True
