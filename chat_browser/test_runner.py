import json
import unittest
from unittest.mock import patch
from chat_browser.runner import (parse_task, require_public_url,
    is_safe_browsing_url, is_safe_click, is_search_field, classify_page_failure)


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


    def test_blocks_destructive_step(self):
        with patch("chat_browser.runner.require_public_url", return_value="https://example.com"):
            with self.assertRaises(ValueError):
                parse_task(json.dumps({"url": "https://example.com", "steps": [{"action": "check", "selector": "input"}]}))

    def test_rejects_destructive_get_links(self):
        self.assertFalse(is_safe_browsing_url("https://example.com/account/delete"))
        self.assertFalse(is_safe_browsing_url("https://example.com/?action=withdraw"))
        self.assertTrue(is_safe_browsing_url("https://example.com/help/article"))

    def test_allows_navigation_links(self):
        self.assertTrue(is_safe_click({
            "tag": "a", "href": "https://www.iana.org/help/example-domains",
            "label": "Learn more", "role": ""
        }))

    def test_denies_destructive_link_even_on_get(self):
        self.assertFalse(is_safe_click({
            "tag": "a", "href": "https://example.com/delete?id=1",
            "label": "Delete", "role": ""
        }))

    def test_allows_safe_buttons(self):
        self.assertTrue(is_safe_click({"tag": "button", "label": "Show more results"}))
        self.assertTrue(is_safe_click({"tag": "button", "label": "Szukaj"}))
        self.assertFalse(is_safe_click({"tag": "button", "label": "Save changes"}))
        self.assertFalse(is_safe_click({"tag": "button", "label": "Delete all"}))
        self.assertFalse(is_safe_click({"tag": "button", "label": ""}))

    def test_search_inputs_only(self):
        self.assertTrue(is_search_field({"tag": "input", "type": "search", "label": ""}))
        self.assertTrue(is_search_field({"tag": "input", "type": "text", "label": "Search products"}))
        self.assertFalse(is_search_field({"tag": "input", "type": "password", "label": "Search"}))
        self.assertFalse(is_search_field({"tag": "textarea", "type": "", "label": "Search"}))


    def test_readonly_click_text_action(self):
        with patch("chat_browser.runner.require_public_url", return_value="https://example.com"):
            task = parse_task(json.dumps({
                "url": "https://example.com", "steps": [
                    {"action": "click_text", "value": "Northern Ireland"},
                    {"action": "inspect"}
                ]}))
            self.assertEqual(task["steps"][0]["value"], "Northern Ireland")
            self.assertEqual(task["steps"][1]["action"], "inspect")

    def test_click_text_requires_label(self):
        with patch("chat_browser.runner.require_public_url", return_value="https://example.com"):
            with self.assertRaises(ValueError):
                parse_task(json.dumps({"url": "https://example.com", "steps": [
                    {"action": "click_text", "value": ""}
                ]}))

    def test_form_actions_still_forbidden(self):
        with patch("chat_browser.runner.require_public_url", return_value="https://example.com"):
            for action in ("select", "check", "uncheck", "submit"):
                with self.assertRaises(ValueError):
                    parse_task(json.dumps({"url": "https://example.com", "steps": [
                        {"action": action, "selector": "form"}
                    ]}))



    def test_ebay_failure_is_not_success(self):
        msg = classify_page_failure("Error Page | eBay", "https://www.ebay.co.uk/itm/123",
                                    "SORRY Something went wrong on our end")
        self.assertIn("unavailable", msg)

    def test_google_challenge_detected(self):
        msg = classify_page_failure("About", "https://www.google.com/sorry/index?q=1",
                                    "Our systems have detected unusual traffic")
        self.assertIn("challenged", msg)

    def test_token_wall_detected(self):
        msg = classify_page_failure("We need your help", "https://openrss.org/www.ebay.co.uk/sch/i.html",
                                    "you'll need a token to use it.")
        self.assertIn("token", msg)

    def test_normal_page_no_false_block(self):
        self.assertIsNone(classify_page_failure("Example Domain", "https://example.com",
                                               "Example content on a public page."))



if __name__ == "__main__":
    unittest.main()
