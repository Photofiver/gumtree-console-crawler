import json
import unittest
from unittest.mock import patch
from chat_browser.runner import (parse_task, require_public_url,
    is_safe_browsing_url, is_safe_click, is_search_field, classify_page_failure,
    observed_safe_link, point_in_canvas)
from chat_browser.blueprint_session import encode_state, decode_state, filter_blueprint_state


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



    def test_snapshot_link_navigation_is_guarded(self):
        actions = [{"frames": [{"links": [
            {"text": "Workbench", "url": "https://example.com/#lab"},
            {"text": "Delete my data", "url": "https://example.com/delete"},
            {"text": "Continue", "url": "https://example.com/withdraw"},
        ]}]}]
        with patch("chat_browser.runner.require_public_url", side_effect=lambda u: u):
            self.assertEqual(
                observed_safe_link(actions, "Workbench"),
                "https://example.com/#lab"
            )
            self.assertIsNone(observed_safe_link(actions, "Delete"))
            self.assertIsNone(observed_safe_link(actions, "Continue"))
            self.assertIsNone(observed_safe_link(actions, "Missing"))


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


    def test_snapshot_and_scroll_steps(self):
        with patch("chat_browser.runner.require_public_url", return_value="https://example.com"):
            task = parse_task(json.dumps({"url": "https://example.com", "steps": [
                {"action": "snapshot"}, {"action": "scroll", "px": 800},
                {"action": "wait_for", "selector": "div.result", "ms": 9000}
            ]}))
            self.assertEqual(len(task["steps"]), 3)

    def test_rejects_long_wait_and_scroll(self):
        with patch("chat_browser.runner.require_public_url", return_value="https://example.com"):
            for step in [
                {"action": "wait_for", "selector": "div", "ms": 99999},
                {"action": "scroll", "px": -200},
                {"action": "scroll", "px": 9999}
            ]:
                with self.assertRaises(ValueError):
                    parse_task(json.dumps({"url": "https://example.com", "steps": [step]}))


    def test_blueprint_authenticated_task_is_restricted(self):
        with patch("chat_browser.runner.require_public_url"):
            valid = parse_task(json.dumps({
                "url": "https://www.blueprint.io/",
                "auth": "blueprint",
                "steps": [{"action": "blueprint_prompt", "value": "Build a simple LED lamp"}]
            }))
            self.assertEqual(valid["auth"], "blueprint")
            for bad in [
                {"url": "https://example.com/", "auth": "blueprint", "steps": []},
                {"url": "https://wrong.blueprint.io/", "auth": "blueprint", "steps": []},
                {"url": "https://www.blueprint.io/", "auth": "blueprint",
                 "steps": [{"action": "snapshot"}]},
                {"url": "https://www.blueprint.io/", "auth": "blueprint",
                 "steps": [{"action": "screenshot"}]},
                {"url": "https://www.blueprint.io/", "auth": "blueprint",
                 "steps": [{"action": "extract", "selector": "body"}]},
                {"url": "https://www.blueprint.io/", "auth": "blueprint",
                 "steps": [{"action": "blueprint_prompt", "value": "one"},
                           {"action": "blueprint_prompt", "value": "two"}]},
            ]:
                with self.assertRaises(ValueError):
                    parse_task(json.dumps(bad))

    def test_blueprint_session_secret_roundtrip_and_domain_isolation(self):
        state = {
            "cookies": [
                {"name": "session", "value": "some-session", "domain": ".blueprint.io",
                 "path": "/", "secure": True, "httpOnly": True, "sameSite": "Lax"},
                {"name": "github", "value": "do-not-transfer", "domain": ".github.com",
                 "path": "/", "secure": True, "httpOnly": True, "sameSite": "Lax"}
            ],
            "origins": [
                {"origin": "https://www.blueprint.io",
                 "localStorage": [{"name": "example", "value": "blueprint-state"}]},
                {"origin": "https://github.com",
                 "localStorage": [{"name": "bad", "value": "do-not-transfer"}]}
            ]
        }
        secret = encode_state(state)
        extracted = decode_state(secret)
        self.assertEqual(len(extracted["cookies"]), 1)
        self.assertEqual(len(extracted["origins"]), 1)
        self.assertEqual(extracted["cookies"][0]["name"], "session")
        self.assertNotIn("github", str(extracted))

    def test_blueprint_session_missing_and_empty_are_rejected(self):
        with self.assertRaises(ValueError):
            decode_state("")
        with self.assertRaises(ValueError):
            encode_state({"cookies": [], "origins": []})

    def test_robotics_lab_canvas_controls(self):
        with patch("chat_browser.runner.require_public_url"):
            task = parse_task(json.dumps({
                "url": "https://robotics-lab-app.vercel.app/#rpi4",
                "steps": [
                    {"action": "scene_inspect"},
                    {"action": "canvas_hover", "x": 0.2, "y": 0.3},
                    {"action": "canvas_click", "x": 0.5, "y": 0.5, "canvas_index": 0},
                    {"action": "canvas_drag", "x": 0.2, "y": 0.2, "to_x": 0.8, "to_y": 0.8},
                    {"action": "scene_button", "value": "Open on the workbench"},
                    {"action": "scene_button", "value": "Run"},
                    {"action": "scene_button", "value": "Wire it for me"}
                ]
            }))
        self.assertEqual(len(task["steps"]), 7)

    def test_scene_controls_restricted_to_robotics_lab(self):
        with patch("chat_browser.runner.require_public_url"):
            for url in ("https://example.com", "https://robotics-lab-app.vercel.app.evil.com",
                        "http://robotics-lab-app.vercel.app"):
                with self.assertRaises(ValueError):
                    parse_task(json.dumps({"url": url, "steps": [{"action": "canvas_click", "x": 0.5, "y": 0.5}]}))

    def test_scene_rejects_out_of_bounds_coordinates_and_actions(self):
        with patch("chat_browser.runner.require_public_url"):
            for step in [
                {"action": "canvas_click", "x": -0.1, "y": 0.5},
                {"action": "canvas_click", "x": 1.1, "y": 0.5},
                {"action": "canvas_click", "x": True, "y": 0.5},
                {"action": "canvas_drag", "x": 0.2, "y": 0.2, "to_x": 1.2, "to_y": 0.6},
                {"action": "canvas_click", "x": 0.5, "y": 0.5, "canvas_index": -1},
                {"action": "scene_button", "value": "Buy"},
            ]:
                with self.subTest(step=step), self.assertRaises(ValueError):
                    parse_task(json.dumps({"url": "https://robotics-lab-app.vercel.app",
                                          "steps": [step]}))

    def test_scene_mouse_pointer_remains_inside_viewport(self):
        rect = {"x": 50, "y": 50, "width": 200, "height": 100}
        self.assertEqual(point_in_canvas(rect, 0.5, 0.5, {"width": 500, "height": 500}), (150, 100))
        with self.assertRaises(ValueError):
            point_in_canvas(rect, 1, 1, {"width": 190, "height": 100})


if __name__ == "__main__":
    unittest.main()
