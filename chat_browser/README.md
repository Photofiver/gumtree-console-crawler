# Chat Browser via GitHub Actions

Remote Playwright browser controlled through the **same ChatGPT conversation** using the existing GitHub connector. No extra MCP server, API key or paid service is required.

## How it works

1. Ask ChatGPT to open a public website or perform browser actions.
2. ChatGPT creates a GitHub Issue with a title starting `[browser]` and a JSON body.
3. This isolated GitHub Actions workflow opens Chromium with Playwright.
4. The result is posted as a comment on that issue, which ChatGPT can read and report back in the original conversation.

Example issue body:

```json
{"url":"https://example.com","steps":[{"action":"extract","selector":"h1"}]}
```

Actions: `click`, `fill`, `press`, `select`, `check`, `uncheck`, `wait`, `screenshot`, `extract` (at most 12 steps).

## Important limits

- This controls a **remote** GitHub browser, **not the physical Android phone**.
- A separate GitHub issue opens a fresh browser session; existing logins are not preserved.
- Never include passwords or personal data: this repository and its Issues are PUBLIC.
- Browser runs are not instant. The GitHub issue and resulting logs are visible to the public.
- Only issues created by repository owner Photofiver with a `[browser]` title trigger runs.
- Does not edit or interact with BloFin, Stock-finder, or their workflows.
- On public GitHub repositories, standard GitHub-hosted Actions runners are included at no charge under GitHub's current published billing rules.
