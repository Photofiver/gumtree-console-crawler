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
from attention_guard import focus_hint
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
        if (check["status"] != "met" or not check.get("finding") or len(quote) < 8
                or quote not in pages.get(url, "")):
            blocked.append(requirement)
        else:
            index = pages[url].index(quote)
            excerpts.append(dict(requirement=requirement, url=url,
                                 observed=pages[url][max(0,index-80):index+len(quote)+80]))
    context = "Question: " + question + "\nRequirements: " + " | ".join(c["requirement"] for c in checks)
    # Full search_log/candidate_log/feasibility remain in the GitHub issue and
    # exploration artifact. Feeding that entire packet to Google split an ordinary
    # S700 draft into 7 arbitrary JSON fragments, losing all useful context.
    claims = [dict(requirement=c["requirement"], status=c.get("status", "unknown"),
                   finding=c.get("finding", ""), quote=c.get("quote", ""))
              for c in checks]
    payload = json.dumps(dict(question=question, draft=draft, checks=claims),
                         ensure_ascii=False, separators=(",", ":"))
    tag = secrets.token_hex(8)
    prefix = ("Audit this complete draft against the stated requirements. "
              "For numbered multi-part input, judge ONLY claims in this fragment: "
              "other parts are reviewed separately; do NOT reject because other "
              "parts or a closing sentence are absent. "
              "REVISE false or unsupported claims actually present; give reasons. "
              "End with ONE exact separate line: REVISE " + tag +
              " OR PASS " + tag + ".\n")
    # Repeat context if it fits. Otherwise the entire original remains in the fragments.
    if len(context.encode()) <= 800:
        prefix += context + "\n"
    # Actual pretrained attention can add a short ranking reminder. It never
    # removes, relaxes, or asserts completion of any original requirement.
    prefix += focus_hint(data)
    chunks = list(parts(payload, 2000 - len(prefix.encode()) - 40))
    votes, failures, unreadable = [], [], []
    for i, chunk in enumerate(chunks, 1):
        query = prefix + f"Part {i}/{len(chunks)}\n" + chunk
        answer = "NIEPOTWIERDZONE"
        # A second, independently phrased prompt helps when Google's HTML answer
        # omitted the exact decision line. Do not fabricate a verdict.
        for attempt in range(2):
            if attempt == 0:
                probe = query
            else:
                retry_prefix = ("Check this claim for factual errors and missing proof. "
                                "This is ONE part of a packet; judge present claims "
                                "only, not absent later parts or truncated formatting. "
                                "End with exactly ONE line: REVISE " + tag +
                                " OR PASS " + tag + ".\n")
                probe = retry_prefix + f"Part {i}/{len(chunks)}\n" + chunk
            if len(probe.encode()) > 2000:
                # Never silently truncate evidence to obtain a convenient PASS.
                continue
            req = dict(query=probe, tag=tag, draft=draft)
            try:
                answer = decide(req, ask(probe))
            except (OSError, ValueError, KeyError, RuntimeError, subprocess.SubprocessError):
                continue
            if answer != "NIEPOTWIERDZONE":
                break
        votes.append(answer.split("\n\n", 1)[0])
        if answer.startswith("DO POPRAWY"):
            failures.append({"part":i, "reason":answer.partition("\n\n")[2][:600]})
        elif not answer.startswith("SPRAWDZONE ·"):
            unreadable.append(i)
    # Never stop after the first REVISE. Each numbered fragment is independently
    # audited, and the report must accurately count all reviewed parts.
    if failures:
        reason = "\n".join("Part "+str(f["part"])+"/"+str(len(chunks))+
                           ": "+(f["reason"] or "Google AI requested revision")
                           for f in failures)
        if unreadable:
            reason += "\nNo authenticated verdict for parts: "+", ".join(map(str,unreadable))
        return dict(review="DO POPRAWY", reason=reason, parts=len(chunks),
                    reviewed=len(votes), blocked=blocked,
                    failed_parts=[f["part"] for f in failures], unreadable_parts=unreadable)
    if unreadable:
        return dict(review="NIEPOTWIERDZONE",
                    reason="Google AI did not return an authenticated PASS/REVISE marker for parts: "+
                           ", ".join(map(str,unreadable))+" after two distinct prompts",
                    parts=len(chunks), reviewed=len(votes), blocked=blocked,
                    unreadable_parts=unreadable)
    # Fragment approvals cannot establish consistency across separate model contexts.
    solved = False
    if not blocked and len(votes) == len(chunks):
        tag = secrets.token_hex(8)
        final_prefix = ("Check ALL conditions of the original question against the same proposed solution "
                       "and the observed page excerpts below. Look for missing conditions, wrong variants, "
                       "unsupported claims and mixing different products. PASS only when each condition is "
                       "demonstrated. End with exactly PASS or REVISE followed by a space and " + tag +
                       " on a separate line.\n")
        summary = json.dumps(dict(question=question, draft=draft, observed=excerpts), ensure_ascii=False)
        coverage_parts = list(parts(summary, 2000-len(final_prefix.encode())))
        for section in coverage_parts:
            final_query = final_prefix + section
            try:
                coverage = decide(dict(query=final_query,tag=tag,draft=draft), ask(final_query))
            except (OSError, ValueError, KeyError, RuntimeError, subprocess.SubprocessError):
                coverage = "NIEPOTWIERDZONE"
            solved = coverage.startswith("SPRAWDZONE ·")
            if not solved:
                blocked.append("Kontrola wszystkich warunków: " + coverage)
                break
        if len(coverage_parts) > 1:
            solved = False
            blocked.append("Dowody oceniono częściami; brak jednej wspólnej oceny całego zestawu")
    return dict(review="SPRAWDZONE", status="POTWIERDZONE" if solved else "NIEPOTWIERDZONE",
                parts=len(chunks), reviewed=len(votes), blocked=blocked)


