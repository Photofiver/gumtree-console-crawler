package com.photofiver.phonebrowser;

import android.app.Activity;
import android.os.Bundle;
import android.os.Handler;
import android.os.Looper;
import android.net.Uri;
import android.webkit.WebResourceError;
import android.webkit.WebResourceRequest;
import android.webkit.WebSettings;
import android.webkit.WebView;
import android.webkit.WebViewClient;
import org.json.JSONArray;
import org.json.JSONObject;
import java.io.File;
import java.io.FileInputStream;
import java.io.FileOutputStream;
import java.net.URLEncoder;
import java.nio.charset.StandardCharsets;

/**
 * One long-lived Android WebView for Google AI Mode.
 *
 * GitHub's warm Python worker pushes numbered questions to the app's external
 * files directory. This Activity keeps the SAME WebView open across all
 * questions, navigates it to Google's AI Mode, and captures the live DOM as
 * soon as Google's readiness marker appears. No instrumentation launch and no
 * arbitrary fixed 18-second wait per query.
 *
 * No GitHub token, user cookies, or secrets are passed to page Javascript.
 */
public final class GoogleAiWarmActivity extends Activity {
    private static final long POLL_MS = 350;
    private static final long MAX_ANSWER_MS = 45000;
    private static final String AI_URL = "https://www.google.com/search?udm=50&hl=pl";
    private static final String SNAPSHOT_JS =
        "(()=>JSON.stringify({"
        + "url:location.href,title:document.title,"
        + "text:(document.body?document.body.innerText:'').slice(0,85000),"
        + "sourceLinks:[...document.querySelectorAll('a[href]')].filter(a=>"
        + "{try{let u=new URL(a.href);return !u.hostname.endsWith('google.com')"
        + "&&/^https?:$/.test(u.protocol)}catch(e){return false}}).slice(0,30)"
        + ".map(a=>({text:(a.innerText||a.getAttribute('aria-label')||'').slice(0,120),url:a.href}))"
        + "}))()";

    private final Handler handler = new Handler(Looper.getMainLooper());
    private WebView browser;
    private File commandFile;
    private File answerFile;
    private File readyFile;
    private String lastId = "";
    private String activeId = "";
    private String activeQuestion = "";
    private String activeUrl = "";
    private long startedAtMs = 0L;
    private boolean pageFinished = false;
    private boolean snapshotPending = false;
    private boolean prewarmReady = false;

    @Override public void onCreate(Bundle state) {
        super.onCreate(state);
        File folder = getExternalFilesDir(null);
        if (folder == null) throw new IllegalStateException("External app files unavailable");
        commandFile = new File(folder, "google-ai-warm-command.json");
        answerFile = new File(folder, "google-ai-warm-result.json");
        readyFile = new File(folder, "google-ai-warm-ready.json");

        browser = new WebView(this);
        WebSettings settings = browser.getSettings();
        settings.setJavaScriptEnabled(true);
        settings.setDomStorageEnabled(true);
        settings.setAllowFileAccess(false);
        settings.setAllowContentAccess(false);
        settings.setJavaScriptCanOpenWindowsAutomatically(false);
        settings.setSupportMultipleWindows(false);
        settings.setMixedContentMode(WebSettings.MIXED_CONTENT_NEVER_ALLOW);
        settings.setGeolocationEnabled(false);
        browser.setWebViewClient(new WebViewClient() {
            @Override public void onPageFinished(WebView view, String url) {
                if (activeId.isEmpty()) {
                    if (!prewarmReady && isGoogleUrl(url)) {
                        prewarmReady = true;
                        try {
                            JSONObject r = new JSONObject();
                            r.put("status", "ready");
                            r.put("url", url);
                            r.put("readyAtEpochMs", System.currentTimeMillis());
                            writeJson(readyFile, r);
                        } catch (Exception ignored) {}
                    }
                } else if (matchesActiveQuery(url)) {
                    pageFinished = true;
                }
            }
            @Override public void onReceivedError(WebView view, WebResourceRequest req,
                    WebResourceError error) {
                if (req.isForMainFrame() && !activeId.isEmpty()) {
                    complete(new JSONObject(), false, "main_frame_error");
                }
            }
            @Override public boolean shouldOverrideUrlLoading(WebView view, WebResourceRequest req) {
                return req.isForMainFrame() && !isGoogleUrl(req.getUrl().toString());
            }
        });
        setContentView(browser);
        // Keep Google's AI Mode loaded while idle. A new question uses the
        // SAME WebView; it never relaunches the activity or instrumentation.
        browser.loadUrl(AI_URL);
        handler.postDelayed(this::tick, POLL_MS);
    }

