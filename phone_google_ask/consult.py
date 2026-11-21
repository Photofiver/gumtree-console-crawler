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
from urllib.parse import urlsplit

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
    if not ips or not all(ipaddress.ip_address(ip).is_global for ip in ips):
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
    blocked, pages = [], {}
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
    context = "Question: " + question + "\nRequirements: " + " | ".join(c["requirement"] for c in checks)
    payload = json.dumps(data, ensure_ascii=False, separators=(",", ":"))
    tag = secrets.token_hex(8)
    prefix = ("Independently verify this analysis, seek counterexamples. Distinguish missing evidence "
              "from a false claim. Review only the visible material. Give reasons and finish with "
              "exactly PASS or REVISE followed by a space and " + tag + " on a separate line.\n")
    # Repeat context if it fits. Otherwise the entire original remains in the fragments.
    if len(context.encode()) <= 800:
        prefix += context + "\n"
    chunks = list(parts(payload, 2000 - len(prefix.encode()) - 40))
    votes = []
    for i, chunk in enumerate(chunks, 1):
        query = prefix + f"Part {i}/{len(chunks)}\n" + chunk
        req = dict(query=query, tag=tag, draft=draft)
        answer = decide(req, ask(query))
        votes.append(answer.split("\n\n", 1)[0])
        if answer.startswith("DO POPRAWY"):
            return dict(review="DO POPRAWY", reason=answer.partition("\n\n")[2],
                        parts=len(chunks), reviewed=i, blocked=blocked)
        if not answer.startswith("SPRAWDZONE ·"):
            return dict(review="NIEPOTWIERDZONE", reason="Brak jednoznacznej oceny części "+str(i),
                        parts=len(chunks), reviewed=i, blocked=blocked)
    # Fragment approvals cannot establish consistency across separate model contexts.
    solved = not blocked and len(votes) == 1
    return dict(review="SPRAWDZONE", status="POTWIERDZONE" if solved else "NIEPOTWIERDZONE",
                parts=len(chunks), reviewed=len(votes), blocked=blocked)


def main():
    from warm_worker import ask_emulator
    issue = json.loads(Path(os.environ["GITHUB_EVENT_PATH"]).read_text())["issue"]
    body = issue["body"]
    try:
        result = evaluate(json.loads(body), ask_emulator)
    except Exception as exc:
        result = dict(review="NIEPOTWIERDZONE", reason=type(exc).__name__ + ": " + str(exc)[:500])
    result.setdefault("status", "NIEPOTWIERDZONE")
    result.update(issue=issue["number"], sha256=digest(body))
    Path("consult-result.json").write_text(json.dumps(result, ensure_ascii=False))


if __name__ == "__main__":
    main()
