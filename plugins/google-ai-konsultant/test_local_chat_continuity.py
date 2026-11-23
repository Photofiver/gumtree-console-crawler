"""Tests for the optional ordinary-chat continuation controller; no real logins."""
import hashlib
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

SCRIPT = Path(__file__).with_name("local_chat_continuity.py")
spec = importlib.util.spec_from_file_location("local_chat_continuity", SCRIPT)
bridge = importlib.util.module_from_spec(spec)
spec.loader.exec_module(bridge)


def issue(number=777, round_=1):
    data = {
        "question": "Find compatible charging equipment without inventing sources",
        "draft": "Initial analysis with no complete verified solution.",
        "checks": [
            {"requirement": "Electrical safety", "status": "unknown", "finding": "Not yet checked"},
            {"requirement": "Realistic winter output", "status": "unknown", "finding": "Not yet checked"},
        ],
        "review_round": round_,
    }
    return {"number": number, "title": "[consult] test",
            "user": {"login": "Photofiver"},
            "body": json.dumps(data, ensure_ascii=False)}


def review(i, status="NIEPOTWIERDZONE", verdict="DO POPRAWY"):
    body = {"sha256": bridge.digest(i["body"]), "issue": i["number"],
            "review": verdict, "status": status, "run": 33,
            "reason": "Need real evidence", "google_ai_responses_received": 1}
    return {"user": {"login": "github-actions[bot]"},
            "body": "Konsultant/2 " + json.dumps(body)}


def next_answer(i):
    d = json.loads(i["body"])
    d["draft"] = "Revised analysis containing independent details and checked evidence."
    d["parent_issue"] = i["number"]
    d["review_round"] = d["review_round"] + 1
    return json.dumps({"action": "new_consult", "data": d})


class FakeGitHub:
    def __init__(self, i, comments):
        self.issues = {i["number"]: i}
        self._comments = {i["number"]: comments}
        self.creates = 0
        self.child = None

    def issue(self, number):
        return self.issues[number]

    def comments(self, number):
        return self._comments.get(number, [])

    def find_child(self, marker, parent):
        return self.child

    def create_consult(self, data):
        self.creates += 1
        n = 778
        self.child = n
        self.issues[n] = {"number": n, "title": "[consult] follow-up",
                          "user": {"login": "Photofiver"},
                          "body": json.dumps(data)}
        self._comments[n] = []
        return {"number": n}


