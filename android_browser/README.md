# Android Phone Browser (experimental)

An Android WebView that opens public pages **on the phone**, not on GitHub-hosted servers. It retrieves **new** `[phone-browser]` commands posted by GitHub user `Photofiver` to `Photofiver/gumtree-console-crawler` and posts results as comments on the same issue. This keeps control in the original ChatGPT conversation using the existing GitHub connector.

## Build and install

- The separate GitHub Actions workflow **Build Android phone browser** compiles an Android debug APK and publishes it as a workflow artifact. It is not an app-store release and is **not yet verified on a real phone**.
- Open the workflow run's **Artifacts** and download `phone-browser-debug-apk`, then install the APK on Android (Android asks to permit installation from that source).
- Create a [fine-grained GitHub token](https://github.com/settings/personal-access-tokens/new), limiting access **only** to `Photofiver/gumtree-console-crawler`, with **Issues: Read and write**. Do not include this token in this chat or a GitHub issue.
- Open the Android app, paste the token, select **Start listening**, and wait for `Connected`. The token remains in app memory and is wiped when listening stops. It is **not persisted**.
- Ask ChatGPT to browse a public web page on your phone; it can create a new issue with a title starting `[phone-browser]` and a body as shown below. The phone app polls for new commands every ~12 seconds and returns a result as an issue comment.

```json
{
  "url": "https://simple.wikipedia.org/wiki/Belfast",
  "steps": [
    {"action": "snapshot"},
    {"action": "click_text", "value": "Northern Ireland"},
    {"action": "snapshot"}
  ]
}
```

Supported actions are **snapshot** (page text/links), **extract** (CSS selector), **click_text** (follows ordinary HTTPS hyperlinks only, never triggers onclick JavaScript), **scroll** (0–1600px), and **wait** (0–5000ms), max 10 steps. The app blocks HTTP/credentials/private IP literals and many dangerous link paths. It never issues website POST actions by user command.

## Important limitations and safety

- **Keep the app running.** Starting listening creates an Android foreground service with an ongoing notification so switching to ChatGPT should keep the app process active. Android can still stop or restrict it (especially after force-stop, battery management, or service time limits); it is not guaranteed to run indefinitely. Stop listening when finished.
- The phone browser is a new WebView, **not your existing Chrome profile**; cookies, logins, extensions, bookmarks, and sessions are not shared. Using the phone's network may avoid some datacenter-IP restrictions, **but there is no guarantee of access to eBay or every site**.
- The foreground service is for a short, user-initiated browsing session, not permanent monitoring. Android 15+ limits some service types to a daily runtime budget.\n- This is **not inherently safe on every site**. A third-party website can send its own HTTP requests via JavaScript; GET navigation can also have side effects on improperly implemented sites. Never open authenticated or private sessions with this prototype.
- **All commands and page extracts are PUBLIC** GitHub issue content. Never use it for confidential, personal, financial, or login pages.
- The token has **Issues read/write** only, and is used only for GitHub API calls. Prefer a short expiration and revoke when finished.
- Only issues actually created by the repository owner `Photofiver` are accepted, and **old issues are not replayed** on startup. Open a new issue after the phone shows `Connected`.
- This code is isolated in `android_browser` and `.github/workflows/phone-browser.yml`; it does **not** modify the BloFin bot, Stock-finder, or their workflows.
