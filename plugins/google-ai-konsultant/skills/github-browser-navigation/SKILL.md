---
name: github-browser-navigation
description: 'Use when Google AI Konsultant is selected and the user wants to open, click through, inspect, or screenshot a public interactive website using the existing GitHub Actions Playwright browser.'
---

# Google AI Konsultant — GitHub browser bridge

## Purpose

When the user explicitly asks Google AI Konsultant to **enter a site, click through the internet, inspect a dynamic page, test an interactive UI, or verify that a webpage opens**, use the existing browser runner in `Photofiver/gumtree-console-crawler` instead of assuming that extracting text from a URL proves interactive access. The runner already exists at `chat_browser/runner.py`; GitHub Actions workflow `.github/workflows/chat-browser.yml` is triggered by an **owner-created** GitHub issue whose title starts `[browser]`. Do not create a replacement browser or pretend that the Google AI review workflow itself controls arbitrary websites.

This skill complements `google-ai-second-opinion`, not replaces it. A `[browser]` task returns observed page behavior; `[consult]` independently requests Google AI critique of an answer. They are separate processes, and neither is evidence that the other ran.

## Invocation through the connected GitHub app

1. Locate connected GitHub actions with `ALL_TOOLS`, notably `mcp__GitHub__create_issue`, `mcp__GitHub__fetch_issue_comments`, and `mcp__GitHub__fetch_issue`. Never claim browser control without invoking the GitHub tools.
2. For a public non-sensitive URL, create an issue in `Photofiver/gumtree-console-crawler` with title `[browser] <short task title>` and a JSON **string** body such as `{"url":"https://robotics-lab-app.vercel.app/#rpi4","steps":[{"action":"snapshot"},{"action":"screenshot"}]}`. The body must be raw JSON (not commentary). Never put credentials, browser cookies, private pages, tokens, personal data, or unredacted private queries in public issues. If the request requires them, explain that this public workflow cannot be used safely.
3. Allowed actions defined by the runner include `snapshot`, `inspect`, `extract` (requires CSS `selector`), `screenshot`, `scroll` (max 1600 px), `wait` (max 5000 ms), `wait_for` (CSS `selector`, max 12000 ms), `click_text` (visible text, **safe navigation only**), `click` (CSS selector, **safe navigation only**), `dismiss_cookies`, `fill` and `press` (search fields only). Maximum 12 steps. Example link navigation: `{"url":"https://example.com","steps":[{"action":"snapshot"},{"action":"click_text","value":"Learn more"},{"action":"snapshot"}]}`. Do not invent unsupported actions; no shell, arbitrary JS, purchases, form submissions, account changes, or unrestricted mouse clicks are supported. Avoid guessing selectors: use `snapshot`/`inspect` first if uncertain.
4. Read comments on the **same issue** until the runner returns its JSON result in the `github-actions[bot]` comment. `ok:true` is necessary but not proof that desired UI action succeeded; inspect the `actions`, `url`, `text`, and artifact status. If `ok:false`, report the actual `error`. If no comment arrives or the run times out, report `NIEPOTWIERDZONE`, with the issue link, not successful browser access. Recheck when tool access and user interaction time permit; never promise future work without a scheduled tool.
5. For multi-page browsing, choose safe observed links from the last result. Issue another `[browser]` task with the observed URL as the starting URL if necessary. Each issue launches a fresh browser; it does **not** share live session state with the prior issue or the user's browser/phone.
6. If Google AI evaluation is additionally requested, send the **actual observed result** (not invented HTML or screenshot analysis) as a draft into a separate `[consult]` issue per `google-ai-second-opinion` skill, wait for and validate the corresponding receipt. Report distinct GitHub issue links and separate verified status for browser and AI.

## Non-negotiable limits

- The GitHub runner is remote Playwright Chromium, not ChatGPT's live Cloud Browser and not the user's Android or laptop browser. It cannot click their device screen or inherit their logins.
- `snapshot` and text extraction are not proof that a three.js/WebGL canvas rendered correctly. For Robotics Lab, dedicated `canvas_hover`, `canvas_click`, `canvas_drag`, `scene_button` and `scene_inspect` commands dispatch local browser events. An event-dispatched result is NOT proof that the desired 3D interaction succeeded; examine the resulting scene, status and screenshots.
- Some sites, including Google Search, may challenge datacenter traffic. Google AI Mode verification uses the separate Android/WebView workflow, which may itself fail. Do not claim unrestricted Google access.
- Browser results are collected via GitHub issue comments and screenshots via short-lived Actions artifacts; ensure they come from the expected workflow. Do not present a public GitHub Issue as private.
- Plugin instructions alone cannot force every ChatGPT turn to call tools. If tools are unavailable, report that limitation clearly.

## Robotics Lab 3D input (site-restricted)

GitHub runner supports mouse control **only** on `https://robotics-lab-app.vercel.app` and does not provide arbitrary universal webpage writing. These are ephemeral, public simulator actions, not access to the user's device:

- `scene_inspect`: lists visible `canvas` geometry, indexes, viewport dimensions, and simulator button text.
- `canvas_hover` / `canvas_click`: require `x` and `y` normalized from 0 to 1 inside the selected canvas. `canvas_index` defaults to 0.
- `canvas_drag`: requires `x`, `y`, `to_x`, `to_y` (all normalized 0..1). Uses true mouse down, smooth movement, then mouse up. The runner rejects coordinates outside visible canvas/viewport.
- `scene_button`: clicks strictly known Robotics Lab control labels (e.g. `Open on the workbench`, `Free build`, `Run`, `Stop`, `Reset`) after exact accessible-name matching; it cannot click arbitrary buttons elsewhere.

Issue example:

```json
{"url":"https://robotics-lab-app.vercel.app/#rpi4","steps":[{"action":"scene_inspect"},{"action":"scene_button","value":"Open on the workbench"},{"action":"scene_inspect"},{"action":"canvas_hover","canvas_index":0,"x":0.5,"y":0.5},{"action":"canvas_drag","canvas_index":0,"x":0.4,"y":0.4,"to_x":0.6,"to_y":0.6},{"action":"screenshot"}]}
```

Important: coordinates must be chosen after reading current canvas geometry and screenshot, not guessed as evidence. To connect wires, obtain an observed pin placement before trying `canvas_click` on both endpoints (or `canvas_drag` if the application requires dragging). Always distinguish simulated pointer activity from a confirmed connected circuit. The GitHub task is single-session within an issue; a new issue starts a new browser with no saved simulation state. Never claim a persisted project unless the site provides and confirms saving.

## Lazy-mounted workbench controls

After `Open on the workbench`, the local simulator mounts controls asynchronously. The runner retries allowlisted `scene_button` labels for up to 8 seconds. On this public demo it permits `Wire it for me`, `Run`, `Remove wires`, and `Clear the bench`; the following is a supported task syntax:

```json
{"url":"https://robotics-lab-app.vercel.app/#rpi4","steps":[{"action":"scene_button","value":"Open on the workbench"},{"action":"scene_button","value":"Wire it for me"},{"action":"scene_button","value":"Run"},{"action":"scene_inspect"}]}
```

Never confuse a sent click with a connected or running circuit; verify visible result. A task keeps one browser session only until the issue workflow finishes; a later issue starts a new fresh simulator. Do not claim that a Raspberry Pi project was wired when the bench actually uses an Arduino demo.
