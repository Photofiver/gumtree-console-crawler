package com.photofiver.phonebrowser;

import android.webkit.WebView;
import android.webkit.WebViewClient;
import android.os.Handler;
import android.os.Looper;
import android.webkit.WebResourceRequest;
import android.webkit.WebResourceError;
import org.json.JSONArray;
import org.json.JSONObject;
import androidx.test.core.app.ActivityScenario;
import androidx.test.ext.junit.runners.AndroidJUnit4;
import org.junit.Test;
import org.junit.runner.RunWith;
import java.lang.reflect.Field;
import java.lang.reflect.Method;
import java.util.concurrent.CountDownLatch;
import java.util.concurrent.TimeUnit;
import java.util.concurrent.atomic.AtomicReference;
import static org.junit.Assert.*;

@RunWith(AndroidJUnit4.class)
public class PhoneBrowserSmokeTest {
    private static WebView browser(MainActivity activity) {
        try {
            Field field = MainActivity.class.getDeclaredField("browser");
            field.setAccessible(true);
            return (WebView) field.get(activity);
        } catch (Exception e) { throw new AssertionError(e); }
    }

    @Test public void launchesWithoutGitHubToken() {
        try (ActivityScenario<MainActivity> scenario = ActivityScenario.launch(MainActivity.class)) {
            scenario.onActivity(activity -> {
                assertNotNull(browser(activity));
                assertTrue(browser(activity).getSettings().getJavaScriptEnabled());
                assertFalse(browser(activity).getSettings().getAllowFileAccess());
            });
        }
    }

    @Test public void dangerousAndNonHttpsUrlsAreRejected() throws Exception {
        Method method = MainActivity.class.getDeclaredMethod("safeUrl", String.class);
        method.setAccessible(true);
        assertTrue((Boolean) method.invoke(null, "https://example.com/read/article"));
        assertFalse((Boolean) method.invoke(null, "http://example.com/"));
        assertFalse((Boolean) method.invoke(null, "https://localhost/admin"));
        assertFalse((Boolean) method.invoke(null, "https://example.com/account/delete"));
        assertFalse((Boolean) method.invoke(null, "https://example.com/?action=delete"));
    }

    @Test public void javascriptExecutesInPhoneWebView() throws Exception {
        CountDownLatch done = new CountDownLatch(1);
        AtomicReference<String> output = new AtomicReference<>("");
        try (ActivityScenario<MainActivity> scenario = ActivityScenario.launch(MainActivity.class)) {
            scenario.onActivity(activity -> {
                WebView webView = browser(activity);
                webView.loadDataWithBaseURL("https://example.org/",
                    "<html><body><span id='result'>before</span><script>"
                    + "document.getElementById('result').textContent='hello-from-js';"
                    + "</script></body></html>", "text/html", "UTF-8", null);
                Handler handler = new Handler(Looper.getMainLooper());
                Runnable check = new Runnable() {
                    int attempts = 0;
                    @Override public void run() {
                        webView.evaluateJavascript(
                            "(document.getElementById('result') || {}).textContent || ''",
                            value -> {
                                if ("\"hello-from-js\"".equals(value)) {
                                    output.set(value);
                                    done.countDown();
                                } else if (attempts++ < 35) {
                                    handler.postDelayed(this, 450);
                                }
                            });
                    }
                };
                handler.postDelayed(check, 500);
            });
            assertTrue("WebView JavaScript timed out", done.await(25, TimeUnit.SECONDS));
            assertEquals("\"hello-from-js\"", output.get());
        }
    }

