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
public class OrigVideoGoogleSolutionTest {
    private static final String QUESTION = "Google AI Mode: We operate TikTok @photofiver.photof in Northern Ireland UK, publishing original photorealistic AI cat shorts generated with Wan 2.2 through GitHub Actions and Buffer Free API; 1 three-second cat video was posted. User wants income, aims up to 15 AI videos per day, no paid services. Research current November 2026 legitimate UK TikTok monetization: Creator Rewards eligibility (followers, views, minimum 1 minute, AI-generated originality), TikTok Shop affiliate eligibility, brand sponsorships, TikTok LIVE gifts, disclosure requirements for realistic AI, and music rights. Compare fastest realistic way to first earnings for a new low-follower account. Give specific actionable 30-day strategy, 3 recommended cat video formats, English vs Polish audience choice, attractive example captions + hashtags, post frequency vs quality, honest expected effort and constraints. Verify facts and distinguish uncertain details; link official TikTok sources; do not promise income. Reply Polish concise.";
    private static WebView view(MainActivity activity) {
        try {
            Field field = MainActivity.class.getDeclaredField("browser");
            field.setAccessible(true);
            return (WebView) field.get(activity);
        } catch (Exception e) { throw new RuntimeException(e); }
    }

    @Test public void testOrigVideoFreeSolution() throws Exception {
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
                output[0] = new File(activity.getExternalFilesDir(null), "original-ai-video-google-response.json");
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
            Thread.sleep(18000);
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
                report.put("mentionsYoutube",text.toLowerCase().contains("youtube"));
                report.put("mentionsTranscript",text.toLowerCase().contains("transcript") || text.toLowerCase().contains("captions"));
                report.put("mentions2006", text.contains("2006"));
                report.put("mentionsTimestamp",text.matches("(?s).*\\\\b\\\\d{1,2}:\\\\d{2}\\\\b.*"));
            } catch (Exception error) { report.put("parseError", error.toString()); }
            try (FileOutputStream stream = new FileOutputStream(output[0])) {
                stream.write(report.toString(2).getBytes(StandardCharsets.UTF_8));
            }
        }
        System.out.println("GOOGLE_ORIGINAL_AI_VIDEO_SOLUTION " + report.toString());
        assertNotNull(output[0]);
    }
}