    private static boolean isGoogleUrl(String raw) {
        try {
            Uri uri = Uri.parse(raw);
            String host = uri.getHost();
            return "https".equalsIgnoreCase(uri.getScheme()) &&
                    host != null && (host.equals("google.com") || host.endsWith(".google.com"));
        } catch (Exception e) {
            return false;
        }
    }

    private boolean matchesActiveQuery(String url) {
        try {
            if (!isGoogleUrl(url)) return false;
            Uri uri = Uri.parse(url);
            return activeQuestion.equals(uri.getQueryParameter("q")) &&
                    "50".equals(uri.getQueryParameter("udm"));
        } catch (Exception e) { return false; }
    }

    private static JSONObject readJson(File file) throws Exception {
        if (!file.exists() || file.length() > 16000L) return null;
        try (FileInputStream stream = new FileInputStream(file)) {
            byte[] bytes = stream.readAllBytes();
            return new JSONObject(new String(bytes, StandardCharsets.UTF_8));
        }
    }

    private static void writeJson(File target, JSONObject data) throws Exception {
        File tmp = new File(target.getParentFile(), target.getName() + ".partial");
        try (FileOutputStream stream = new FileOutputStream(tmp)) {
            stream.write(data.toString().getBytes(StandardCharsets.UTF_8));
            stream.getFD().sync();
        }
        if (!tmp.renameTo(target)) {
            // android ext-files rename normally replaces an existing file.
            if (target.exists() && target.delete() && tmp.renameTo(target)) return;
            throw new IllegalStateException("Could not publish warm Google AI result");
        }
    }

    private void tick() {
        try {
            if (activeId.isEmpty()) {
                JSONObject request = readJson(commandFile);
                if (request != null) {
                    String id = request.optString("id");
                    String question = request.optString("question");
                    if (!id.isEmpty() && !id.equals(lastId) &&
                            !question.trim().isEmpty() &&
                            question.getBytes(StandardCharsets.UTF_8).length <= 2000) {
                        lastId = id;
                        activeId = id;
                        activeQuestion = question;
                        activeUrl = AI_URL + "&q=" + URLEncoder.encode(question, "UTF-8");
                        startedAtMs = android.os.SystemClock.elapsedRealtime();
                        pageFinished = false;
                        snapshotPending = false;
                        browser.loadUrl(activeUrl);
                    }
                }
            } else if (android.os.SystemClock.elapsedRealtime() - startedAtMs > MAX_ANSWER_MS) {
                complete(new JSONObject(), false, "answer_timeout");
            } else if (pageFinished && !snapshotPending && matchesActiveQuery(browser.getUrl())) {
                snapshotPending = true;
                final String expectedId = activeId;
                browser.evaluateJavascript(SNAPSHOT_JS, encoded -> {
                    if (!expectedId.equals(activeId)) return;
                    snapshotPending = false;
                    try {
                        // evaluateJavascript returns a quoted JSON-encoded JS string.
                        String unwrapped = new JSONArray("[" + encoded + "]").getString(0);
                        JSONObject snapshot = new JSONObject(unwrapped);
                        if (!matchesActiveQuery(snapshot.optString("url"))) return;
                        String text = snapshot.optString("text");
                        boolean ready = text.contains("Odpowiedź trybu AI jest gotowa") ||
                                text.contains("AI Mode response is ready");
                        if (ready) complete(snapshot, true, "");
                    } catch (Exception ignored) {
                        // The live page can change while its DOM is being sampled.
                    }
                });
            }
        } catch (Exception ignored) {
            // Partially pushed commands are retried; never publish a fake reply.
        }
        handler.postDelayed(this::tick, POLL_MS);
    }

    private void complete(JSONObject snapshot, boolean ready, String error) {
        if (activeId.isEmpty()) return;
        try {
            JSONObject response = new JSONObject();
            response.put("id", activeId);
            response.put("question", activeQuestion);
            response.put("method", "persistent Android Google AI Mode WebView");
            response.put("loadUrl", activeUrl);
            response.put("pageFinished", pageFinished);
            response.put("page", snapshot);
            response.put("aiResponseReady", ready);
            response.put("elapsedMs", android.os.SystemClock.elapsedRealtime() - startedAtMs);
            response.put("answeredAtEpochMs", System.currentTimeMillis());
            if (!error.isEmpty()) response.put("error", error);
            writeJson(answerFile, response);
        } catch (Exception ignored) {
            // On disk failure the host detects a timeout rather than a fake PASS.
        } finally {
            activeId = "";
            activeQuestion = "";
            activeUrl = "";
            pageFinished = false;
            snapshotPending = false;
        }
    }

    @Override public void onDestroy() {
        handler.removeCallbacksAndMessages(null);
        if (browser != null) browser.destroy();
        super.onDestroy();
    }
}
