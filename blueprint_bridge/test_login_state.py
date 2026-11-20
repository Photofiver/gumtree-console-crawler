import unittest

from blueprint_bridge.server import login_prompt_visible


class BlueprintSignInTests(unittest.TestCase):
    def test_signin_text_visible_on_public_home(self):
        self.assertTrue(login_prompt_visible("ABOUT US\nPRICING\nSIGN IN\nNEED AN IDEA?"))
        self.assertTrue(login_prompt_visible("Sign in\nCONTINUE WITH GITHUB\nCONTINUE"))
        self.assertTrue(login_prompt_visible("MAKE ANY IDEA REAL\nCONTINUE WITH GOOGLE\nOR"))

    def test_no_false_login_prompt_from_logged_in_project(self):
        self.assertFalse(login_prompt_visible("MY PROJECTS\nPhotofiver\nCreate new project"))
        self.assertFalse(login_prompt_visible("A 9V LED lamp created, press to assign"))


if __name__ == "__main__":
    unittest.main()
