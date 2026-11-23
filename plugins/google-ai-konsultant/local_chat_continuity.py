#!/usr/bin/env python3
"""Optional local GitHub -> ordinary ChatGPT conversation continuation bridge.

Requires tritao/chatgpt-web and an already authenticated local Chrome.
Never upload or commit any ChatGPT session files or cookies to GitHub.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess
import sys
import time
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

REPO = "Photofiver/gumtree-console-crawler"
API = "https://api.github.com/repos/" + REPO


def digest(text):
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


class GitHub:
    def __init__(self, token=""):
        self.token = token

    def request(self, method, path, payload=None):
        headers = {"Accept": "application/vnd.github+json",
                   "User-Agent": "google-ai-consultant-local-bridge",
                   "X-GitHub-Api-Version": "2022-11-28"}
        if self.token:
            headers["Authorization"] = "Bearer " + self.token
        body = json.dumps(payload, ensure_ascii=False).encode() if payload is not None else None
        if body is not None:
            headers["Content-Type"] = "application/json"
        request = Request(API + path, data=body, headers=headers, method=method)
        with urlopen(request, timeout=25) as response:
            return json.load(response)

    def issue(self, number):
        return self.request("GET", "/issues/" + str(number))

    def comments(self, number):
        return self.request("GET", "/issues/" + str(number) + "/comments?per_page=100")

    def find_child(self, marker, parent):
        # Recovery after successful remote creation and local crash.
        for page in range(1, 11):
            issues = self.request("GET", "/issues?state=all&per_page=100&page=" + str(page))
            for i in issues:
                if i.get("pull_request") or i.get("user", {}).get("login") != "Photofiver":
                    continue
                if marker not in (i.get("body") or "") or not i.get("title", "").startswith("[consult]"):
                    continue
                try:
                    packet = json.loads(i["body"])
                except (ValueError, TypeError):
                    continue
                if packet.get("parent_issue") == parent and packet.get("bridge_request_id") == marker:
                    return i["number"]
            if len(issues) < 100:
                return None
        raise RuntimeError("Cannot establish duplicate safety after 1000 issues")

    def create_consult(self, packet):
        if not self.token:
            raise RuntimeError("GH_TOKEN required for a new issue (keep it local)")
        return self.request("POST", "/issues", {
            "title": "[consult] ordinary-chat follow-up " + packet["bridge_request_id"][:16],
            "body": json.dumps(packet, ensure_ascii=False, separators=(",", ":"))
        })


def matching_receipt(issue, comments):
    if issue.get("user", {}).get("login") != "Photofiver" or not issue.get("title", "").startswith("[consult]"):
        raise ValueError("Issue must be an owner-created [consult]")
    body_hash = digest(issue.get("body") or "")
    for comment in reversed(comments):
        if comment.get("user", {}).get("login") != "github-actions[bot]":
            continue
        text = comment.get("body") or ""
        if not text.startswith("Konsultant/2 "):
            continue
        try:
            receipt = json.loads(text[len("Konsultant/2 "):])
        except ValueError:
            continue
        if receipt.get("sha256") == body_hash and receipt.get("issue") == issue["number"]:
            return receipt
    return None


def parse_reply(text):
    packet = json.loads(text.strip())
    if not isinstance(packet, dict) or packet.get("action") not in ("new_consult", "blocked"):
        raise ValueError("ChatGPT did not return a single expected JSON action")
    return packet


def validate_revision(issue, reply, marker):
    original = json.loads(issue.get("body") or "{}")
    revised = reply.get("data")
    if not isinstance(revised, dict) or not isinstance(original, dict):
        raise ValueError("Expected a complete ChatGPT-authored packet")
    if revised.get("question") != original.get("question"):
        raise ValueError("Original question was changed")
    draft = revised.get("draft")
    if not isinstance(draft, str) or len(draft.strip()) < 30:
        raise ValueError("Missing revised draft")
    if " ".join(draft.split()) == " ".join(str(original.get("draft", "")).split()):
        raise ValueError("Identical draft would repeat the same unsuccessful review")
    before, after = original.get("checks"), revised.get("checks")
    if not isinstance(before, list) or not before or not isinstance(after, list):
        raise ValueError("Missing checks")
    if [c["requirement"] for c in before] != [c.get("requirement") for c in after]:
        raise ValueError("An original requirement was modified or lost")
    for check in after:
        if check.get("status") not in ("met", "unknown", "unmet"):
            raise ValueError("Unexpected status")
        if check["status"] == "met":
            if not (isinstance(check.get("source"), str) and check["source"].startswith("https://")
                    and isinstance(check.get("quote"), str) and len(check["quote"].strip()) >= 8):
                raise ValueError("Unsupported claim marked met")
    if revised.get("parent_issue") != issue["number"]:
        raise ValueError("Incorrect parent_issue")
    if revised.get("review_round") != int(original.get("review_round", 1)) + 1:
        raise ValueError("Incorrect review_round")
    packet = dict(original)
    packet.update(revised)
    packet["parent_issue"] = issue["number"]
    packet["bridge_request_id"] = marker
    return packet


def make_prompt(issue, receipt, marker):
    return (
        "Continue this EXISTING ordinary ChatGPT conversation after the new Google AI "
        "review. Independently research and verify the original user's complete "
        "requirements, correct the entire draft, and preserve all constraints. "
        "Google AI is only a reviewer. Do not fabricate sources, prices or "
        "electrical safety. Do NOT create a GitHub issue with a tool; the local "
        "bridge will transport YOUR independently written revision to GitHub. "
        "Output ONE JSON object only (no Markdown). If progress is possible use "
        '{"action":"new_consult","data":{"question":"identical original question",'
        '"draft":"complete revised analysis","checks":[{"requirement":"exact original",'
        '"status":"unknown","finding":"..."}],"parent_issue":NUMBER,'
        '"review_round":NEXT_NUMBER}}. '
        'If genuinely blocked by a rate limit, unavailable session, required approval '
        'or proven physical impossibility, use {"action":"blocked","reason":"..."}; '
        "never claim success without a real Google AI verdict and evidence. "
        "Request ID: " + marker + "\n"
        "ISSUE NUMBER: " + str(issue["number"]) + "\n"
        "ORIGINAL ISSUE JSON:\n" + issue["body"] + "\n"
        "AUTHENTICATED GITHUB WORKFLOW RECEIPT (check actual Google responses):\n" +
        json.dumps(receipt, ensure_ascii=False)
    )


class Controller:
    def __init__(self, github, send, path, root, conversation):
        self.github, self.send, self.path = github, send, path
        if path.exists():
            self.state = json.loads(path.read_text(encoding="utf-8"))
            if self.state.get("root") != root or self.state.get("conversation") != conversation:
                raise ValueError("State belongs to another issue or conversation")
        else:
            self.state = {"root": root, "conversation": conversation,
                          "current": root, "delivery": None}
            self.save()

    def save(self):
        self.write_state(self.path, self.state)

    @staticmethod
    def write_state(path, state):
        path.parent.mkdir(parents=True, exist_ok=True)
        tmp = path.with_name(path.name + ".tmp")
        fd = os.open(tmp, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
        with os.fdopen(fd, "w", encoding="utf-8") as fp:
            json.dump(state, fp, ensure_ascii=False)
            fp.flush()
            os.fsync(fp.fileno())
        os.replace(tmp, path)

    def once(self):
        if self.state.get("terminal"):
            return self.state["terminal"]
        issue = self.github.issue(self.state["current"])
        receipt = matching_receipt(issue, self.github.comments(issue["number"]))
        if receipt is None:
            return "waiting_for_google_ai"
        marker = digest(str(issue["number"]) + ":" + receipt["sha256"] + ":" + str(receipt.get("run", "")))
        delivery = self.state.get("delivery")
        if delivery:
            if delivery["marker"] != marker:
                return "previous_delivery_unresolved_do_not_resend"
            if delivery["status"] != "ready":
                return "delivery_uncertain_do_not_resend"
            return self.create_child(delivery["packet"], marker, issue["number"])
        verified = (receipt.get("status") == "POTWIERDZONE" and
                    receipt.get("review") == "SPRAWDZONE" and
                    receipt.get("google_ai_responses_received", 0) > 0)
        if verified:
            # Publish the final outcome into the same ordinary conversation.
            # Persist before sending so a browser timeout cannot double-submit.
            self.state["delivery"] = {"marker": marker, "status": "reporting_final"}
            self.save()
            self.send(self.state["conversation"],
                      "Google AI has completed its authenticated review of "
                      "the following consultation. Give the user the final "
                      "evidence-based answer, preserving all original conditions "
                      "and distinguishing verified findings from uncertainty. "
                      "Do not open any new issue. ISSUE JSON:\n" + issue["body"] +
                      "\nREVIEW:\n" + json.dumps(receipt, ensure_ascii=False))
            self.state["terminal"] = "verified_issue_" + str(issue["number"])
            self.state["delivery"] = None
            self.save()
            return self.state["terminal"]
        self.state["delivery"] = {"marker": marker, "status": "sending"}
        self.save()  # Persist BEFORE sending. Never blindly resend on an uncertain outcome.
        answer = parse_reply(self.send(self.state["conversation"], make_prompt(issue, receipt, marker)))
        if answer["action"] == "blocked":
            self.state["terminal"] = "blocked: " + str(answer.get("reason", "no reason"))
            self.save()
            return self.state["terminal"]
        packet = validate_revision(issue, answer, marker)
        self.state["delivery"] = {"marker": marker, "status": "ready", "packet": packet}
        self.save()
        return self.create_child(packet, marker, issue["number"])

    def create_child(self, packet, marker, parent):
        child = self.github.find_child(marker, parent)
        if child is None:
            child = self.github.create_consult(packet)["number"]
        self.state.update(current=child, delivery=None)
        self.save()
        return "created_child_issue_" + str(child)


def valid_id(value):
    return isinstance(value, str) and re.fullmatch(r"[A-Za-z0-9_-]{8,160}", value) is not None


def open_controller(github, send, path, root, conversation, cli):
    if path.exists():
        saved = json.loads(path.read_text(encoding="utf-8"))
        if saved.get("root") != root:
            raise ValueError("State belongs to another issue")
        if saved.get("creating") and valid_id(conversation):
            Controller.write_state(path, {"root": root, "current": root,
                                          "conversation": conversation, "delivery": None})
            return Controller(github, send, path, root, conversation)
        if not valid_id(saved.get("conversation")):
            raise ValueError("Creation outcome uncertain: inspect the chat, then pass its --conversation-id")
        return Controller(github, send, path, root, conversation or saved["conversation"])
    if conversation:
        return Controller(github, send, path, root, conversation)

    path.parent.mkdir(parents=True, exist_ok=True)
    # Reserve this state before the external call. If Chrome times out after
    # accepting the message, a restart must not silently open a second chat.
    fd = os.open(path, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
    with os.fdopen(fd, "w", encoding="utf-8") as fp:
        json.dump({"root": root, "creating": True}, fp)
        fp.flush()
        os.fsync(fp.fileno())
    prompt = (f"Ta rozmowa dotyczy konsultacji {REPO}#{root}. "
              "W następnej wiadomości otrzymasz zadanie i wynik Google AI. "
              "Na razie potwierdź gotowość.")
    result = subprocess.run([str(cli), "new", "--output", "json"], input=prompt,
                            capture_output=True, text=True, timeout=900, check=True)
    payload = json.loads(result.stdout)
    chat_id = payload.get("conversation_id") if isinstance(payload, dict) else None
    if not valid_id(chat_id):
        raise ValueError("chatgpt-web new did not return a valid conversation_id")
    # Controller.save uses an atomic replacement in the same directory.
    state = {"root": root, "conversation": chat_id, "current": root, "delivery": None}
    Controller.write_state(path, state)
    return Controller(github, send, path, root, chat_id)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root-issue", type=int, required=True)
    parser.add_argument("--conversation-id", help="Existing chat ID; omit to create or resume the saved chat")
    parser.add_argument("--chatgpt-web", type=Path, required=True)
    parser.add_argument("--state", type=Path,
                        default=Path.home() / ".local/state/google-ai-konsultant/continuity.json")
    parser.add_argument("--poll-seconds", type=int, default=120)
    parser.add_argument("--once", action="store_true")
    args = parser.parse_args()
    if args.root_issue < 1 or args.poll_seconds < 60:
        parser.error("Issue must be positive and polling >=60 seconds")
    if args.conversation_id is not None and not valid_id(args.conversation_id):
        parser.error("Invalid conversation ID")
    if not args.chatgpt_web.is_file():
        parser.error("No local chatgpt-web/run script")
    def send(conversation, prompt):
        response = subprocess.run(
            [str(args.chatgpt_web.resolve()), "send", conversation, prompt],
            stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True,
            timeout=900, check=False)
        if response.returncode:
            raise RuntimeError("ChatGPT browser CLI returned error " + str(response.returncode)
                               + "; inspect the conversation before any retry")
        return response.stdout
    try:
        c = open_controller(GitHub(os.environ.get("GH_TOKEN", "")), send,
                            args.state.expanduser(), args.root_issue, args.conversation_id,
                            args.chatgpt_web.resolve())
    except (ValueError, OSError, subprocess.SubprocessError) as exc:
        print(f"Chat initialization failed: {exc}", file=sys.stderr)
        return 1
    while True:
        try:
            status = c.once()
            print(status, flush=True)
        except (ValueError, RuntimeError, HTTPError, URLError, OSError,
                subprocess.TimeoutExpired) as exc:
            print(type(exc).__name__ + ": " + str(exc)[:240], file=sys.stderr)
            return 1
        if args.once or status.startswith(("verified_", "blocked:", "delivery_uncertain",
                                           "previous_delivery")):
            return 0 if not status.startswith(("delivery_uncertain", "previous_delivery")) else 1
        time.sleep(args.poll_seconds)


if __name__ == "__main__":
    raise SystemExit(main())
