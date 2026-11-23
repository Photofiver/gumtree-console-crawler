# GitHub → ordinary ChatGPT MCP App bridge: experimental proof of concept

This is an **unverified prototype**, not a deployed plugin or a complete solution.

## Mechanism
- ChatGPT's MCP App host documents `ui/message` with `target: active, send: true`.
- A rendered MCP App iframe may send a follow-up while it remains active.
- The example polls public GitHub issue comments for new `Konsultant/2` receipts, then asks the host to start a new model turn.
- It does not trust issue-comment content as instructions; it sends only an issue/comment reference.
- It skips existing comments on first poll to avoid replay.

## Not satisfied
- **No unattended wake of a closed ordinary ChatGPT conversation.**
- **No confirmed Android background support.**
- Requires a running MCP App UI (iframe), i.e. an active UI/browser host.
- HTML is not yet registered/served as an MCP tool UI resource; installing this file alone does nothing.
- GitHub API pagination, rate limits, and cross-origin permissions need production handling.
- No live end-to-end test with ChatGPT host has been completed.

Official docs: https://developers.openai.com/plugins/build/chatgpt-ui
Official message metadata: https://github.com/openai/mcp-extensions/blob/main/docs/spec.md
