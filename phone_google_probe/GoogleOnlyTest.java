package com.photofiver.phonebrowser;

import android.os.Handler;
import android.os.Looper;
import android.util.Log;
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

import java.io.File;
import java.io.FileOutputStream;
import java.lang.reflect.Field;
import java.nio.charset.StandardCharsets;
import java.util.Locale;
import java.util.concurrent.CountDownLatch;
import java.util.concurrent.TimeUnit;
import java.util.concurrent.atomic.AtomicReference;
import static org.junit.Assert.*;

@RunWith(AndroidJUnit4.class)
public class GoogleOnlyTest {
    @Test public void testGoogleBelfast() throws Exception {
        final String queryUrl = "https://www.google.com/search?q=Belfast+Northern+Ireland&udm=14";
        CountDownLatch completed = new CountDownLatch(1);
        AtomicReference<String> raw = new AtomicReference<>("");
        AtomicReference<String> loadedUrl = new AtomicReference<>("");
        AtomicReference<File> output = new AtomicReference<>();
        try (ActivityScenario<MainActivity> scenario = ActivityScenario.launch(MainActivity.class)) {
            scenario.onActivity(activity -> {
                try {
                    Field field = MainActivity.class.getDeclaredField("browser");
                    field.setAccessible(true);
                    WebView browser = (WebView) field.get(activity);
                    output.set(new File(activity.getExternalFilesDir(null), "google-only.json"));
                    browser.setWebViewClient(new WebViewClient() {
                        @Override public void onPageFinished(WebView view, String url) {
                            if (url.startsWith("https://example.com/")) return;
                            loadedUrl.set(url);
                            new Handler(Looper.getMainLooper()).postDelayed(() ->
                                view.evaluateJavascript(
                                    "(()=>{const page=JSON.parse(" + PageSnapshotScript.javascript() + ");"
                                    + "const heads=[...document.querySelectorAll('h1,h2,h3,[role=heading]')].slice(0,12);"
                                    + "const inspect=e=>{let a=e;let out=[];for(let i=0;a&&i<5;i++,a=a.parentElement){"
                                    + "out.push({tag:a.tagName,text:(a.innerText||'').slice(0,90),"
                                    + "attrs:[...a.attributes].filter(v=>/href|url|role|data-|jsaction/.test(v.name))"
                                    + ".slice(0,10).map(v=>[v.name,v.value.slice(0,170)])});}return out;};"
                                    + "const needle=/Belfast|Wikipedia|Tripadvisor|Ireland.com/i;"
                                    + "const walk=document.createTreeWalker(document.body,NodeFilter.SHOW_TEXT);"
                                    + "let n,samples=[],seen=0;while((n=walk.nextNode())&&seen++<18000){"
                                    + "if(needle.test((n.textContent||'').trim())&&(n.textContent||'').trim().length<160){"
                                    + "samples.push(inspect(n.parentElement));if(samples.length>=10)break;}}"
                                    + "page.domDebug={anchors:document.querySelectorAll('a[href]').length,"
                                    + "headings:heads.map(e=>inspect(e)),samples:samples};"
                                    + "return JSON.stringify(page)})()",
                                    value -> { raw.set(value); completed.countDown(); })
                                , 1200);
                        }
                        @Override public void onReceivedError(WebView view, WebResourceRequest req, WebResourceError error) {
                            if (req.isForMainFrame()) {
                                raw.set("NETWORK_ERROR:" + error.getDescription());
                                completed.countDown();
                            }
                        }
                    });
                    browser.loadUrl(queryUrl);
                } catch (Exception e) { raw.set("APP_ERROR:" + e); completed.countDown(); }
            });
            boolean finished = completed.await(25, TimeUnit.SECONDS);
            JSONObject report = new JSONObject();
            report.put("engine","Google");
            report.put("query","Belfast Northern Ireland");
            report.put("url",loadedUrl.get());
            if (!finished) { report.put("status","TIMEOUT"); }
            else if (raw.get().startsWith("NETWORK_ERROR:") || raw.get().startsWith("APP_ERROR:")) {
                report.put("status","ERROR"); report.put("error",raw.get());
            } else {
                try {
                    JSONObject data = new JSONObject(new JSONArray("["+raw.get()+"]").getString(0));
                    String t=data.optString("text"), lower=t.toLowerCase(Locale.ROOT);
                    boolean blocked = data.optString("url").contains("google.com/sorry")
                        || lower.contains("unusual traffic")
                        || lower.contains("automated queries")
                        || lower.contains("verify you are human")
                        || lower.contains("captcha")
                        || lower.contains("before you continue to google")
                        || lower.contains("consent to cookies")
                        || lower.contains("403 forbidden")
                        || lower.contains("access denied");
                    JSONArray links = data.optJSONArray("links");
                    int count = links==null?0:links.length();
                    report.put("status",blocked?"BLOCKED":(lower.contains("belfast") && count>=2 && t.length()>350)?"POSSIBLE_RESULTS":"NO_CONFIRMED_RESULTS");
                    report.put("title",data.optString("title"));
                    report.put("textSample",t.substring(0,Math.min(t.length(),2000)));
                    report.put("resultLinks",links);
                    report.put("linkDiagnostics",data.optJSONArray("linkDiagnostics"));
                    report.put("domDebug",data.optJSONObject("domDebug"));
                    report.put("externalLinkCount",count);
                } catch(Exception e) {report.put("status","PARSE_ERROR");report.put("error",e.toString());}
            }
            if ("POSSIBLE_RESULTS".equals(report.optString("status"))) {
                JSONArray found = report.optJSONArray("resultLinks");
                String wikipediaLink = "";
                for (int i = 0; found != null && i < found.length(); i++) {
                    JSONObject candidate = found.optJSONObject(i);
                    if (candidate != null && candidate.optString("text")
                            .toLowerCase(Locale.ROOT).contains("wikipedia")) {
                        wikipediaLink = candidate.optString("url");
                        break;
                    }
                }
                report.put("selectedLink", wikipediaLink);
                if (!wikipediaLink.startsWith("https://")) {
                    report.put("clickStatus", "WIKIPEDIA_RESULT_LINK_MISSING");
                } else {
                    CountDownLatch opened = new CountDownLatch(1);
                    AtomicReference<String> finalUrl = new AtomicReference<>("");
                    AtomicReference<String> openedText = new AtomicReference<>("");
                    AtomicReference<String> navigationError = new AtomicReference<>("");
                    final String target = wikipediaLink;
                    scenario.onActivity(activity -> {
                        try {
                            Field field = MainActivity.class.getDeclaredField("browser");
                            field.setAccessible(true);
                            WebView view = (WebView) field.get(activity);
                            view.setWebViewClient(new WebViewClient() {
                                @Override public void onPageFinished(WebView webView, String url) {
                                    finalUrl.set(url);
                                    if (url.contains("wikipedia.org/")) {
                                        webView.evaluateJavascript(
                                            "document.body ? document.body.innerText.slice(0,1000) : ''",
                                            value -> {
                                                try {
                                                    openedText.set(new JSONArray("[" + value + "]").getString(0));
                                                } catch (Exception e) {
                                                    navigationError.set("Text read failed: " + e);
                                                }
                                                opened.countDown();
                                            });
                                    }
                                }
                                @Override public void onReceivedError(WebView webView,
                                        WebResourceRequest req, WebResourceError error) {
                                    if (req.isForMainFrame()) {
                                        finalUrl.set(req.getUrl().toString());
                                        navigationError.set(error.getDescription().toString());
                                        opened.countDown();
                                    }
                                }
                            });
                            view.loadUrl(target);
                        } catch (Exception e) {
                            navigationError.set(e.toString());
                            opened.countDown();
                        }
                    });
                    boolean gotResult = opened.await(30, TimeUnit.SECONDS);
                    report.put("clickedFinalUrl", finalUrl.get());
                    report.put("clickedTextSample", openedText.get().substring(
                        0, Math.min(500, openedText.get().length())));
                    report.put("clickStatus", !gotResult ? "NAVIGATION_TIMEOUT"
                        : !navigationError.get().isEmpty() ? "NAVIGATION_ERROR"
                        : finalUrl.get().contains("wikipedia.org/")
                                && openedText.get().toLowerCase(Locale.ROOT).contains("belfast")
                                ? "OPENED_WIKIPEDIA" : "UNEXPECTED_DESTINATION");
                    if (!navigationError.get().isEmpty())
                        report.put("clickError", navigationError.get());
                }
            } else {
                report.put("clickStatus", "SEARCH_RESULTS_NOT_CONFIRMED");
            }
            Log.i("GOOGLE_SINGLE_PROBE","FINAL "+report.toString());
            System.out.println("GOOGLE_SINGLE_PROBE_FINAL "+report.toString());
            try(FileOutputStream f=new FileOutputStream(output.get())){
                f.write(report.toString(2).getBytes(StandardCharsets.UTF_8));
            }
            assertEquals("Google result must open real Wikipedia page: " + report,
                "OPENED_WIKIPEDIA", report.optString("clickStatus"));
        }
    }
}