def patch_target(draft, criticism):
    """Choose a short, exact span from the actual draft for a local correction.

    Google does not have to guess an exact 'old' substring from an arbitrary
    truncated JSON prefix. An absence of strong matching words is not proof
    of a factual error: the selection is only an edit target.
    """
    lines = [part.strip() for part in re.split(r"(?<=[.!?])\s+|\n+", draft)
             if 8 <= len(part.strip()) <= 380]
    if not lines:
        lines = [draft[:min(len(draft), 300)].strip()]
    words = set(re.findall(r"\w{5,}", criticism.casefold()))
    def score(line):
        tokens = set(re.findall(r"\w{5,}", line.casefold()))
        return (len(words & tokens), -len(line))
    target = max(lines, key=score)
    if len(target) > 380:
        target = target[:380].rsplit(" ", 1)[0]
    return target


def parse_patch_response(page_text, tag, predetermined_old):
    """Accept a tagged JSON patch, including a 'new'-only anchored protocol."""
    proposal = tagged_json(page_text, tag)
    if proposal is not None:
        return proposal
    decoder = json.JSONDecoder(strict=False)
    for m in re.finditer(r"\{", page_text):
        try:
            obj, _ = decoder.raw_decode(page_text[m.start():])
        except (ValueError, TypeError):
            continue
        if not isinstance(obj, dict) or obj.get("tag") != tag:
            continue
        new = obj.get("new")
        if not isinstance(new, str):
            continue
        if "old" in obj and obj["old"] != predetermined_old:
            continue
        return {"old":predetermined_old, "new":new}
    return None


def google_source_research(data, result, ask, read=source_text):
    """Ask for a new primary source and verify its verbatim excerpt ourselves.

    This is a genuine bounded research step, NOT certification of the whole
    requirement or a substitute for opening a real product listing.
    """
    unfinished = [(i, c) for i, c in enumerate(data["checks"])
                  if c.get("status") != "met" and not
                  (c.get("source") and c.get("quote"))]
    if not unfinished:
        return None
    reason = result.get("reason", "")
    keywords = set(re.findall(r"\w{5,}", reason.casefold()))
    def relevance(item):
        tokens = set(re.findall(r"\w{5,}", item[1]["requirement"].casefold()))
        return len(tokens & keywords)
    index, check = max(unfinished, key=relevance)
    tag = secrets.token_hex(8)
    query = ("Find ONE actual public manufacturer's data sheet or official "
             "retailer source related to the SPECIFIC requirement below. "
             "Return ONLY JSON with tag, url (direct HTTPS page), quote "
             "(a verbatim substring of that page, 16-200 chars). "
             "Do not invent sources, datasheet values, prices or quotes. "
             + json.dumps({"tag":tag, "equipment":data["question"][:170],
                           "requirement":check["requirement"][:230]},
                          ensure_ascii=False, separators=(",", ":")))
    if len(query.encode()) > 2000:
        return None
    page = ask(query)
    url = urlsplit(page.get("page", {}).get("url", ""))
    params = parse_qs(url.query)
    if (page.get("question") != query or url.scheme != "https" or
            url.hostname != "www.google.com" or url.path != "/search" or
            params.get("q") != [query] or params.get("udm") != ["50"]):
        return None
    output = page["page"].get("text", "")
    decoder = json.JSONDecoder(strict=False)
    for m in re.finditer(r"\{", output):
        try:
            obj, _ = decoder.raw_decode(output[m.start():])
        except (TypeError, ValueError):
            continue
        if not isinstance(obj, dict) or obj.get("tag") != tag:
            continue
        url = obj.get("url")
        quote = obj.get("quote")
        if (not isinstance(url, str) or not url.startswith("https://")
                or len(url) > 500 or not isinstance(quote, str)
                or not 16 <= len(quote) <= 200):
            continue
        quote = " ".join(quote.split())
        if len(quote) < 16:
            continue
        try:
            page_text = read(url)
        except (ValueError, OSError, subprocess.SubprocessError):
            continue
        if quote not in " ".join(page_text.split()):
            continue
        # Evidence from a real page is useful, but a quote alone cannot
        # prove a whole solar configuration safe or automatically make a
        # check 'met'. Preserve the exact user requirement and its status.
        updated = dict(data)
        checks = [dict(c) for c in data["checks"]]
        checks[index]["source"] = url
        checks[index]["quote"] = quote
        checks[index]["finding"] = "Exact source quotation retrieved; full requirement still unverified"
        updated["checks"] = checks
        updated["draft"] = data["draft"] + (
            "\nDodatkowe źródło dla nierozstrzygniętego wymogu: " + url +
            ". Samo źródło nie potwierdza jeszcze kompletnego zestawu.")
        updated["research_trace"] = list(data.get("research_trace", [])) + [
            dict(requirement=check["requirement"], url=url,
                 verified_quote=quote, requirement_status="unknown")]
        return updated
    return None


