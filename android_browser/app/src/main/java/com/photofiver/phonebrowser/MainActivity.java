package com.photofiver.phonebrowser;

import android.app.Activity;
import android.content.Intent;
import android.os.Bundle;
import android.os.Handler;
import android.os.Looper;
import android.text.InputType;
import android.view.View;
import android.webkit.WebChromeClient;
import android.webkit.WebResourceError;
import android.webkit.WebResourceRequest;
import android.webkit.WebSettings;
import android.webkit.WebView;
import android.webkit.WebViewClient;
import android.widget.Button;
import android.widget.EditText;
import android.widget.LinearLayout;
import android.widget.TextView;
import org.json.JSONArray;
import org.json.JSONObject;
import java.io.InputStream;
import java.io.OutputStream;
import java.net.HttpURLConnection;
import java.net.URI;
import java.net.URLEncoder;
import java.net.URL;
import java.nio.charset.StandardCharsets;
import java.util.concurrent.ExecutorService;
import java.util.concurrent.Executors;
import java.util.regex.Pattern;

/**
 * Minimal public-page Android browser controlled by GitHub Issues.
 * The token is never written to GitHub, embedded in web content, or stored on disk.
 * The app is a prototype; keep it open for command delivery.
 */
public class MainActivity extends Activity {
    private static final String REPO_API =
            "https://api.github.com/repos/Photofiver/gumtree-console-crawler";
    private static final Pattern DANGEROUS = Pattern.compile(
            "(?i)(^|[/\\?&=_-])(delete|remove|erase|reset|logout|signout|cancel|purchase|buy|checkout|pay|transfer|withdraw|deposit|trade|sell|order|unsubscribe)(?=$|[/\\?&=_-])");
    private final Handler ui = new Handler(Looper.getMainLooper());
    private final ExecutorService io = Executors.newSingleThreadExecutor();
    private WebView browser;
    private EditText tokenInput;
    private TextView status;
    private boolean listening = false;
    private boolean busy = false;
    private boolean navigating = false;
    private boolean initialized = false;
    private int lastSeen = 0;
    private int issueNumber = 0;
    private int stepIndex = 0;
    private String token = "";
    private JSONArray steps = new JSONArray();
    private JSONArray actions = new JSONArray();

    @Override public void onCreate(Bundle savedInstanceState) {
        super.onCreate(savedInstanceState);
        LinearLayout layout = new LinearLayout(this);
        layout.setOrientation(LinearLayout.VERTICAL);
        int p = Math.round(12f * getResources().getDisplayMetrics().density);
        layout.setPadding(p, p, p, p);

        TextView heading = new TextView(this);
        heading.setText("Chat Phone Browser · public browsing only");
        heading.setTextSize(17f);
        layout.addView(heading);

        tokenInput = new EditText(this);
        tokenInput.setSingleLine(true);
        tokenInput.setHint("GitHub fine-grained token (Issues: read/write)");
        tokenInput.setInputType(InputType.TYPE_CLASS_TEXT | InputType.TYPE_TEXT_VARIATION_PASSWORD);
        layout.addView(tokenInput);

        Button start = new Button(this);
        start.setText("Start / Stop listening");
        layout.addView(start);

        status = new TextView(this);
        status.setText("Ready. Token stays only in app memory. Never log into personal accounts here.");
        status.setTextSize(13f);
        layout.addView(status);

        browser = new WebView(this);
        WebSettings ws = browser.getSettings();
        ws.setJavaScriptEnabled(true);
        ws.setDomStorageEnabled(true);
        ws.setAllowFileAccess(false);
        ws.setAllowContentAccess(false);
        ws.setJavaScriptCanOpenWindowsAutomatically(false);
        ws.setSupportMultipleWindows(false);
        ws.setMixedContentMode(WebSettings.MIXED_CONTENT_NEVER_ALLOW);
        ws.setGeolocationEnabled(false);
        browser.setWebChromeClient(new WebChromeClient());
        browser.setWebViewClient(new WebViewClient() {
            @Override public boolean shouldOverrideUrlLoading(WebView view, WebResourceRequest req) {
                if (!req.isForMainFrame()) return false;
                if (!safeUrl(req.getUrl().toString())) {
                    show("Blocked unsafe navigation");
                    return true;
                }
                return false;
            }
            @Override public void onPageFinished(WebView view, String url) {
                if (busy && navigating) {
                    navigating = false;
                    ui.postDelayed(() -> nextStep(), 1300);
                }
            }
            @Override public void onReceivedError(WebView view, WebResourceRequest req, WebResourceError err) {
                if (busy && req.isForMainFrame())
                    fail("Page failed to load: " + err.getDescription());
            }
        });
        layout.addView(browser, new LinearLayout.LayoutParams(
                LinearLayout.LayoutParams.MATCH_PARENT, 0, 1));
        setContentView(layout);
        browser.loadUrl("https://example.com/");

        start.setOnClickListener(v -> {
            if (listening) {
                listening = false;
                stopService(new Intent(this, BrowserKeepAliveService.class));
                token = "";
                tokenInput.setText("");
                show("Stopped.");
            } else {
                token = tokenInput.getText().toString().trim();
                if (token.isEmpty()) {
                    show("Enter a fine-grained GitHub token for this repository first.");
                    return;
                }
                listening = true;
                try { startForegroundService(new Intent(this, BrowserKeepAliveService.class)); }
                catch (Exception e) { show("Background service unavailable: " + e.getMessage()); }
                initialized = false;
                lastSeen = 0;
                show("Connecting to GitHub (the app must remain running)...");
                poll();
            }
        });
    }

