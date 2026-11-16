package com.photofiver.phonebrowser;

import android.webkit.WebView;
import android.webkit.WebViewClient;
import android.webkit.WebResourceRequest;
import android.webkit.WebResourceError;
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
public class SocialMediaProbeTest {
    private WebView browser(MainActivity activity) {
        try {
            Field f = MainActivity.class.getDeclaredField("browser");
            f.setAccessible(true);
            return (WebView) f.get(activity);
        } catch (Exception e) { throw new RuntimeException(e); }
    }

    private JSONObject snapshot(ActivityScenario<MainActivity> scenario) throws Exception {
        AtomicReference<String> result = new AtomicReference<>("null");
        CountDownLatch done = new CountDownLatch(1);
        scenario.onActivity(a -> browser(a).evaluateJavascript(
            "(()=>JSON.stringify({url:location.href,title:document.title,text:(document.body?document.body.innerText:'').slice(0,20000)}))()",
            value -> { result.set(value); done.countDown(); }));
        if (!done.await(15,TimeUnit.SECONDS)) throw new Exception("JavaScript snapshot timed out");
        return new JSONObject(new JSONArray("["+result.get()+"]").getString(0));
    }

    private JSONObject visit(ActivityScenario<MainActivity> scenario, String url, int seconds) throws Exception {
        CountDownLatch loaded = new CountDownLatch(1);
        AtomicReference<String> page = new AtomicReference<>("TIMEOUT");
        scenario.onActivity(a -> {
            WebView web = browser(a);
            web.setWebViewClient(new WebViewClient() {
                @Override public void onPageFinished(WebView v,String u) {
                    page.set(u); loaded.countDown();
                }
                @Override public void onReceivedError(WebView v,WebResourceRequest q,WebResourceError e) {
                    if(q.isForMainFrame()){page.set("ERROR:"+e.getDescription());loaded.countDown();}
                }
            });
            web.loadUrl(url);
        });
        boolean wasLoaded = loaded.await(seconds,TimeUnit.SECONDS);
        Thread.sleep(6500);
        JSONObject snap = snapshot(scenario);
        snap.put("navigationFinished", wasLoaded);
        snap.put("navigationOutcome", page.get());
        return snap;
    }

    @Test public void testSocialContentAndVideoPublishingAccess() throws Exception {
        JSONObject out = new JSONObject();
        out.put("scope","Anonymous Google AI Mode and public page accessibility, no login, no publishing, no credits consumed");
        String question = "Write an original 15-second vertical social media video script about three simple smartphone battery tips. Reply ONLY as exactly five separate lines beginning with HEADLINE:, SCENE1:, SCENE2:, SCENE3:, CAPTION:. Keep each scene below eight words, make it useful and avoid exaggerated claims. Do not repeat instructions.";
        String aiUrl = "https://www.google.com/search?udm=50&hl=en&q="
               + URLEncoder.encode(question, StandardCharsets.UTF_8.name());
        try(ActivityScenario<MainActivity> scenario=ActivityScenario.launch(MainActivity.class)) {
            JSONObject ai=visit(scenario,aiUrl,30);
            String body=ai.optString("text");
            ai.put("answerReady",body.contains("AI Mode response is ready"));
            ai.put("headlineFound",body.contains("\nHEADLINE:"));
            ai.put("scenesFound",body.contains("\nSCENE1:") && body.contains("\nSCENE2:") && body.contains("\nSCENE3:"));
            out.put("google_ai",ai);

            JSONObject flow=visit(scenario,"https://labs.google/fx/tools/flow",25);
            String text=flow.optString("text").toLowerCase(java.util.Locale.ROOT);
            flow.put("hasSignInText",text.contains("sign in")||text.contains("get started")||text.contains("google account"));
            flow.put("mentionsFree",text.contains("free")||text.contains("no subscription"));
            out.put("google_flow",flow);

            JSONObject youtube=visit(scenario,"https://studio.youtube.com/",20);
            out.put("youtube_studio",youtube);
            JSONObject tiktok=visit(scenario,"https://www.tiktok.com/upload",20);
            out.put("tiktok_upload",tiktok);
            JSONObject instagram=visit(scenario,"https://www.instagram.com/",20);
            out.put("instagram",instagram);
        }
        File file = new File(androidx.test.platform.app.InstrumentationRegistry.getInstrumentation()
            .getTargetContext().getExternalFilesDir(null),"social-media-probe.json");
        try(FileOutputStream stream=new FileOutputStream(file)) {
            stream.write(out.toString(2).getBytes(StandardCharsets.UTF_8));
        }
        System.out.println("SOCIAL_MEDIA_PROBE_REPORT "+out.toString());
        assertTrue("Google AI page did not return a usable AI Mode answer: "+out.toString(),
            out.getJSONObject("google_ai").optBoolean("answerReady"));
    }
}