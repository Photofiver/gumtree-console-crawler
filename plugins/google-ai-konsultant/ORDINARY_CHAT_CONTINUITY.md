# Optional ordinary ChatGPT continuity (without Work and OpenAI API key)

This is an EXPERIMENTAL LOCAL BRIDGE, not a ChatGPT platform feature and not a
way to remove subscription limits. It sends a NEW USER MESSAGE into an
existing ordinary ChatGPT conversation when Google AI responds on GitHub.
It does not reactivate a previously completed model turn.

## How it works

1. GitHub workflow posts an authenticated Konsultant/2 review receipt
   into an owner-created [consult] issue.
2. local_chat_continuity.py polls the exact issue, verifies its SHA256
   and the bot identity, and forwards the feedback through the separate
   tritao/chatgpt-web CLI to the existing conversation.
3. ChatGPT prepares the corrected full JSON packet. The local controller
   validates requirements, then creates a new [consult] issue on GitHub.
4. Repeat for the child issue after Google AI has independently reviewed it.
   A verified solution ends the chain. Technical or evidence blockers are
   reported, not disguised as successful results.
5. An uncertain submission is NEVER blindly resent; the original chat
   must be inspected before a safe retry.

## Requirements and installation

- A computer and a local signed-in Chrome that stay running.
- Linux/macOS, Python 3.10+, Node.js 22+, and installed CLI:
  https://github.com/tritao/chatgpt-web .
  The CLI is NOT CONFIRMED to run natively on Windows. Windows would need
  a working Linux environment with Chrome; this is not turnkey.
- Existing ordinary conversation ID from a URL like
  https://chatgpt.com/c/CONVERSATION_ID .
- Local GitHub authorization capable of creating issues in this repo.
  Keep credentials on the computer, NEVER in the public repository.

Follow the upstream project's README to perform the one-time local
Chrome login and authentication and confirm that the CLI can read your
existing conversation.

Run locally (replace placeholders with real values):

    export GH_TOKEN="$(gh auth token)"
    python3 plugins/google-ai-konsultant/local_chat_continuity.py \
      --root-issue INITIAL_CONSULT_ISSUE_NUMBER \
      --conversation-id CONVERSATION_ID \
      --chatgpt-web /absolute/path/to/chatgpt-web/run

To run one check and stop, append --once.
Default private state: ~/.local/state/google-ai-konsultant/continuity.json
Use a different --state for each independent issue chain.

## Limits

The external CLI drives undocumented ChatGPT web behaviour. Browser login,
website changes, rate limits, approvals and provider failures may interrupt
this process. GitHub Actions alone cannot maintain a local Chrome session.

This method may be incompatible with OpenAI's terms regarding automated
extraction; inspect the applicable terms before using. Do not attempt to
circumvent protective measures, challenges or rate limits.

Unit tests only verify local logic using simulated tools. They DO NOT prove
the user's browser login works, that ChatGPT actually sends a message, or
that a complete solution was independently verified.

References:
https://github.com/tritao/chatgpt-web
https://openai.com/en-GB/policies/eu-terms-of-use/
https://learn.chatgpt.com/docs/non-interactive-mode