    private void show(String message) {
        ui.post(() -> status.setText(message));
    }

    private static boolean safeUrl(String candidate) {
        try {
            URI uri = new URI(candidate);
            if (!"https".equalsIgnoreCase(uri.getScheme()) || uri.getUserInfo() != null
                    || uri.getHost() == null || uri.getPort() != -1) return false;
            String host = uri.getHost().toLowerCase(java.util.Locale.ROOT);
            if (host.equals("localhost") || host.equals("metadata.google.internal")
                    || host.endsWith(".local") || host.endsWith(".internal")
                    || host.endsWith(".localhost")) return false;
            if (host.matches("\\d+\\.\\d+\\.\\d+\\.\\d+")
                    || host.contains(":") || DANGEROUS.matcher(
                            (uri.getRawPath() == null ? "" : uri.getRawPath())
                            + "?" + (uri.getRawQuery() == null ? "" : uri.getRawQuery())
                    ).find())
                return false;
            return true;
        } catch (Exception e) { return false; }
    }

    private String api(String method, String url, JSONObject data) throws Exception {
        HttpURLConnection connection = (HttpURLConnection) new URL(url).openConnection();
        connection.setRequestMethod(method);
        connection.setConnectTimeout(12000);
        connection.setReadTimeout(12000);
        connection.setRequestProperty("Accept", "application/vnd.github+json");
        connection.setRequestProperty("X-GitHub-Api-Version", "2022-11-28");
        connection.setRequestProperty("User-Agent", "ChatPhoneBrowser/0.1");
        connection.setRequestProperty("Authorization", "Bearer " + token);
        if (data != null) {
            connection.setDoOutput(true);
            connection.setRequestProperty("Content-Type", "application/json; charset=utf-8");
            try (OutputStream out = connection.getOutputStream()) {
                out.write(data.toString().getBytes(StandardCharsets.UTF_8));
            }
        }
        int code = connection.getResponseCode();
        try (InputStream input = code >= 400 ? connection.getErrorStream() : connection.getInputStream()) {
            String body = input == null ? "" : new String(input.readAllBytes(), StandardCharsets.UTF_8);
            if (code < 200 || code >= 300) throw new IllegalStateException(
                    "GitHub HTTP " + code + " " + body.substring(0, Math.min(180, body.length())));
            return body;
        } finally { connection.disconnect(); }
    }

    private void poll() {
        if (!listening) return;
        if (busy) { ui.postDelayed(this::poll, 8000); return; }
        io.execute(() -> {
            try {
                JSONArray issues = new JSONArray(api("GET", REPO_API
                        + "/issues?state=open&per_page=30&sort=created&direction=desc", null));
                int newest = lastSeen;
                JSONObject chosen = null;
                int chosenNum = Integer.MAX_VALUE;
                for (int i = 0; i < issues.length(); ++i) {
                    JSONObject issue = issues.getJSONObject(i);
                    if (issue.has("pull_request")) continue;
                    if (!"Photofiver".equalsIgnoreCase(
                            issue.optJSONObject("user") == null ? "" : issue.getJSONObject("user").optString("login")))
                        continue;
                    if (!issue.optString("title").startsWith("[phone-browser]")) continue;
                    int n = issue.optInt("number");
                    newest = Math.max(newest, n);
                    if (n > lastSeen && n < chosenNum) {
                        chosen = issue;
                        chosenNum = n;
                    }
                }
                final int recent = newest;
                final int selectedIssue = chosenNum;
                final JSONObject command = chosen;
                ui.post(() -> {
                    if (!listening) return;
                    if (!initialized) {
                        initialized = true;
                        lastSeen = recent; // Do not replay old commands.
                        show("Connected. Waiting for NEW [phone-browser] GitHub issues...");
                    } else if (command != null) {
                        lastSeen = selectedIssue;
                        beginTask(command);
                    }
                    ui.postDelayed(this::poll, 12000);
                });
            } catch (Exception e) {
                show("GitHub polling failed: " + e.getMessage());
                ui.postDelayed(this::poll, 16000);
            }
        });
    }