    @Test public void externalHttpsPageLoadsInWebView() throws Exception {
        CountDownLatch done = new CountDownLatch(1);
        AtomicReference<String> output = new AtomicReference<>("");
        try (ActivityScenario<MainActivity> scenario = ActivityScenario.launch(MainActivity.class)) {
            scenario.onActivity(activity -> {
                WebView webView = browser(activity);
                webView.setWebViewClient(new WebViewClient() {
                    @Override public void onPageFinished(WebView view, String url) {
                        if (url.startsWith("https://example.com/")) {
                            view.evaluateJavascript(
                                "document.body ? document.body.innerText.slice(0,1500) : ''",
                                value -> { output.set(value); done.countDown(); });
                        }
                    }
                    @Override public void onReceivedError(WebView view, WebResourceRequest request, WebResourceError error) {
                        if (request.isForMainFrame()) {
                            output.set("ERROR: " + error.getDescription());
                            done.countDown();
                        }
                    }
                });
                webView.loadUrl("https://example.com/");
            });
            assertTrue("External page timed out", done.await(40, TimeUnit.SECONDS));
            assertFalse("WebView cannot open public HTTPS page: " + output.get(), output.get().startsWith("ERROR:"));
            assertTrue("No readable webpage content: " + output.get(), output.get().length() >= 30);
        }
    }
    @Test public void searchQueryBuildsSafeUrl() throws Exception {
        Method method = MainActivity.class.getDeclaredMethod("makeSearchUrl", String.class);
        method.setAccessible(true);
        String url = (String) method.invoke(null, "Belfast city");
        assertTrue(url.startsWith("https://www.google.com/search?q="));
        assertTrue(url.contains("Belfast"));
        assertFalse(url.contains(" "));
    }

    @Test public void searchActionLoadsRealSearchResults() throws Exception {
        CountDownLatch done = new CountDownLatch(1);
        AtomicReference<String> urlResult = new AtomicReference<>("");
        AtomicReference<String> rawResult = new AtomicReference<>("");
        try (ActivityScenario<MainActivity> scenario = ActivityScenario.launch(MainActivity.class)) {
            scenario.onActivity(activity -> {
                try {
                    WebView webView = browser(activity);
                    webView.setWebViewClient(new WebViewClient() {
                        @Override public void onPageFinished(WebView view, String url) {
                            if (!url.contains("google.com/search")) return;
                            urlResult.set(url);
                            new Handler(Looper.getMainLooper()).postDelayed(() ->
                                view.evaluateJavascript(PageSnapshotScript.javascript(),
                                    value -> { rawResult.set(value); done.countDown(); }), 1700);
                        }
                        @Override public void onReceivedError(WebView view, WebResourceRequest req, WebResourceError error) {
                            if (req.isForMainFrame()) {
                                rawResult.set("ERROR: " + error.getDescription());
                                done.countDown();
                            }
                        }
                    });
                    Field busy = MainActivity.class.getDeclaredField("busy");
                    Field navigating = MainActivity.class.getDeclaredField("navigating");
                    Field steps = MainActivity.class.getDeclaredField("steps");
                    Field index = MainActivity.class.getDeclaredField("stepIndex");
                    for (Field field : new Field[]{busy, navigating, steps, index}) field.setAccessible(true);
                    busy.set(activity, true);
                    navigating.set(activity, false);
                    index.set(activity, 0);
                    steps.set(activity, new JSONArray().put(
                        new JSONObject().put("action","search").put("value","Belfast Northern Ireland")));
                    Method next = MainActivity.class.getDeclaredMethod("nextStep");
                    next.setAccessible(true);
                    next.invoke(activity);
                } catch (Exception e) {
                    rawResult.set("ERROR: " + e.getMessage());
                    done.countDown();
                }
            });
            assertTrue("Search did not finish loading", done.await(60, TimeUnit.SECONDS));
            assertFalse("Search navigation failed: " + rawResult.get(), rawResult.get().startsWith("ERROR:"));
            assertTrue("Search did not navigate to expected search engine: " + urlResult.get(),
                urlResult.get().contains("google.com/search"));
            String decoded = new JSONArray("[" + rawResult.get() + "]").getString(0);
            JSONObject page = new JSONObject(decoded);
            String body = page.optString("text").toLowerCase(java.util.Locale.ROOT);
            assertTrue("No topic-related search results: " + body.substring(0,Math.min(600,body.length())),
                body.contains("belfast") && body.length() > 250);
            assertTrue("Search engine did not return result links: " + page,
                page.getJSONArray("links").length() >= 2);
            assertFalse("Search engine challenge page: " + body.substring(0,Math.min(600,body.length())),
                body.contains("unusual traffic") || body.contains("verify you are human")
                || body.contains("access denied") || body.contains("captcha"));
        }
    }

}
