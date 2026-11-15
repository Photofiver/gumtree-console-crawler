package com.photofiver.phonebrowser;

import android.webkit.WebView;
import android.webkit.WebViewClient;
import android.webkit.WebResourceError;
import android.webkit.WebResourceRequest;
import androidx.test.core.app.ActivityScenario;
import androidx.test.ext.junit.runners.AndroidJUnit4;
import org.json.JSONArray;
import org.json.JSONObject;
import org.junit.Test;
import org.junit.runner.RunWith;
import java.lang.reflect.Field;
import java.util.Locale;
import java.util.concurrent.CountDownLatch;
import java.util.concurrent.TimeUnit;
import java.util.concurrent.atomic.AtomicReference;
import static org.junit.Assert.*;

@RunWith(AndroidJUnit4.class)
public class SearchEngineProbeTest {
    private static WebView browser(MainActivity activity) {
        try {
            Field field = MainActivity.class.getDeclaredField("browser");
            field.setAccessible(true);
            return (WebView) field.get(activity);
        } catch (Exception e) { throw new AssertionError(e); }
    }

    private void verify(String engine, String url, String expectedHost) throws Exception {
        CountDownLatch done = new CountDownLatch(1);
        AtomicReference<String> result = new AtomicReference<>("");
        AtomicReference<String> actualUrl = new AtomicReference<>("");
        try (ActivityScenario<MainActivity> scenario = ActivityScenario.launch(MainActivity.class)) {
            scenario.onActivity(activity -> {
                WebView webview = browser(activity);
                webview.setWebViewClient(new WebViewClient() {
                    @Override public void onPageFinished(WebView view, String loadedUrl) {
                        if (loadedUrl.contains("example.com")) return;
                        actualUrl.set(loadedUrl);
                        view.evaluateJavascript(
                            "JSON.stringify({title:document.title,text:(document.body?document.body.innerText:'').slice(0,8000),"
                            + "count:document.querySelectorAll('a[href]').length,"
                            + "external:[...document.querySelectorAll('a[href]')].filter(a=>{try{return new URL(a.href).hostname!==location.hostname}catch(e){return false}}).length})",
                            v -> { result.set(v); done.countDown(); });
                    }
                    @Override public void onReceivedError(WebView view, WebResourceRequest request, WebResourceError error) {
                        if (request.isForMainFrame()) {
                            result.set("ERROR:" + error.getDescription());
                            done.countDown();
                        }
                    }
                });
                webview.loadUrl(url);
            });
            assertTrue(engine + " timed out", done.await(50, TimeUnit.SECONDS));
            assertFalse(engine + " failed: " + result.get(), result.get().startsWith("ERROR:"));
            String decoded = new JSONArray("[" + result.get() + "]").getString(0);
            JSONObject page = new JSONObject(decoded);
            String body = page.getString("text").toLowerCase(Locale.ROOT);
            String sample = body.substring(0,Math.min(700,body.length()));
            assertTrue(engine + " redirected to unrelated page: " + actualUrl.get(),
                    actualUrl.get().contains(expectedHost));
            assertTrue(engine + " no Belfast-related results: " + sample,
                    body.contains("belfast") && body.length() > 350);
            assertTrue(engine + " insufficient link results: " + sample + " " + page,
                    page.optInt("external") >= 2);
            assertFalse(engine + " rejected automation: " + sample,
                    body.contains("unusual traffic") || body.contains("automated queries")
                    || body.contains("captcha") || body.contains("access denied") || body.contains("verify you are human"));
        }
    }

    @Test public void bingSearch() throws Exception {
        verify("Bing", "https://www.bing.com/search?q=Belfast+Northern+Ireland", "bing.com");
    }

    @Test public void duckDuckGoLiteSearch() throws Exception {
        verify("DDG Lite", "https://lite.duckduckgo.com/lite/?q=Belfast+Northern+Ireland", "duckduckgo.com");
    }

    @Test public void braveSearch() throws Exception {
        verify("Brave", "https://search.brave.com/search?q=Belfast+Northern+Ireland", "brave.com");
    }
}