    private void beginTask(JSONObject issue) {
        issueNumber = issue.optInt("number");
        try {
            JSONObject task = new JSONObject(issue.optString("body"));
            String url = task.getString("url");
            if (!safeUrl(url)) throw new IllegalArgumentException("Only public HTTPS page URLs are supported");
            steps = task.optJSONArray("steps");
            if (steps == null) steps = new JSONArray();
            if (steps.length() > 10) throw new IllegalArgumentException("Too many steps (max 10)");
            for (int i = 0; i < steps.length(); i++) {
                JSONObject step = steps.getJSONObject(i);
                String action = step.getString("action");
                if (!action.equals("snapshot") && !action.equals("extract")
                        && !action.equals("scroll") && !action.equals("wait")
                        && !action.equals("click_text") && !action.equals("search")
                        && !action.equals("fill") && !action.equals("submit_search"))
                    throw new IllegalArgumentException("Unsupported action: " + action);
                if (action.equals("fill") || action.equals("submit_search")) {
                    String selector = step.optString("selector");
                    if (selector.isEmpty() || selector.length() > 180)
                        throw new IllegalArgumentException("Form selector must have 1-180 characters");
                    if (action.equals("fill")) {
                        String value = step.optString("value");
                        if (value.isEmpty() || value.length() > 200)
                            throw new IllegalArgumentException("Field text must have 1-200 characters");
                    }
                }
                if (action.equals("wait") && (step.optInt("ms", -1) < 0 || step.optInt("ms") > 5000))
                    throw new IllegalArgumentException("Wait must be 0-5000ms");
                if (action.equals("scroll") && (step.optInt("px", -1) < 0 || step.optInt("px") > 1600))
                    throw new IllegalArgumentException("Scroll must be 0-1600px");
                if (action.equals("click_text") && step.optString("value").trim().isEmpty())
                    throw new IllegalArgumentException("Click target missing");
                if (action.equals("search")) makeSearchUrl(step.optString("value"));
            }
            busy = true;
            navigating = true;
            stepIndex = 0;
            actions = new JSONArray();
            show("Phone opening " + url + " for issue #" + issueNumber);
            browser.loadUrl(url);
        } catch (Exception e) {
            fail("Invalid task: " + e.getMessage());
        }
    }

    private static String makeSearchUrl(String value) {
        if (value == null) throw new IllegalArgumentException("Search query missing");
        String query = value.trim();
        if (query.isEmpty() || query.length() > 160 || query.contains("\\n") || query.contains("\\r")) {
            throw new IllegalArgumentException("Search query must be between 1 and 160 characters");
        }
        String url = "https://www.google.com/search?q=" + URLEncoder.encode(query, StandardCharsets.UTF_8) + "&udm=14";
        if (!safeUrl(url)) throw new IllegalArgumentException("Unsafe search query");
        return url;
    }

    private static String jsString(String value) {
        return JSONObject.quote(value);
    }

    private static String decodeJs(String result) {
        try { return new JSONArray("[" + result + "]").optString(0, ""); }
        catch (Exception e) { return ""; }
    }

