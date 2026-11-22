"""Regression checks: warm Android route must serve both [consult] and [google-ask]."""
import json
import os
import sys
import types
import unittest
from unittest.mock import patch

os.environ.setdefault("GITHUB_REPOSITORY", "Photofiver/gumtree-console-crawler")
import warm_worker


def issue(title, body=""):
    return {"number": 9001, "title": title, "body": body,
            "user": {"login": "Photofiver"}}


class WarmWorkerRoutingTests(unittest.TestCase):
    def test_owner_consult_and_google_ask_are_routed(self):
        self.assertTrue(warm_worker.is_ours(issue("[consult] audit"), False))
        self.assertTrue(warm_worker.is_ours(issue("[google-ask] ping"), False))
        self.assertFalse(warm_worker.is_ours(issue("[google-warm-start] start"), False))
        outsider = issue("[consult] audit")
        outsider["user"]["login"] = "not-owner"
        self.assertFalse(warm_worker.is_ours(outsider, False))

    def test_handle_consult_posts_actual_receipt(self):
        with patch.object(warm_worker, "is_answered", return_value=False), \
             patch.object(warm_worker, "review_consult", return_value='Konsultant/2 {"review":"DO POPRAWY"}'), \
             patch.object(warm_worker, "api") as api:
            self.assertTrue(warm_worker.handle(issue("[consult] audit", '{"question":"test"}')))
            api.assert_called_once()
            self.assertEqual(api.call_args.args[0], "POST")
            self.assertEqual(api.call_args.args[1], "/issues/9001/comments")
            self.assertIn("Konsultant/2", api.call_args.args[2]["body"])

    def test_handle_consult_no_fake_receipt_when_unavailable(self):
        with patch.object(warm_worker, "is_answered", return_value=False), \
             patch.object(warm_worker, "review_consult", return_value=None), \
             patch.object(warm_worker, "api") as api:
            self.assertFalse(warm_worker.handle(issue("[consult] audit")))
            api.assert_not_called()

    def test_consult_does_real_screening_and_google_review(self):
        payload = {"question": "Main goal", "draft": "Review this proposal.",
                   "checks": [{"requirement": "A", "status": "unknown"}],
                   "idea_target": 1000, "candidate_log": []}
        fake_transformers = types.SimpleNamespace(SentenceTransformer=lambda *a, **k: object())
        verdict = {"review": "DO POPRAWY", "status": "NIEPOTWIERDZONE",
                   "google_ai_queries_sent": 1, "google_ai_responses_received": 1}
        with patch.dict(sys.modules, {"sentence_transformers": fake_transformers}), \
             patch("attention_guard.build_focus", return_value={"status": "active", "model": "fake"}), \
             patch("explore.screen", return_value={"summary": {"screened": 1000}}) as screen, \
             patch("consult.review_for_chatgpt", return_value=verdict) as reviewer, \
             patch.object(warm_worker, "_ATTENTION_MODEL", None):
            result = warm_worker.review_consult(issue("[consult] audit", json.dumps(payload)))
        self.assertIsInstance(result, str)
        self.assertTrue(result.startswith("Konsultant/2 "))
        body = json.loads(result.split(" ", 1)[1])
        self.assertEqual(body["exploration"]["screened"], 1000)
        self.assertEqual(body["google_ai_responses_received"], 1)
        self.assertEqual(body["attention"]["status"], "active")
        screen.assert_called_once()
        reviewer.assert_called_once()


if __name__ == "__main__":
    unittest.main()
