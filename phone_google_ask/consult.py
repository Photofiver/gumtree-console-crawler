"""Review a complete evidence packet in a booted emulator, without truncating input."""
import hashlib
import ipaddress
import json
import os
import re
import secrets
import socket
import subprocess
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import parse_qs, urlsplit

from review import decide
from revision_guard import guarded_patch, tagged_json, safe_arithmetic_patch, validate_revision


def digest(value):
    return hashlib.sha256(value.encode()).hexdigest()


class VisibleText(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.ignore = 0
        self.parts = []

    def handle_starttag(self, tag, attrs):
        if tag in ("script", "style"):
            self.ignore += 1

    def handle_endtag(self, tag):
        if tag in ("script", "style"):
            self.ignore = max(0, self.ignore - 1)

    def handle_data(self, data):
        if not self.ignore:
            self.parts.append(data)


def source_text(url):
    u = urlsplit(url)
    if (u.scheme != "https" or u.port not in (None, 443) or u.username or u.password
            or not re.fullmatch(r"[a-zA-Z0-9.-]+", u.hostname or "")):
        raise ValueError("Unsupported source URL")
    ips = [a[4][0] for a in socket.getaddrinfo(u.hostname, 443, type=socket.SOCK_STREAM)]
    addresses = [ipaddress.ip_address(ip) for ip in ips]
    if not addresses or not all(ip.is_global and not ip.is_multicast for ip in addresses):
        raise ValueError("Expected public source")
    ip = ips[0] if ":" not in ips[0] else "[" + ips[0] + "]"
    # Pin the checked address, accept only a direct HTTP 200 HTML/text page.
    proc = subprocess.run(["curl", "-q", "--silent", "--show-error", "--fail",
        "--noproxy", "*", "--proto", "=https", "--max-time", "10", "--max-filesize",
        "4000000", "--resolve", f"{u.hostname}:443:{ip}", "-w", "\n%{http_code}", "--", url],
        capture_output=True, timeout=12, check=True)
    raw, code = proc.stdout.rsplit(b"\n", 1)
    if code != b"200":
        raise ValueError("Source did not return HTTP 200")
    page = VisibleText()
    page.feed(raw.decode("utf-8", errors="replace"))
    return " ".join(" ".join(page.parts).split())


def parts(text, limit):
    """Split on word boundaries when possible, keeping every UTF-8 character."""
    while len(text.encode()) > limit:
        block = text.encode()[:limit].decode(errors="ignore")
        cut = block.rfind(" ") + 1
        cut = cut if cut > len(block) // 2 else len(block)
        yield text[:cut]
        text = text[cut:]
    if text:
        yield text


def evaluate(data, ask, read=source_text):
    question, checks, draft = (data[k] for k in ("question", "checks", "draft"))
    if not question.strip() or not draft.strip() or not isinstance(checks, list) or not checks:
        raise ValueError("Missing question, draft or requirements")
    blocked, pages, excerpts = [], {}, []
    for check in checks:
        requirement = check["requirement"]
        if not requirement.strip():
            raise ValueError("Empty requirement")
        url, quote = check.get("source"), " ".join(check.get("quote", "").split())
        if url and url not in pages:
            try:
                pages[url] = read(url)
            except (OSError, ValueError, subprocess.SubprocessError):
                pages[url] = ""
        # Fetch and match the actual source BEFORE calling Google. A claimed
        # citation or check status alone is not evidence of an opened URL.
        matched = bool(url and len(quote) >= 8 and quote in pages.get(url, ""))
        if check["status"] != "met" or not check.get("finding") or not matched:
            blocked.append(requirement)
        if matched:
            index = pages[url].index(quote)
            excerpts.append(dict(requirement=requirement, url=url, quote=quote,
                                 observed=pages[url][max(0, index-65):index+len(quote)+65]))

    # The previous reviewer only saw user-supplied quotes, so it repeatedly
    # hallucinated "file not found" even though the engine had opened the file.
    # Send independently fetched excerpts in the FIRST Google request.
    claims = []
    for c in checks:
        url = c.get("source")
        quote = " ".join(c.get("quote", "").split())
        verified = bool(url and len(quote) >= 8 and quote in pages.get(url, ""))
        claim = dict(requirement=c["requirement"], status=c.get("status", "unknown"),
                     finding=c.get("finding", ""), source=url, quote=quote,
                     source_quote_verified=verified)
        if verified:
            index = pages[url].index(quote)
            claim["observed_from_source"] = pages[url][
                max(0, index-55):index+len(quote)+55]
        claims.append(claim)
    payload = json.dumps(dict(question=question, draft=draft, checks=claims),
                         ensure_ascii=False, separators=(",", ":"))
    tag = secrets.token_hex(8)
    prefix = (
        "Audit this complete factual draft and the supplied evidence. "
        "source_quote_verified=true means the exact quote was independently "
        "fetched from source URL and matched by our source reader, not merely "
        "asserted by the author. Do not invent 'file missing' when source evidence "
        "is present. REVISE for false claims or unsupported conclusions; "
        "PASS only if the entire supplied claim is supported. "
        "End with ONE separate line: REVISE " + tag + " OR PASS " + tag + ".\n"
    )
    chunks = list(parts(payload, 2000 - len(prefix.encode()) - 45))
    votes = []
    for i, chunk in enumerate(chunks, 1):
        query = prefix + f"Part {i}/{len(chunks)}\n" + chunk
        answer = "NIEPOTWIERDZONE"
        for attempt in range(2):
            if attempt == 0:
                probe = query
            else:
                retry_prefix = (
                    "Check this claim against the source_quote_verified fields "
                    "and observed_from_source evidence. Do not ignore verified "
                    "source excerpts. End with exactly ONE line: REVISE " + tag +
                    " OR PASS " + tag + ".\n"
                )
                probe = retry_prefix + f"Part {i}/{len(chunks)}\n" + chunk
            if len(probe.encode()) > 2000:
                continue
            try:
                answer = decide(dict(query=probe, tag=tag, draft=draft), ask(probe))
            except (OSError, ValueError, KeyError, RuntimeError, subprocess.SubprocessError):
                continue
            if answer != "NIEPOTWIERDZONE":
                break
        votes.append(answer.split("\n\n", 1)[0])
        if answer.startswith("DO POPRAWY"):
            return dict(review="DO POPRAWY", reason=answer.partition("\n\n")[2],
                        parts=len(chunks), reviewed=i, blocked=blocked)
        if not answer.startswith("SPRAWDZONE ·"):
            return dict(review="NIEPOTWIERDZONE",
                        reason="Google AI did not return an authenticated PASS/REVISE marker for part " +
                               str(i) + " after two distinct prompts",
                        parts=len(chunks), reviewed=i, blocked=blocked)

    # A one-part review already covers the complete draft, every check and the
    # fetched citations. Repeating an evidence-free final Google prompt caused
    # false NIEPOTWIERDZONE on correct, source-verified one-part reviews.
    solved = not blocked and len(chunks) == 1 and len(votes) == 1
    if not blocked and len(chunks) > 1:
        # Multiple independent PASS votes cannot establish consistency across
        # fragmented contexts: keep an explicit independent combined audit.
        tag = secrets.token_hex(8)
        final_prefix = (
            "Check ALL conditions against the SAME draft and the independently "
            "retrieved source excerpts. PASS only if every condition is proved. "
            "End with exactly PASS or REVISE followed by a space and " + tag +
            " on a separate line.\n"
        )
        summary = json.dumps(dict(question=question, draft=draft,
                                  observed=excerpts), ensure_ascii=False)
        coverage_parts = list(parts(summary, 2000-len(final_prefix.encode())-30))
        if len(coverage_parts) == 1:
            final_query = final_prefix + coverage_parts[0]
            try:
                coverage = decide(dict(query=final_query, tag=tag, draft=draft),
                                  ask(final_query))
            except (OSError, ValueError, KeyError, RuntimeError, subprocess.SubprocessError):
                coverage = "NIEPOTWIERDZONE"
            solved = coverage.startswith("SPRAWDZONE ·")
            if not solved:
                blocked.append("Kontrola wszystkich warunków: " + coverage)
        else:
            blocked.append("Dowody nie mieszczą się w jednej wspólnej recenzji")
    return dict(review="SPRAWDZONE",
                status="POTWIERDZONE" if solved else "NIEPOTWIERDZONE",
                parts=len(chunks), reviewed=len(votes), blocked=blocked)


def google_research(data, result, ask):
    """Request ONE bounded text patch; never concatenate separate AI drafts.

    AI suggestions are hypotheses, not source evidence. Only an exact substring
    of the user's original draft can be replaced; requirements and checks stay.
    """
    tag = secrets.token_hex(8)
    criticism = " ".join(result.get("reason", "").split())[:350]
    base = {
        "tag": tag,
        "question": data["question"][:260],
        "criticism": criticism,
        "instructions": "Keep the exact same equipment and user constraints.",
    }
    errors = []
    for attempt in range(2):
        prefix = (
            "Correct ONE factual error in the DRAFT below. "
            "Return ONLY one JSON object with fields tag, old, new, where tag is the "
            "same tag, old is an EXACT substring of DRAFT and new is a short replacement "
            "(under 480 characters). No new products, stations, prices or claims. "
            "Do not replace the entire draft. If evidence is missing, state that "
            "it remains unverified; never invent proof. "
        )
        if attempt:
            prefix = (
                "Your previous response could not be safely parsed or applied. "
                "Respond ONLY with a valid JSON object with fields tag, old, new; "
                "old must exactly match the draft and new must not invent claims. "
            )
        query = None
        for excerpt_length in (850, 650, 450, 250, 100):
            packet = dict(base, draft_excerpt=data["draft"][:excerpt_length])
            candidate = prefix + json.dumps(packet, ensure_ascii=False, separators=(",", ":"))
            if len(candidate.encode()) <= 2000:
                query = candidate
                break
        if query is None:
            raise ValueError("Could not fit a complete bounded patch request")
        page = ask(query)
        u = urlsplit(page.get("page", {}).get("url", ""))
        params = parse_qs(u.query)
        if (page.get("question") != query or u.scheme != "https" or
                u.hostname != "www.google.com" or u.path != "/search" or
                params.get("q") != [query] or params.get("udm") != ["50"]):
            raise ValueError("Research response did not match query")
        proposal = tagged_json(page["page"].get("text", ""), tag)
        if proposal is None:
            errors.append("No tagged structured JSON patch")
            continue
        try:
            patched = guarded_patch(data, proposal["old"], proposal["new"])
        except ValueError as exc:
            errors.append(str(exc))
            continue
        # Never accept AI's proposed evidence as verified. Original checks stay.
        return dict(data, draft=patched, checks=[dict(c) for c in data["checks"]])
    raise ValueError("No safe patch accepted: " + "; ".join(errors)[:240])


def evidence_revision(data, result, read):
    """Repair only a known deterministic arithmetic error; do not quote raw AI prose."""
    return safe_arithmetic_patch(data)


def solve(data, ask, read=source_text, research=google_research):
    """Every attempted correction MUST receive a fresh, independent Google AI review.

    Corrections are never silently accepted when the reviewer is unreachable or
    returns an unverifiable response. Attempted calls and completed verdicts are
    reported separately, including the original draft and every revised draft.
    """
    history, seen = [], set()
    audit = []
    edits_rechecked = 0
    def audited_ask(query):
        record = dict(query_sha256=digest(query), state="sent")
        audit.append(record)
        try:
            answer = ask(query)
        except Exception as exc:
            record["state"] = "transport_error"
            record["error"] = type(exc).__name__
            raise
        if not isinstance(answer, dict):
            record["state"] = "invalid_response"
            return answer
        page = answer.get("page", {})
        u = urlsplit(page.get("url", ""))
        params = parse_qs(u.query)
        if (answer.get("question") == query and u.scheme == "https"
                and u.hostname == "www.google.com" and u.path == "/search"
                and params.get("q") == [query] and params.get("udm") == ["50"]
                and bool(page.get("text", "").strip())):
            record["state"] = "response_received"
        else:
            record["state"] = "invalid_response"
        return answer

    waiting_for_recheck = False
    last_reviewed = data["draft"]
    result = dict(review="NIEPOTWIERDZONE", status="NIEPOTWIERDZONE",
                  reason="Google AI review was not performed")
    for attempt in range(1, 4):
        key = " ".join(data["draft"].split()).casefold()
        if key in seen:
            result["obstacle"] = "Repeated draft cannot skip independent review"
            break
        seen.add(key)
        result = evaluate(data, audited_ask, read)
        step = dict(round=attempt, draft=data["draft"], **result)
        history.append(step)
        if waiting_for_recheck:
            edits_rechecked += 1
            step["correction_rechecked_by_google"] = result["review"] != "NIEPOTWIERDZONE"
            if result["review"] == "NIEPOTWIERDZONE":
                step["correction_status"] = "BLOCKED_NO_GOOGLE_VERDICT"
                result["obstacle"] = "Corrected draft not independently reviewed by Google AI"
                # Never output a correction as accepted when no model verdict was read.
                data = dict(data, draft=last_reviewed)
                break
        last_reviewed = data["draft"]
        # A Google PASS ends text corrections even when evidence is incomplete.
        # Missing/failed checks cannot be fixed by rewriting a passed answer:
        # they require independent new evidence, not another speculative patch.
        if (result["review"] in ("SPRAWDZONE", "NIEPOTWIERDZONE")
                or result.get("status") == "POTWIERDZONE"
                or attempt == 3):
            break
        try:
            revised = validate_revision(data, research(data, result, audited_ask))
        except (ValueError, KeyError, TypeError, OSError, subprocess.SubprocessError, RuntimeError) as exc:
            step["research_error"] = str(exc)[:400]
            revised = evidence_revision(data, result, read)
            if revised is None:
                step["correction_status"] = "BLOCKED_UNVERIFIED"
                result["obstacle"] = "No safe, evidenced revision: " + str(exc)[:300]
                break
            revised = validate_revision(data, revised)
        if " ".join(revised["draft"].split()).casefold() in seen:
            result["obstacle"] = "Research repeated a previously reviewed draft"
            break
        # Next loop MUST call Google AI for the amended draft, or it is discarded.
        data = revised
        waiting_for_recheck = True

    return dict(result, status=result.get("status", "NIEPOTWIERDZONE"),
                history=history, checks=data["checks"], draft=data["draft"],
                google_ai_queries_sent=len(audit),
                google_ai_responses_received=sum(x["state"] == "response_received" for x in audit),
                google_ai_edits_rechecked=edits_rechecked,
                google_ai_audit=audit)


def main():
    from warm_worker import ask_emulator
    issue = json.loads(Path(os.environ["GITHUB_EVENT_PATH"]).read_text())["issue"]
    body = issue["body"]
    try:
        result = solve(json.loads(body), ask_emulator)
    except Exception as exc:
        result = dict(review="NIEPOTWIERDZONE", reason=type(exc).__name__ + ": " + str(exc)[:500])
    result.setdefault("status", "NIEPOTWIERDZONE")
    # Computed hypotheses are intentionally separate from verified research.
    report = Path("exploration-report.json")
    if report.exists():
        try:
            result["exploration"] = json.loads(report.read_text())["summary"]
        except (KeyError, ValueError, OSError):
            result["exploration_error"] = "Failed to load screening summary"
    problem = Path("exploration-error.txt")
    if problem.exists():
        result["exploration_error"] = problem.read_text()[:350]
    result.update(issue=issue["number"], sha256=digest(body))
    Path("consult-result.json").write_text(json.dumps(result, ensure_ascii=False))


if __name__ == "__main__":
    main()
