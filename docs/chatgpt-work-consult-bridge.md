# ChatGPT Work ↔ Google AI consultation feed

**Keep this pull request OPEN; do not merge.** It is a durable GitHub
pull-request comment feed, not a code change intended for `main`.

The GitHub workflow `.github/workflows/google-ai-consult-continuity.yml`
posts `GOOGLE_AI_REVIEW_FOR_CHATGPT_WORK` comments here after an incomplete
`[consult]` review. ChatGPT Work supports event-triggered GitHub PR comments
on eligible plans. This does **not** awaken an arbitrary closed ChatGPT chat.

## One-time setup in ChatGPT Work

1. Connect the GitHub repository `Photofiver/gumtree-console-crawler`.
2. Create an **event-triggered task** for **new comments on this exact PR**.
   Leave the author filter broad enough to include `github-actions[bot]`.
3. Use this task prompt:

> On a new PR comment prefixed `GOOGLE_AI_REVIEW_FOR_CHATGPT_WORK`,
> open the referenced `[consult]` issue, retrieve its original JSON and
> the authenticated `Konsultant/2` receipt. Independently research and
> verify every outstanding requirement; do not rely on an unverified
> model-generated claim. For `DO POPRAWY` or `NIEPOTWIERDZONE`, correct
> the complete draft yourself and create a new `[consult]` issue
> with `parent_issue` equal to the referenced issue number. Preserve all
> requirements; never convert unknown claims to proven, remove budget
> constraints or invent product safety, availability or prices. Inspect
> existing child issues to avoid duplicate reruns. If the condition is
> demonstrably impossible, report the exact limiting constraint rather
> than claiming a solution. If external tools or approvals block progress,
> report the blocker transparently. A fresh Google AI review of the new
> issue produces a new PR event for the next cycle. Never announce
> success without `POTWIERDZONE` plus independent verification.

The workflow only **signals** the event and writes an audit trail; it
does not call an OpenAI API or charge API tokens. ChatGPT Work may use
the user's plan allowance, may pause for approval, and cannot guarantee
unlimited autonomous runs. Only authenticated GitHub bot receipts
matching the exact issue body SHA are forwarded.

References:
- https://help.openai.com/en/articles/10291617-scheduled-tasks-in-chatgpt
- https://learn.chatgpt.com/docs/automations
