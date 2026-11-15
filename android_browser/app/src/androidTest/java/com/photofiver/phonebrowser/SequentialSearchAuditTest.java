package com.photofiver.phonebrowser;

import android.os.Handler;
import android.os.Looper;
import android.util.Log;
import android.webkit.WebResourceError;
import android.webkit.WebResourceRequest;
import android.webkit.WebView;
import android.webkit.WebViewClient;

import androidx.test.core.app.ActivityScenario;
import androidx.test.ext.junit.runners.AndroidJUnit4;

import org.json.JSONArray;
import org.json.JSONObject;
import org.junit.Test;
import org.junit.runner.RunWith;

import java.io.File;
import java.io.FileOutputStream;
import java.lang.reflect.Field;
import java.nio.charset.StandardCharsets;
import java.util.Locale;
import java.util.concurrent.CountDownLatch;
import java.util.concurrent.TimeUnit;
import java.util.concurrent.atomic.AtomicBoolean;
import java.util.concurrent.atomic.AtomicReference;

import static org.junit.Assert.*;

@RunWith(AndroidJUnit4.class)
public class SequentialSearchAuditTest {
    private static final String QUERY = "Belfast Northern Ireland";
    private static final String Q = "Belfast+Northern+Ireland";
    private static final String[][] ENGINES = {
        {"01 Google", "https://www.google.com/search?q=" + Q},
        {"02 Bing", "https://www.bing.com/search?q=" + Q},
        {"03 DuckDuckGo", "https://duckduckgo.com/?q=" + Q + "&ia=web"},
        {"04 DuckDuckGo Lite", "https://lite.duckduckgo.com/lite/?q=" + Q},
        {"05 Brave Search", "https://search.brave.com/search?q=" + Q},
        {"06 Mojeek", "https://www.mojeek.com/search?q=" + Q},
        {"07 Startpage", "https://www.startpage.com/sp/search?query=" + Q},
        {"08 Qwant", "https://www.qwant.com/?q=" + Q},
        {"09 Ecosia", "https://www.ecosia.org/search?q=" + Q},
        {"10 Swisscows", "https://swisscows.com/en/web?query=" + Q},
        {"11 Yahoo", "https://search.yahoo.com/search?p=" + Q},
        {"12 Yandex", "https://yandex.com/search/?text=" + Q},
        {"13 Yep", "https://yep.com/web?q=" + Q},
        {"14 You.com", "https://you.com/search?q=" + Q},
        {"15 Lilo", "https://search.lilo.org/?q=" + Q},
        {"16 SearXNG Disroot", "https://search.disroot.org/search?q=" + Q},
        {"17 MetaGer", "https://metager.org/meta/meta.ger3?eingabe=" + Q},
        {"18 AOL Search", "https://search.aol.com/aol/search?q=" + Q},
        {"19 Seznam", "https://search.seznam.cz/?q=" + Q},
        {"20 Naver", "https://search.naver.com/search.naver?query=" + Q}
    };

    private static WebView getBrowser(MainActivity activity) throws Exception {
        Field f = MainActivity.class.getDeclaredField("browser");
        f.setAccessible(true);
        return (WebView) f.get(activity);
    }

    private static String decode(String fromJs) {
        try { return new JSONArray("[" + fromJs + "]").getString(0); }
        catch (Exception e) { return ""; }
    }

    private static JSONObject classify(String name, String requestUrl, JSONObject page) throws Exception {
        String body = page.optString("text");
        String lower = body.toLowerCase(Locale.ROOT);
        String title = page.optString("title");
        String finalUrl = page.optString("url");
        JSONArray external = page.optJSONArray("external");
        int externalCount = external == null ? 0 : external.length();
        boolean hasTopic = lower.contains("belfast");
        boolean challenged = lower.contains("automated queries") ||
                lower.contains("unusual traffic") || lower.contains("captcha") ||
                lower.contains("verify you are human") || lower.contains("verify you're human") ||
                lower.contains("access denied") || lower.contains("403 - forbidden") ||
                lower.contains("checking your browser") || lower.contains("robot verification") ||
                lower.contains("rate limit exceeded") || finalUrl.contains("/sorry/");
        String status = challenged ? "BLOCKED" :
                (hasTopic && externalCount >= 2 && body.length() >= 350)
                        ? "CANDIDATE_RESULTS" : "NO_CONFIRMED_RESULTS";
        JSONObject item = new JSONObject();
        item.put("name", name);
        item.put("query", QUERY);
        item.put("status", status);
        item.put("requestUrl", requestUrl);
        item.put("finalUrl", finalUrl);
        item.put("title", title);
        item.put("bodyChars", body.length());
        item.put("topicMentioned", hasTopic);
        item.put("externalLinks", externalCount);
        item.put("textSample", body.substring(0, Math.min(1100, body.length())));
        JSONArray linkSample = new JSONArray();
        for (int i=0; external != null && i < Math.min(6, external.length()); i++) {
            linkSample.put(external.getJSONObject(i));
        }
        item.put("linkSamples", linkSample);
        return item;
    }

