# Chat Browser via GitHub Actions

Remote Playwright browser controlled through the **same ChatGPT conversation** using the existing GitHub connector. No extra MCP server, API key or paid service is required.

## How it works

1. Ask ChatGPT to open a public website, search it or click safe navigation controls.
2. ChatGPT creates a GitHub Issue with a title starting `[browser]` and a JSON body.
3. This isolated GitHub Actions workflow opens Chromium with Playwright.
4. The result is posted as a comment on that issue, which ChatGPT can read and report back in the original conversation.

Example issue body:

```json
{"url":"https://example.com","steps":[{"action":"extract","selector":"h1"}]}
```

Read-only actions: `click` (ordinary links and explicitly safe navigation buttons), `fill` (search fields only), `press` (Enter in search fields only), `wait`, `screenshot`, `extract` (at most 12 steps). `select`, `check`, `uncheck` and form-editing are disabled.

## Read-only safety mode

- HTTP methods other than **GET/HEAD** are blocked, including POST, PUT, PATCH and DELETE.
- Known destructive URL patterns (delete, remove, logout, withdraw, pay, order, etc.) are blocked even for GET.
- Only links and buttons clearly used for browsing (search, more, next, open, filter, etc.) may be clicked.
- Only search boxes can receive text. Sending forms, changing account settings and changing checkboxes are not supported.
- Every run uses a disposable browser session with downloads disabled.
- **No program can promise that GET navigation on an untrusted site is always side-effect-free.** Some websites incorrectly perform changes through GET endpoints or JavaScript, and the browser can still make ordinary read requests to servers. Only use this module to read public content.
- On all sites use sensible frequency and comply with site terms. No private logins.

## Important limits

- This controls a **remote** GitHub browser, **not the physical Android phone**.
- A separate GitHub issue opens a fresh browser session; existing logins are not preserved.
- Never include passwords or personal data: this repository and its Issues are PUBLIC.
- Browser runs are not instant. The GitHub issue and resulting logs are visible to the public.
- Only issues created by repository owner Photofiver with a `[browser]` title trigger runs.
- Does not edit or interact with BloFin, Stock-finder, or their workflows.
- On public GitHub repositories, standard GitHub-hosted Actions runners are included at no charge under GitHub's current published billing rules.
