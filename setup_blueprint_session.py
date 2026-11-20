"""One-time local Blueprint sign-in and secure GitHub Actions Secret upload.

Run on your own computer. No credentials or browser state are sent to chat,
public GitHub issues, workflow artifacts or repository content.
Requires: pip install playwright; python -m playwright install chromium;
GitHub CLI (gh) logged into the Photofiver account.
"""
import shutil
import subprocess
import sys

from playwright.sync_api import sync_playwright
from chat_browser.blueprint_session import SECRET_NAME, encode_state

REPO = "Photofiver/gumtree-console-crawler"
HOME = "https://www.blueprint.io/"


def main():
    if shutil.which("gh") is None:
        print("GitHub CLI (gh) is required. Install it and run 'gh auth login' first.")
        return 1
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(headless=False)
        try:
            context = browser.new_context()
            page = context.new_page()
            page.goto(HOME, wait_until="domcontentloaded", timeout=45000)
            print("Sign in to Blueprint in the opened browser, using GitHub.")
            input("After Blueprint shows your signed-in home screen, press Enter here: ")
            page.goto(HOME, wait_until="domcontentloaded", timeout=45000)
            page.wait_for_timeout(1500)
            if page.get_by_role("button", name="SIGN IN", exact=True).count():
                print("Blueprint still shows SIGN IN; session was not captured.")
                return 2
            state = context.storage_state(indexed_db=True)
            encoded = encode_state(state)
        finally:
            browser.close()

    # Pass the encoded state via standard input (not a command-line argument).
    # GitHub CLI encrypts it before uploading it as an Actions Secret.
    try:
        subprocess.run(
            ["gh", "secret", "set", SECRET_NAME, "--repo", REPO],
            input=encoded + "\n",
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            check=True,
        )
    except subprocess.CalledProcessError:
        print("Could not upload secret; verify gh auth status and repository access.")
        return 3
    print("Blueprint session installed as an encrypted GitHub Actions Secret.")
    print("Never paste session state or cookies into public GitHub Issues.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