    private static JSONObject probe(ActivityScenario<MainActivity> scenario, String name, String url)
            throws Exception {
        CountDownLatch done = new CountDownLatch(1);
        AtomicReference<String> raw = new AtomicReference<>("");
        AtomicBoolean responded = new AtomicBoolean(false);
        long t0 = System.currentTimeMillis();

        scenario.onActivity(activity -> {
            try {
                WebView view = getBrowser(activity);
                Handler handler = new Handler(Looper.getMainLooper());
                view.setWebViewClient(new WebViewClient() {
                    @Override public void onPageFinished(WebView webview, String loadedUrl) {
                        if (responded.get()) return;
                        handler.postDelayed(() -> {
                            if (responded.get()) return;
                            String js = "(()=>JSON.stringify({title:document.title,url:location.href,"
                                + "text:(document.body?document.body.innerText:'').slice(0,10000),"
                                + "external:[...document.querySelectorAll('a[href]')].slice(0,180)"
                                + ".filter(a=>{try{let h=new URL(a.href).hostname;"
                                + "return a.href.startsWith('http')&&h!==location.hostname"
                                + "&&(a.innerText||a.getAttribute('aria-label')||'').trim().length>3;"
                                + "}catch(e){return false}}).slice(0,35)"
                                + ".map(a=>({text:(a.innerText||a.getAttribute('aria-label')||'').trim().slice(0,100),"
                                + "url:a.href.slice(0,220)}))}))()";
                            webview.evaluateJavascript(js, value -> {
                                if (responded.compareAndSet(false, true)) {
                                    raw.set(decode(value));
                                    done.countDown();
                                }
                            });
                        }, 1600);
                    }
                    @Override public void onReceivedError(WebView webview,
                            WebResourceRequest request, WebResourceError error) {
                        if (request.isForMainFrame() && responded.compareAndSet(false,true)) {
                            raw.set("LOAD_ERROR: " + error.getDescription());
                            done.countDown();
                        }
                    }
                });
                view.loadUrl(url);
            } catch(Exception e) {
                raw.set("LAUNCH_ERROR: " + e.getMessage());
                done.countDown();
            }
        });

        boolean finished = done.await(9, TimeUnit.SECONDS);
        JSONObject item;
        if (!finished || raw.get().startsWith("LOAD_ERROR") ||
                raw.get().startsWith("LAUNCH_ERROR") || raw.get().isEmpty()) {
            item = new JSONObject();
            item.put("name",name);
            item.put("requestUrl",url);
            item.put("status", !finished ? "TIMEOUT" : "LOAD_ERROR");
            item.put("error", raw.get());
        } else {
            try { item = classify(name, url, new JSONObject(raw.get())); }
            catch (Exception error) {
                item = new JSONObject();
                item.put("name",name);
                item.put("requestUrl",url);
                item.put("status","PARSE_ERROR");
                item.put("error",error.toString());
            }
        }
        item.put("durationMs", System.currentTimeMillis() - t0);
        Log.i("PHONE_SEARCH_AUDIT", item.toString());
        System.out.println("SEARCH_RESULT " + item.toString());
        return item;
    }

    @Test public void auditTwentySearchEnginesInOrder() throws Exception {
        JSONArray results = new JSONArray();
        try(ActivityScenario<MainActivity> scenario = ActivityScenario.launch(MainActivity.class)) {
            AtomicReference<File> output = new AtomicReference<>();
            scenario.onActivity(activity ->
                output.set(new File(activity.getExternalFilesDir(null), "search-audit.json")));
            for (String[] e: ENGINES) {
                JSONObject outcome = probe(scenario, e[0],e[1]);
                results.put(outcome);
                // Write after EACH engine so a later hang cannot erase earlier evidence.
                try (FileOutputStream out = new FileOutputStream(output.get())) {
                    out.write(results.toString(2).getBytes(StandardCharsets.UTF_8));
                }
                Log.i("PHONE_SEARCH_AUDIT", "Completed "+results.length()+"/20");
                Thread.sleep(700);
            }
        }
        assertEquals(20, results.length());
    }
}
