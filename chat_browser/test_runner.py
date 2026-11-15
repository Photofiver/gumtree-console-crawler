import json
import unittest
from unittest.mock import patch
from chat_browser.runner import parse_task, require_public_url


class RunnerTests(unittest.TestCase):
    def test_simple_task(self):
        with patch("chat_browser.runner.require_public_url", return_value="https://example.com"):
            task = parse_task(json.dumps({"url": "https://example.com", "steps": [{"action": "click", "selector": "a"}]}))
            self.assertEqual(task["steps"][0]["action"], "click")

    def test_reject_command_injection(self):
        with patch("chat_browser.runner.require_public_url", return_value="https://example.com"):
            with self.assertRaises(ValueError):
                parse_task(json.dumps({"url": "https://example.com", "steps": [{"action": "exec", "value": "rm -rf /"}]}))

    def test_reject_big_wait(self):
        with patch("chat_browser.runner.require_public_url", return_value="https://example.com"):
            with self.assertRaises(ValueError):
                parse_task(json.dumps({"url": "https://example.com", "steps": [{"action": "wait", "ms": 9000}]}))

    def test_reject_localhost(self):
        with self.assertRaises(ValueError):
            require_public_url("http://localhost:8000/")

    def test_reject_file(self):
        with self.assertRaises(ValueError):
            require_public_url("file:///etc/passwd")

    def test_reject_credentials(self):
        with self.assertRaises(ValueError):
            require_public_url("https://user:password@example.com")

    def test_fenced_json(self):
        with patch("chat_browser.runner.require_public_url", return_value="https://example.com"):
            self.assertEqual(parse_task('```json\n{"url":"https://example.com"}\n```')["url"], "https://example.com")


if __name__ == "__main__":
    unittest.main()
