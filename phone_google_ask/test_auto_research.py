import json
import unittest
from datetime import datetime, timezone, timedelta
from unittest.mock import patch

from auto_research import (initial_state, next_step, load, run_once, PREFIX,
                           ready)


class AutoResearchTests(unittest.TestCase):
    def setUp(self):
        self.issue = {
            "number": 90012,
            "body": json.dumps({
                "question": "Find a safe S700 solar kit in Belfast, UK",
                "draft": "No complete verified setup yet.",
                "checks": [
                    {"requirement": "Cold Voc within input limit", "status": "unknown"},
                    {"requirement": "Amazon UK or Argos purchase", "status": "unknown"},
                ],
            }),
        }
        self.now = datetime(2026, 11, 22, 18, 0, tzinfo=timezone.utc)

    def test_original_chatgpt_google_review_path_is_preserved(self):
        import importlib.util
        from pathlib import Path
        from consult import review_for_chatgpt
        # The autonomous source gatherer does NOT replace ChatGPT authorship
        # or the separate Google AI review of that ChatGPT draft.
        self.assertTrue(callable(review_for_chatgpt))
        hook = (Path(__file__).resolve().parents[1] /
                "plugins/google-ai-konsultant/hooks/review_turn.py")
        spec = importlib.util.spec_from_file_location("review_turn_for_test", hook)
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        instruction = mod.evaluate({
            "hook_event_name": "UserPromptSubmit",
            "session_id": "agent-integration-test",
            "turn_id": "unique-1",
        })["hookSpecificOutput"]["additionalContext"]
        self.assertIn("ORYGINALNY", instruction)
        self.assertIn("AutoResearch/1", instruction)
        self.assertIn("nowy [consult]", instruction)
        self.assertIn("ChatGPT bada i poprawia", instruction)
        self.assertIn("Google AI osobno recenzuje", instruction)

    def test_no_proof_is_not_marked_verified(self):
        packet = initial_state(self.issue)
        source = {"research_trace": [{
            "url": "https://manufacturer.example/spec",
            "verified_quote": "Open circuit voltage 22.1 V",
        }]}
        with patch("auto_research.google_source_research", return_value=source):
            result, changed = next_step(self.issue, packet, lambda _: None,
                                        now=self.now)
        self.assertTrue(changed)
        self.assertEqual(result["rounds"], 1)
        self.assertEqual(result["status"], "RESEARCHING")
        self.assertEqual(result["checks"][0]["status"], "unknown")
        self.assertEqual(len(result["sources"]), 1)
        self.assertEqual(result["checks"][1]["requirement"],
                         packet["checks"][1]["requirement"])
        self.assertFalse(ready(result, self.now + timedelta(seconds=20)))
        self.assertTrue(ready(result, self.now + timedelta(seconds=50)))

    def test_failure_rotates_instead_of_stopping(self):
        packet = initial_state(self.issue)
        with patch("auto_research.google_source_research",
                   side_effect=RuntimeError("Google unavailable")):
            result, changed = next_step(self.issue, packet, lambda _: None,
                                        now=self.now)
        self.assertTrue(changed)
        self.assertEqual(result["rounds"], 1)
        self.assertEqual(result["status"], "RESEARCHING")
        self.assertTrue(ready(result, self.now + timedelta(seconds=181)))
        with patch("auto_research.google_source_research", return_value=None):
            later, _ = next_step(self.issue, result, lambda _: None,
                                 now=self.now + timedelta(seconds=181))
        self.assertEqual(later["rounds"], 2)
        self.assertEqual(later["status"], "RESEARCHING")

    def test_comment_is_resumable_and_authentic(self):
        state = initial_state(self.issue)
        forged = {"id": 22, "body": PREFIX + json.dumps(state),
                  "user": {"login": "stranger"}}
        self.assertIsNone(load(self.issue, [forged])[1])
        valid = {"id": 23, "body": PREFIX + json.dumps(state),
                 "user": {"login": "github-actions[bot]"}}
        loaded, comment_id = load(self.issue, [forged, valid])
        self.assertEqual(comment_id, 23)
        self.assertEqual(loaded["sha256"], state["sha256"])

    def test_persistent_comment_updated_not_duplicated(self):
        comments = []
        calls = []
        def api(method, path, data=None):
            calls.append((method, path))
            if method == "GET":
                return comments
            if method == "POST":
                comments.append({"id": 33, "body": data["body"],
                                 "user": {"login": "github-actions[bot]"}})
            if method == "PATCH":
                comments[0]["body"] = data["body"]
        with patch("auto_research.google_source_research", return_value=None):
            self.assertTrue(run_once(self.issue, lambda _: None, api,
                                     now=self.now))
            self.assertFalse(run_once(self.issue, lambda _: None, api,
                                      now=self.now + timedelta(seconds=1)))
            self.assertTrue(run_once(self.issue, lambda _: None, api,
                                     now=self.now + timedelta(seconds=50)))
        self.assertEqual(len(comments), 1)
        self.assertEqual(json.loads(comments[0]["body"][len(PREFIX):])["rounds"], 2)
        self.assertEqual([c[0] for c in calls if c[0] != "GET"], ["POST", "PATCH"])


if __name__ == "__main__":
    unittest.main()