def google_research(data, result, ask, read=source_text):
    """Request a short anchored correction and require source-safe validation.

    The reviewer is NOT a source of prices or electrical proof. If no safe edit
    exists, fail closed; a DO POPRAWY verdict never becomes a manufactured PASS.
    """
    tag = secrets.token_hex(8)
    reason = " ".join(result.get("reason", "").split())[:450]
    old = patch_target(data["draft"], reason)
    if len(old) < 5 or data["draft"].count(old) != 1:
        raise ValueError("No unique local edit target in draft")
    base = {"tag":tag, "old":old, "reason":reason[:220],
            "question":data["question"][:180]}
    errors = []
    for attempt in range(2):
        if attempt == 0:
            prefix = (
                "Check the review criticism and correct ONLY the exact OLD text. "
                "Return ONE JSON object with tag, old, new; copy old verbatim, "
                "new <= 280 characters. Keep all original constraints. "
                "If a technical claim lacks proof, state uncertainty instead "
                "of adding invented specifications, offers or prices. "
                "No markdown. "
            )
        else:
            prefix = (
                "Previous correction was unsafe or unparseable. Return ONLY "
                "JSON with tag and new (<=280 characters). The program already "
                "knows OLD. Replace ONLY OLD with a cautious evidence-based "
                "correction, never new unverified facts. "
            )
        packet = dict(base)
        if attempt:
            packet.pop("old")
            packet["old_exact_text"] = old
        query = prefix + json.dumps(packet, ensure_ascii=False, separators=(",", ":"))
        if len(query.encode()) > 2000:
            raise ValueError("Patch request exceeds Google transport limit")
        page = ask(query)
        u = urlsplit(page.get("page", {}).get("url", ""))
        params = parse_qs(u.query)
        if (page.get("question") != query or u.scheme != "https" or
                u.hostname != "www.google.com" or u.path != "/search" or
                params.get("q") != [query] or params.get("udm") != ["50"]):
            raise ValueError("Research response did not match query")
        proposal = parse_patch_response(page["page"].get("text", ""), tag, old)
        if proposal is None:
            errors.append("No valid tagged short correction")
            continue
        try:
            patched = guarded_patch(data, proposal["old"], proposal["new"])
        except ValueError as exc:
            errors.append(str(exc))
            continue
        return dict(data, draft=patched, checks=[dict(c) for c in data["checks"]])
    # A textual correction cannot supply a missing datasheet or a valid
    # purchase bundle. Search for independent source evidence before giving up.
    sourced = google_source_research(data, result, ask, read=read)
    if sourced is not None:
        return sourced
    raise ValueError("No safe patch accepted; no independently readable source: " +
                     "; ".join(errors)[:240])


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
        if (result.get("status") == "POTWIERDZONE"
                or result["review"] == "NIEPOTWIERDZONE"
                or attempt == 3):
            break
        try:
            if research is google_research:
                proposal = research(data, result, audited_ask, read=read)
            else:
                proposal = research(data, result, audited_ask)
            revised = validate_revision(data, proposal)
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
                google_ai_audit=audit,
                research_trace=data.get("research_trace", []))


def main():
    from warm_worker import ask_emulator
    issue = json.loads(Path(os.environ["GITHUB_EVENT_PATH"]).read_text())["issue"]
    body = issue["body"]
    attention = {"status":"unavailable", "reason":"no_attention_report"}
    attention_path = Path("attention-report.json")
    if attention_path.exists():
        try:
            attention = json.loads(attention_path.read_text())
        except (OSError, ValueError, TypeError):
            attention = {"status":"unavailable", "reason":"unreadable_attention_report"}
    try:
        packet = json.loads(body)
        packet["attention"] = attention
        result = solve(packet, ask_emulator)
    except Exception as exc:
        result = dict(review="NIEPOTWIERDZONE", reason=type(exc).__name__ + ": " + str(exc)[:500])
    result.setdefault("status", "NIEPOTWIERDZONE")
    result["attention"] = {k: attention[k] for k in ("status", "model", "reason", "error_detail", "ranked_indices") if k in attention}
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
