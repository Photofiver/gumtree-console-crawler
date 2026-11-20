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

Read-only actions: `click` (CSS selector), `click_text` (search visible safe links/buttons by label), `inspect` (list available links/buttons), `fill` (search fields only), `press` (Enter in search fields only), `wait`, `screenshot`, `extract` (at most 12 steps). `select`, `check`, `uncheck` and form-editing are disabled.

## Read-only safety mode

- HTTP methods other than **GET/HEAD** are blocked, including POST, PUT, PATCH and DELETE.
- Known destructive URL patterns (delete, remove, logout, withdraw, pay, order, etc.) are blocked even for GET.
- Only links and buttons clearly used for browsing (search, more, next, open, filter, etc.) may be clicked. Use `click_text` if a site's CSS paths have changed; use `inspect` to discover links. The runner reports site error pages explicitly rather than claiming the task succeeded.
- Only search boxes can receive text. Sending forms, changing account settings and changing checkboxes are not supported.
- Every run uses a disposable browser session with downloads disabled.
- **No program can promise that GET navigation on an untrusted site is always side-effect-free.** Some websites incorrectly perform changes through GET endpoints or JavaScript, and the browser can still make ordinary read requests to servers. Only use this module to read public content.
- On all sites use sensible frequency and comply with site terms. No private logins.

## eBay UK compatibility

- Tested both `ebay.co.uk/sch/i.html` and direct item URLs from GitHub Actions: eBay returns **"Error Page | eBay"**, not listings.
- Google search from the same runner shows an **unusual automated traffic** challenge.
- The Open RSS eBay feed requires a free email token, so it does not satisfy no-registration usage.
- The module now returns these as explicit failures instead of claiming success; this **does not enable eBay access**.
- eBay's official Browse API can retrieve live item summaries but requires developer credentials, and is not configured in this public repository. Never put secrets in GitHub Issues.

## Compatibility improvements from open-source projects (Nov 2026)

The runner takes ideas from public docs of Obscura (snapshot + wait + network diagnostics), Browsentic (semantic/accessible elements), and Playwright (role-based, auto-waiting locators). The current read-only runner supports:
- `snapshot` — show headings, links, buttons and search fields, including same-origin or cross-origin frames, without submitting anything
- `click_text` — find safe navigation controls by their accessible label, including iframe controls
- `wait_for` — wait for JavaScript-loaded content to appear without a blind delay (max 12 seconds)
- `scroll` — move down up to 1600 pixels to reveal lazy-loaded content
- `inspect` — lightweight frame-by-frame link and button inventory

```json
{"url":"https://simple.wikipedia.org/wiki/Belfast","steps":[{"action":"snapshot"},{"action":"click_text","value":"Northern Ireland"}]}
```

Important architectural lesson: Obscura is a replacement engine with browser fingerprint tooling, but Github Actions still sends traffic from a datacenter. Browsentic runs in a user's genuine browser; Agent for Android runs a WebView on the phone; Android Remote Control MCP controls the phone through a local service. Those are **different execution locations** and do not grant this GitHub-hosted runner the user's network/browser identity. None guarantees access to every website.

References:
- https://github.com/h4ckf0r0day/obscura
- https://github.com/imshaikot/browsentic
- https://github.com/Past-da-king/agent
- https://github.com/danielealbano/android-remote-control-mcp
- https://playwright.dev/docs/locators

## Important limits

- This controls a **remote** GitHub browser, **not the physical Android phone**.
- A separate GitHub issue opens a fresh browser session; existing logins are not preserved.
- Never include passwords or personal data: this repository and its Issues are PUBLIC.
- Browser runs are not instant. The GitHub issue and resulting logs are visible to the public.
- Only issues created by repository owner Photofiver with a `[browser]` title trigger runs.
- Does not edit or interact with BloFin, Stock-finder, or their workflows.
- On public GitHub repositories, standard GitHub-hosted Actions runners are included at no charge under GitHub's current published billing rules.


## Blueprint.io: optional authenticated project creation

The GitHub browser has a narrowly scoped `"auth": "blueprint"` mode. It reads an **encrypted GitHub Actions Secret** called `BLUEPRINT_STORAGE_STATE_ZB64`. It is **not** your ChatGPT GitHub connector token or the login in Brave on your Android phone. Those sessions cannot be copied automatically.

### One-time connection from your own computer

1. Install Python 3, the official GitHub CLI (`gh`), and Playwright: `python -m pip install playwright` then `python -m playwright install chromium`.
2. Authenticate GitHub CLI once with `gh auth login` (the repo owner must approve on GitHub).
3. Download/clone this repository and run `python setup_blueprint_session.py` from its root.
4. A local Chromium browser opens Blueprint. Sign in there with GitHub and complete onboarding; then press Enter in the terminal. The script uploads the Blueprint-only browser session **directly to GitHub Actions Secrets** using encrypted CLI transport. It never prints or commits session tokens, creates public issues, or writes a session file.

The resulting secret can be checked (but not read back) under [Actions repository secrets](https://github.com/Photofiver/gumtree-console-crawler/settings/secrets/actions).

**Security:** The session is as sensitive as a password. Do not paste it, email a cookie, copy it to an Issue or commit it to this public repository. GitHub may eventually expire the session. If so, rerun the local setup. Not all websites support Playwright storage-state restoration; IndexedDB is captured but sessionStorage is not.

### Using the session

Create a GitHub Issue with the exact title prefix `[browser]` and an innocuous, non-secret JSON body such as:

```json
{"url":"https://www.blueprint.io/","auth":"blueprint","steps":[{"action":"blueprint_prompt","value":"Build a simple 9V red LED lamp with a 470-ohm resistor and button."}]}
```

Authenticated mode accepts only one Blueprint prompt plus optional waits. It **does not publicly post** the account's page text, cookies, links, DOM or screenshot. The issue comment reports only whether login was available and whether submission was attempted — **not** whether Blueprint completed or saved the design. Verify any generated project in your account. The public Issue body includes the project idea itself, so do not submit confidential designs.

If the secret is missing, authentication cannot succeed; a GitHub OAuth approval on your **phone** does not log in the **GitHub Actions** browser.
