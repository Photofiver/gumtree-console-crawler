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
import java.io.File;
import java.io.FileOutputStream;
import java.lang.reflect.Field;
import java.net.URLEncoder;
import java.nio.charset.StandardCharsets;
import java.util.concurrent.CountDownLatch;
import java.util.concurrent.TimeUnit;
import java.util.concurrent.atomic.AtomicReference;
import static org.junit.Assert.*;

@RunWith(AndroidJUnit4.class)
public class AiModeTest {
    private static final String QUESTION = "Napisz kompletny kod w Pythonie 3.11 wykrywający sygnały SHORT na podstawie RSI(14) na interwale 5 minut.\n\nWarunki:\n1. Sygnał występuje wyłącznie wtedy, gdy RSI poprzedniej zamkniętej świecy było poniżej 89, a aktualnej zamkniętej świecy wynosi co najmniej 89.\n2. Nigdy nie używaj niezakończonych świec.\n3. Każdy sygnał można wygenerować tylko raz.\n4. Obsługuj jednocześnie 200 kryptowalut.\n5. Nie korzystaj z dodatkowych bibliotek.\n\nPodaj kompletny działający kod, automatyczne testy i ich oczekiwane wyniki. Uwzględnij brakujące świece, duplikaty danych i RSI równe dokładnie 89. Nie modyfikuj żadnego istniejącego repozytorium.";
    private static WebView view(MainActivity activity) {
        try {
            Field field = MainActivity.class.getDeclaredField("browser");
            field.setAccessible(true);
            return (WebView) field.get(activity);
        } catch (Exception e) { throw new RuntimeException(e); }
    }

    @Test public void testGoogleAiModeRsiPythonCode() throws Exception {
        JSONObject report = new JSONObject();
        report.put("question", QUESTION);
        report.put("method", "Google AI Mode direct URL via Android WebView on GitHub Actions, without Google login");
        File[] output = {null};
        String url = "https://www.google.com/search?udm=50&hl=en&q="
                + URLEncoder.encode(QUESTION, StandardCharsets.UTF_8.name());
        CountDownLatch pageLoaded = new CountDownLatch(1);
        AtomicReference<String> loaded = new AtomicReference<>("NO_PAGE_FINISHED");
        try (ActivityScenario<MainActivity> scenario = ActivityScenario.launch(MainActivity.class)) {
            scenario.onActivity(activity -> {
                WebView web = view(activity);
                output[0] = new File(activity.getExternalFilesDir(null), "google-ai-mode.json");
                web.setWebViewClient(new WebViewClient() {
                    @Override public void onPageFinished(WebView v, String finalUrl) {
                        if (!finalUrl.contains("example.com")) {
                            loaded.set(finalUrl);
                            pageLoaded.countDown();
                        }
                    }
                    @Override public void onReceivedError(WebView v, WebResourceRequest req,
                            WebResourceError error) {
                        if (req.isForMainFrame()) {
                            loaded.set("ERROR:" + error.getDescription());
                            pageLoaded.countDown();
                        }
                    }
                });
                web.loadUrl(url);
            });
            report.put("pageFinished", pageLoaded.await(24, TimeUnit.SECONDS));
            report.put("loadUrl", loaded.get());
            Thread.sleep(27000);
            CountDownLatch snapReady = new CountDownLatch(1);
            AtomicReference<String> raw = new AtomicReference<>("null");
            String js = "(()=>JSON.stringify({"
                    + "url:location.href,title:document.title,"
                    + "text:(document.body?document.body.innerText:'').slice(0,85000),"
                    + "sourceLinks:[...document.querySelectorAll('a[href]')].filter(a=>"
                    + "{try{let u=new URL(a.href);return !u.hostname.endsWith('google.com')"
                    + " && /^https?:$/.test(u.protocol)}catch(e){return false}}).slice(0,45)"
                    + ".map(a=>({text:(a.innerText||a.getAttribute('aria-label')||'').slice(0,120),url:a.href})),"
                    + "fields:[...document.querySelectorAll('textarea,input,[contenteditable=true]')].slice(0,6)"
                    + ".map(e=>({tag:e.tagName,placeholder:e.getAttribute('placeholder')}))"
                    + "}))()";
            scenario.onActivity(activity ->
                view(activity).evaluateJavascript(js, result -> {
                    raw.set(result);
                    snapReady.countDown();
                }));
            report.put("snapshotRead", snapReady.await(12, TimeUnit.SECONDS));
            try {
                String unwrapped = new JSONArray("[" + raw.get() + "]").getString(0);
                JSONObject snapshot = new JSONObject(unwrapped);
                report.put("page", snapshot);
                String text = snapshot.optString("text");
                report.put("aiResponseReady", text.contains("AI Mode response is ready"));
                report.put("responseCharacters",text.length());
                report.put("hasPythonDef",text.contains("def "));
                report.put("hasPythonTest",text.contains("unittest") || text.contains("assert "));
                report.put("containsDVA", text.contains("DVA"));
                report.put("mentionsMOT", text.toLowerCase().contains("mot"));
            } catch (Exception error) { report.put("parseError", error.toString()); }
            try (FileOutputStream stream = new FileOutputStream(output[0])) {
                stream.write(report.toString(2).getBytes(StandardCharsets.UTF_8));
            }
        }
        System.out.println("GOOGLE_AI_RSI_CODE_REPORT " + report.toString());
        assertNotNull(output[0]);
    }
}