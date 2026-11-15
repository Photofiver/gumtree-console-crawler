package com.photofiver.phonebrowser;

import android.webkit.WebView;
import android.webkit.WebViewClient;
import android.webkit.WebResourceRequest;
import android.webkit.WebResourceError;
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
                webView.setWebViewClient(new WebViewClient() {
                    @Override public void onPageFinished(WebView view, String url) {
                        if (url.startsWith("https://example.org/")) {
                            view.evaluateJavascript("document.getElementById('result').textContent",
                                    value -> { output.set(value); done.countDown(); });
                        }
                    }
                });
                webView.loadDataWithBaseURL("https://example.org/",
                    "<html><body><span id='result'>before</span><script>"
                    + "document.getElementById('result').textContent='hello-from-js';"
                    + "</script></body></html>", "text/html", "UTF-8", null);
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
}
