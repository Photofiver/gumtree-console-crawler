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
            self.assertEqual(api.call_count, 2)
            self.assertEqual(api.call_args_list[0].args[0], "POST")
            self.assertEqual(api.call_args_list[0].args[1], "/issues/9001/comments")
            self.assertIn("Konsultant/2", api.call_args_list[0].args[2]["body"])
            self.assertEqual(api.call_args_list[1].args[1],
                             "/actions/workflows/google-ai-consult-continuity.yml/dispatches")

    def test_handle_consult_no_fake_receipt_when_unavailable(self):
        with patch.object(warm_worker, "is_answered", return_value=False), \
             patch.object(warm_worker, "review_consult", return_value=None), \
             patch.object(warm_worker, "api") as api:
            self.assertFalse(warm_worker.handle(issue("[consult] audit")))
            api.assert_not_called()

    def test_persistent_browser_runs_once_at_worker_start(self):
        with patch.dict(os.environ, {"GOOGLE_AI_PERSISTENT_WEBVIEW": "1"}), \
             patch.object(warm_worker, "start_persistent_webview") as launch, \
             patch.object(warm_worker, "ask_persistent_webview",
                          return_value={"aiResponseReady": True}) as ask:
            result = warm_worker.ask_emulator("2+2")
        self.assertTrue(result["aiResponseReady"])
        ask.assert_called_once_with("2+2")
        launch.assert_not_called()  # Already running, not launched per question.

    def test_persistent_protocol_rejects_old_response(self):
        from unittest.mock import MagicMock
        import subprocess
        import tempfile
        import shutil
        with patch("secrets.token_hex", return_value="abcdef12"), \
             patch.object(warm_worker.subprocess, "run") as run, \
             patch.object(warm_worker.time, "sleep"), \
             patch.object(warm_worker.time, "monotonic", side_effect=[1.0, 2.0, 3.0, 4.0]):
            def response(command, **kwargs):
                if command[1:3] == ["shell", "cat"]:
                    return subprocess.CompletedProcess(command, 0, stdout=json.dumps({
                        "id": "abcdef12", "question": "3+4",
                        "loadUrl": "https://www.google.com/search?udm=50",
                        "aiResponseReady": True, "page": {"text": "7"}
                    }), stderr="")
                return subprocess.CompletedProcess(command, 0, stdout="", stderr="")
            run.side_effect = response
            with self.assertRaisesRegex(RuntimeError, "question mismatch"):
                warm_worker.ask_persistent_webview("2+2")

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
