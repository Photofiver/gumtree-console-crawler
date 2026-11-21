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
              "REVISE if any claim is false or lacks evidence. Give a specific reason. "
              "End with ONE exact separate line: REVISE " + tag +
              " OR PASS " + tag + ".\n")
    # Repeat context if it fits. Otherwise the entire original remains in the fragments.
    if len(context.encode()) <= 800:
        prefix += context + "\n"
    chunks = list(parts(payload, 2000 - len(prefix.encode()) - 40))
    votes = []
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
            return dict(review="DO POPRAWY", reason=answer.partition("\n\n")[2],
                        parts=len(chunks), reviewed=i, blocked=blocked)
        if not answer.startswith("SPRAWDZONE ·"):
            return dict(review="NIEPOTWIERDZONE", reason="Google AI did not return an authenticated PASS/REVISE marker for part "+str(i)+" after two distinct prompts",
                        parts=len(chunks), reviewed=i, blocked=blocked)
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


def google_research(data, result, ask):
    """Ask for changed findings in context. Treat suggested quotes as unverified."""
    tag = secrets.token_hex(6)
    prompt = ("Search for a different concrete solution. Check the criticism against manufacturer and "
              "retailer pages. Return one JSON object between standalone lines BEGIN-" + tag +
              " and END-" + tag + ". Keys: draft (revised complete answer), evidence (list of objects "
              "with index (zero based), status met/unknown/failed, finding, source URL, exact quote). "
              "Keep draft under 380 characters. Plain text, no math formatting. Preserve all requirements. Input: ")
    evidence = [{"index": i, **c} for i, c in enumerate(data["checks"])]
    payload = json.dumps(dict(question=data["question"], previous=data["draft"],
                              feedback=result, checks=evidence), ensure_ascii=False)
    # Research each fragment if necessary; merge proposed evidence by original index.
    updated = dict(data, checks=[dict(c) for c in data["checks"]])
    drafts = []
    for piece in parts(payload, 2000-len(prompt.encode())):
        query = prompt + piece
        page = ask(query)
        u = urlsplit(page.get("page", {}).get("url", ""))
        params = parse_qs(u.query)
        if (page.get("question") != query or u.scheme != "https" or u.hostname != "www.google.com"
                or u.path != "/search" or params.get("q") != [query] or params.get("udm") != ["50"]):
            raise ValueError("Research response did not match query")
        match = re.search(r"(?ms)^BEGIN-" + tag + r"[ \t]*\n(.*?)^END-" + tag + r"[ \t]*$",
                          page["page"]["text"])
        if not match:
            raise ValueError("No complete structured research response")
        raw = match[1].strip().removeprefix("```json").removeprefix("```").removesuffix("```").strip()
        # Google WebView renders line wraps inside JSON string literals.
        proposal = json.loads(raw, strict=False)
        if not isinstance(proposal["draft"], str) or not proposal["draft"].strip():
            raise ValueError("Empty revision")
        drafts.append(proposal["draft"].strip())
        for entry in proposal.get("evidence", []):
            i = entry["index"]
            if isinstance(i, str) and i.isdecimal():
                i = int(i)
            if type(i) != int or not 0 <= i < len(evidence):
                raise ValueError("Unknown requirement index")
            for key in ("status", "finding", "source", "quote"):
                if key in entry and isinstance(entry[key], str):
                    updated["checks"][i][key] = entry[key]
    updated["draft"] = "\n".join(drafts)
    return updated


def evidence_revision(data, result, read):
    """Withdraw the disputed recommendation and re-open exact sources after a failed research parse."""
    checks, facts, gaps = [], [], []
    for check in data["checks"]:
        item = dict(check)
        url, quote = item.get("source"), " ".join(item.get("quote", "").split())
        observed = False
        if url and len(quote) >= 8:
            try:
                observed = quote in read(url)
            except (OSError, ValueError, subprocess.SubprocessError):
                pass
        if observed:
            facts.append(url + " — " + quote)
        if item.get("status") != "failed" or not observed:
            item["status"] = "unknown"
        gaps.append(item["requirement"])
        checks.append(item)
    if not facts:
        return None
    criticism = " ".join(result.get("reason", "").split())
    draft = ("Wycofuję wcześniejszą rekomendację. W źródłach odczytano: " + " | ".join(facts)
             + ". Do potwierdzenia dla jednego rozwiązania: " + "; ".join(gaps) + ".")
    if criticism:
        draft += " Uwaga recenzenta do sprawdzenia: " + criticism
    return dict(data, draft=draft, checks=checks)


def solve(data, ask, read=source_text, research=google_research):
    history, seen = [], set()
    for attempt in range(1, 4):
        key = " ".join(data["draft"].split()).casefold()
        if key in seen:
            break
        seen.add(key)
        result = evaluate(data, ask, read)
        history.append(dict(round=attempt, draft=data["draft"], **result))
        if result.get("status") == "POTWIERDZONE" or result["review"] == "NIEPOTWIERDZONE" or attempt == 3:
            break
        try:
            revised = research(data, result, ask)
        except (ValueError, KeyError, TypeError, OSError, subprocess.SubprocessError, RuntimeError) as exc:
            history[-1]["research_error"] = str(exc)[:400]
            revised = evidence_revision(data, result, read)
            if revised is None:
                result["obstacle"] = "Research: " + str(exc)[:400]
                break
        if " ".join(revised["draft"].split()).casefold() in seen:
            result["obstacle"] = "Research repeated a previously reviewed draft"
            break
        data = revised
    return dict(result, status=result.get("status","NIEPOTWIERDZONE"),
                history=history, checks=data["checks"], draft=history[-1]["draft"])


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