    private void nextStep() {
        if (!busy || navigating) return;
        if (stepIndex >= steps.length()) { finishWithPage(); return; }
        try {
            JSONObject step = steps.getJSONObject(stepIndex++);
            String action = step.getString("action");
            if (action.equals("search")) {
                String url = makeSearchUrl(step.getString("value"));
                actions.put("Searched: " + step.getString("value"));
                navigating = true;
                browser.loadUrl(url);
            } else if (action.equals("wait")) {
                ui.postDelayed(this::nextStep, step.optInt("ms", 800));
            } else if (action.equals("scroll")) {
                int px = step.optInt("px", 600);
                browser.evaluateJavascript("window.scrollBy(0," + px + "); 'scrolled';",
                        v -> nextStep());
            } else if (action.equals("snapshot")) {
                readSnapshot(json -> {
                    try { actions.put(new JSONObject().put("action", "snapshot").put("page", json)); }
                    catch (Exception ignored) {}
                    nextStep();
                });
            } else if (action.equals("extract")) {
                String selector = step.optString("selector");
                if (selector.isEmpty() || selector.length() > 180) { fail("Invalid selector"); return; }
                String js = "(()=>{let e=document.querySelector(" + jsString(selector)
                        + ");return e ? (e.innerText||'').slice(0,4000) : 'NOT_FOUND';})()";
                browser.evaluateJavascript(js, raw -> {
                    actions.put("extract " + selector + ": " + decodeJs(raw));
                    nextStep();
                });
            } else if (action.equals("fill")) {
                String selector = step.getString("selector");
                browser.evaluateJavascript(SafeFormScript.fill(selector, step.getString("value")), raw -> {
                    String result = decodeJs(raw);
                    if (!"FILLED".equals(result)) {
                        fail("Could not fill " + selector + ": " + result);
                        return;
                    }
                    actions.put("Filled public text field: " + selector);
                    nextStep();
                });
            } else if (action.equals("submit_search")) {
                String selector = step.getString("selector");
                navigating = true;
                browser.evaluateJavascript(SafeFormScript.submitSearch(selector), raw -> {
                    String result = decodeJs(raw);
                    if (!"SUBMITTED".equals(result)) {
                        navigating = false;
                        fail("Search form rejected " + selector + ": " + result);
                        return;
                    }
                    actions.put("Submitted safe GET search form: " + selector);
                    // The form may update in-page (without a navigation).
                    ui.postDelayed(() -> {
                        if (busy && navigating) {
                            navigating = false;
                            nextStep();
                        }
                    }, 1700);
                });
            } else if (action.equals("click_text")) {
                String target = step.optString("value").trim();
                if (target.length() > 100 || DANGEROUS.matcher(target).find()) {
                    fail("Unsafe link text");
                    return;
                }
                // Only resolve an ordinary public navigation anchor.
                // Do not execute the site's click handlers or submit a form.
                String js = "(()=>{let t=" + jsString(target.toLowerCase(java.util.Locale.ROOT))
                        + ";let a=[...document.querySelectorAll('a[href]')].find(x=>"
                        + "((x.innerText||x.getAttribute('aria-label')||'').trim().toLowerCase()).includes(t));"
                        + "return a ? a.href : '';})()";
                browser.evaluateJavascript(js, raw -> {
                    String nextUrl = decodeJs(raw);
                    if (!safeUrl(nextUrl) || DANGEROUS.matcher(nextUrl.toLowerCase()).find()) {
                        fail("No safe navigation link matching: " + target);
                        return;
                    }
                    actions.put("Followed: " + target + " -> " + nextUrl);
                    navigating = true;
                    browser.loadUrl(nextUrl);
                });
            }
        } catch (Exception e) { fail("Step failed: " + e.getMessage()); }
    }

    private interface PageConsumer { void ready(JSONObject page); }

    private void readSnapshot(PageConsumer callback) {
        browser.evaluateJavascript(PageSnapshotScript.javascript(), raw -> {
            try { callback.ready(new JSONObject(decodeJs(raw))); }
            catch (Exception e) { fail("Could not read this page: " + e.getMessage()); }
        });
    }

    private void finishWithPage() {
        readSnapshot(page -> {
            try {
                String title = page.optString("title").toLowerCase(java.util.Locale.ROOT);
                String text = page.optString("text").toLowerCase(java.util.Locale.ROOT);
                boolean blocked = title.contains("error page | ebay")
                        || text.contains("something went wrong on our end")
                        || page.optString("url").contains("google.com/sorry/")
                        || text.contains("unusual traffic from your computer network")
                        || text.contains("captcha") && text.contains("robot")
                        || title.contains("access denied");
                boolean googleSearch = page.optString("url").startsWith("https://www.google.com/search?");
                boolean missingLinks = googleSearch
                        && page.optJSONArray("links") != null
                        && page.optJSONArray("links").length() == 0;
                JSONObject out = new JSONObject().put("ok", !blocked && !missingLinks)
                        .put("page", page).put("actions", actions);
                if (blocked) out.put("error", "Website returned a block/error page");
                else if (missingLinks)
                    out.put("error", "Google showed search text but no usable result links");
                report(out);
            } catch (Exception e) { fail("Result error: " + e.getMessage()); }
        });
    }

    private void fail(String reason) {
        try { report(new JSONObject().put("ok", false).put("error", reason)); }
        catch (Exception e) { show(reason); busy = false; }
    }

    private void report(JSONObject result) {
        if (!busy) busy = true; // Invalid-task errors also need a comment.
        final int number = issueNumber;
        final String body = "Phone browser result (public pages only):\n\n```json\n"
                + result.toString().substring(0, Math.min(20000, result.toString().length()))
                + "\n```";
        io.execute(() -> {
            try {
                api("POST", REPO_API + "/issues/" + number + "/comments",
                        new JSONObject().put("body", body));
                show("Issue #" + number + " complete: "
                        + (result.optBoolean("ok") ? "page read" : result.optString("error")));
            } catch (Exception e) {
                show("Failed posting issue #" + number + " result: " + e.getMessage());
            } finally { ui.post(() -> busy = false); }
        });
    }

    @Override protected void onDestroy() {
        listening = false;
        stopService(new Intent(this, BrowserKeepAliveService.class));
        io.shutdownNow();
        if (browser != null) browser.destroy();
        super.onDestroy();
    }
}