class BridgeTests(unittest.TestCase):
    def test_only_authenticated_matching_bot_receipt(self):
        i = issue()
        correct = review(i)
        fake = {"user": {"login": "Photofiver"}, "body": correct["body"]}
        self.assertIsNone(bridge.matching_receipt(i, [fake]))
        self.assertEqual(bridge.matching_receipt(i, [fake, correct])["review"], "DO POPRAWY")
        j = dict(i, body=i["body"] + "edited")
        self.assertIsNone(bridge.matching_receipt(j, [correct]))

    def test_revised_packet_preserves_requirements(self):
        i = issue()
        response = bridge.parse_reply(next_answer(i))
        packet = bridge.validate_revision(i, response, "1234")
        self.assertEqual(packet["bridge_request_id"], "1234")
        self.assertEqual(packet["parent_issue"], 777)
        self.assertEqual(packet["review_round"], 2)
        response["data"]["checks"].pop()
        with self.assertRaises(ValueError):
            bridge.validate_revision(i, response, "1234")

    def test_identical_draft_rejected(self):
        i = issue()
        response = bridge.parse_reply(next_answer(i))
        response["data"]["draft"] = json.loads(i["body"])["draft"]
        with self.assertRaisesRegex(ValueError, "Identical"):
            bridge.validate_revision(i, response, "marker")

    def test_google_review_creates_child_and_waits_for_next(self):
        i = issue()
        fake = FakeGitHub(i, [review(i)])
        messages = []
        def sender(conversation, prompt):
            messages.append((conversation, prompt))
            return next_answer(i)
        with tempfile.TemporaryDirectory() as folder:
            c = bridge.Controller(fake, sender, Path(folder)/"state.json", 777, "abcABC234567")
            self.assertEqual(c.once(), "created_child_issue_778")
            self.assertEqual(fake.creates, 1)
            self.assertEqual(len(messages), 1)
            self.assertEqual(c.once(), "waiting_for_google_ai")
            reopened = bridge.Controller(fake, sender, Path(folder)/"state.json", 777, "abcABC234567")
            self.assertEqual(reopened.state["current"], 778)

    def test_uncertain_send_is_never_automatically_replayed(self):
        i = issue()
        fake = FakeGitHub(i, [review(i)])
        calls = []
        def broken_send(*args):
            calls.append(args)
            raise RuntimeError("browser timeout after possible delivery")
        with tempfile.TemporaryDirectory() as folder:
            c = bridge.Controller(fake, broken_send, Path(folder)/"state.json", 777, "abcABC234567")
            with self.assertRaises(RuntimeError):
                c.once()
            self.assertEqual(c.once(), "delivery_uncertain_do_not_resend")
            self.assertEqual(len(calls), 1)

    def test_ready_state_recovers_without_new_send(self):
        i = issue()
        fake = FakeGitHub(i, [review(i)])
        with tempfile.TemporaryDirectory() as folder:
            c = bridge.Controller(fake, lambda *args: next_answer(i),
                                  Path(folder)/"state.json", 777, "abcABC234567")
            c.once()
            fake._comments[778] = []
            self.assertEqual(fake.creates, 1)

    def test_positive_verdict_does_not_trigger_new_consult(self):
        i = issue()
        fake = FakeGitHub(i, [review(i, "POTWIERDZONE", "SPRAWDZONE")])
        messages = []
        with tempfile.TemporaryDirectory() as folder:
            c = bridge.Controller(fake, lambda *args: messages.append(args) or "reported",
                                  Path(folder)/"state.json", 777, "abcABC234567")
            self.assertEqual(c.once(), "verified_issue_777")
            self.assertEqual(fake.creates, 0)
            self.assertEqual(len(messages), 1)
            self.assertIn("evidence-based answer", messages[0][1])


class ConversationStartupTests(unittest.TestCase):
    def setUp(self):
        folder = tempfile.TemporaryDirectory()
        self.addCleanup(folder.cleanup)
        self.path = Path(folder.name) / "state.json"
        self.cli = Path("/test/run")

    def start(self, conversation=None):
        return bridge.open_controller(None, None, self.path, 777, conversation, self.cli)

    @patch.object(bridge.subprocess, "run")
    def test_new_chat_is_saved_and_reused_on_restart(self, run):
        run.return_value.stdout = '{"conversation_id":"created-1234","messages":[]}'
        self.assertEqual(self.start().state["conversation"], "created-1234")
        self.assertEqual(self.start().state["conversation"], "created-1234")
        run.assert_called_once()
        self.assertEqual(run.call_args.args[0], [str(self.cli), "new", "--output", "json"])
        self.assertIn("#777", run.call_args.kwargs["input"])

    @patch.object(bridge.subprocess, "run")
    def test_existing_chat_skips_creation(self, run):
        self.assertEqual(self.start("existing-1234").state["conversation"], "existing-1234")
        self.assertEqual(self.start().state["conversation"], "existing-1234")
        run.assert_not_called()

    @patch.object(bridge.subprocess, "run")
    def test_missing_id_does_not_create_a_duplicate(self, run):
        run.return_value.stdout = '{"conversation_id":null}'
        with self.assertRaisesRegex(ValueError, "valid conversation_id"):
            self.start()
        with self.assertRaisesRegex(ValueError, "uncertain"):
            self.start()
        self.assertEqual(self.start("recovered-1234").state["conversation"], "recovered-1234")
        run.assert_called_once()


if __name__ == "__main__":
    unittest.main()
