package com.photofiver.phonebrowser;

import android.os.Handler;
import android.os.Looper;
import android.view.KeyEvent;
import android.webkit.WebResourceError;
import android.webkit.WebResourceRequest;
import android.webkit.WebView;
import android.webkit.WebViewClient;
import androidx.test.core.app.ActivityScenario;
import androidx.test.ext.junit.runners.AndroidJUnit4;
import androidx.test.platform.app.InstrumentationRegistry;
import org.json.JSONArray;
import org.json.JSONObject;
import org.junit.Test;
import org.junit.runner.RunWith;
import java.io.File;
import java.io.FileOutputStream;
import java.lang.reflect.Field;
import java.nio.charset.StandardCharsets;
import java.util.concurrent.CountDownLatch;
import java.util.concurrent.TimeUnit;
import java.util.concurrent.atomic.AtomicReference;
import static org.junit.Assert.*;

@RunWith(AndroidJUnit4.class)
public class AiModeTest {
    private static WebView view(MainActivity activity) {
        try {
            Field f = MainActivity.class.getDeclaredField("browser");
            f.setAccessible(true);
            return (WebView)f.get(activity);
        } catch (Exception e) { throw new RuntimeException(e); }
    }
    private static String eval(ActivityScenario<MainActivity> scenario, String js) throws Exception {
        CountDownLatch done = new CountDownLatch(1);
        AtomicReference<String> value = new AtomicReference<>("null");
        scenario.onActivity(activity ->
            view(activity).evaluateJavascript(js, result -> {
                value.set(result);
                done.countDown();
            }));
        if (!done.await(8, TimeUnit.SECONDS)) return "JS_TIMEOUT";
        try { return new JSONArray("[" + value.get() + "]").getString(0); }
        catch (Exception e) { return "JS_ERROR:" + e; }
    }
    private static String pageSnapshot(ActivityScenario<MainActivity> scenario) throws Exception {
        String script = "(()=>JSON.stringify({"
            + "url:location.href,title:document.title,"
            + "text:(document.body?document.body.innerText:'').slice(0,9500),"
            + "inputFields:[...document.querySelectorAll('textarea,input,[contenteditable=true],[role=textbox]')].slice(0,15)"
            + ".map(e=>({tag:e.tagName,role:e.getAttribute('role'),placeholder:e.getAttribute('placeholder'),"
            + "aria:e.getAttribute('aria-label'),type:e.getAttribute('type'),editable:e.getAttribute('contenteditable')})),"
            + "buttons:[...document.querySelectorAll('button,[role=button]')].slice(0,30)"
            + ".map(e=>({text:(e.innerText||'').slice(0,90),aria:e.getAttribute('aria-label')})),"
            + "hasBelfast:(document.body?document.body.innerText:'').includes('Belfast'),"
            + "hasTwelve:(document.body?document.body.innerText:'').match(/\\b12\\b/)!==null"
            + "}))()";
        return eval(scenario, script);
    }
    private static String open(ActivityScenario<MainActivity> scenario,
                               String url) throws Exception {
        CountDownLatch loaded = new CountDownLatch(1);
        AtomicReference<String> result = new AtomicReference<>("NOT_LOADED");
        scenario.onActivity(activity -> {
            WebView v = view(activity);
            v.setWebViewClient(new WebViewClient() {
                @Override public void onPageFinished(WebView web, String finalUrl) {
                    if (finalUrl.startsWith("https://www.google.com/")) {
                        result.set(finalUrl);
                        loaded.countDown();
                    }
                }
                @Override public void onReceivedError(WebView web,
                    WebResourceRequest request, WebResourceError error) {
                    if (request.isForMainFrame()) {
                        result.set("NETWORK_ERROR:" + error.getDescription());
                        loaded.countDown();
                    }
                }
            });
            v.loadUrl(url);
        });
        loaded.await(19, TimeUnit.SECONDS);
        return result.get();
    }

    @Test public void testGoogleAiModeWithoutAccount() throws Exception {
        JSONObject report = new JSONObject();
        report.put("asked", "What is 7 plus 5? Reply only with the number.");
        report.put("account", "No Google login or credentials were used");
        report.put("method", "Android WebView on GitHub Actions");
        AtomicReference<File> out = new AtomicReference<>();
        try (ActivityScenario<MainActivity> scenario = ActivityScenario.launch(MainActivity.class)) {
            scenario.onActivity(activity -> out.set(new File(
                activity.getExternalFilesDir(null), "google-ai-mode.json")));
            String entry = open(scenario, "https://www.google.com/ai");
            report.put("entryUrl",entry);
            Thread.sleep(1700);
            JSONObject landing = new JSONObject(pageSnapshot(scenario));
            report.put("landing",landing);
            String editor = eval(scenario,
                "(()=>{const e=document.querySelector('textarea,[contenteditable=true],"
                + "[role=textbox],input[type=search],input[type=text]');"
                + "if(!e)return 'NO_EDITOR';"
                + "e.focus();"
                + "const prompt='What is 7 plus 5? Reply only with the number.';"
                + "if(e.isContentEditable){e.textContent=prompt;"
                + "e.dispatchEvent(new InputEvent('input',{bubbles:true,data:prompt,inputType:'insertText'}));}"
                + "else {const p=e.tagName==='TEXTAREA'?HTMLTextAreaElement.prototype:"
                + "HTMLInputElement.prototype;"
                + "Object.getOwnPropertyDescriptor(p,'value').set.call(e,prompt);"
                + "e.dispatchEvent(new Event('input',{bubbles:true}));}"
                + "return 'EDITOR_FILLED:'+e.tagName;})()");
            report.put("editorAction",editor);
            if (editor.startsWith("EDITOR_FILLED")) {
                try {
                    InstrumentationRegistry.getInstrumentation().sendKeyDownUpSync(KeyEvent.KEYCODE_ENTER);
                    report.put("keyboardSubmit","ENTER_SENT");
                } catch (Exception e) { report.put("keyboardSubmit","ERROR:"+e); }
                Thread.sleep(8500);
            }
            JSONObject after = new JSONObject(pageSnapshot(scenario));
            report.put("afterKeyboardSubmit",after);
            boolean answer = after.optBoolean("hasTwelve")
                && !landing.optBoolean("hasTwelve")
                && after.optString("text").toLowerCase().contains("12");
            report.put("initialAnswerCandidate",answer);
            // If AI Mode's editor did not submit, also test its direct query link.
            if (!answer) {
                String directUrl = open(scenario,
                    "https://www.google.com/search?udm=50&hl=en&q=What+is+7+plus+5%3F+Reply+only+with+the+number");
                report.put("directQueryUrl",directUrl);
                Thread.sleep(9000);
                JSONObject direct = new JSONObject(pageSnapshot(scenario));
                report.put("directQuery",direct);
                answer = direct.optBoolean("hasTwelve")
                    && !direct.optString("url").contains("/sorry/")
                    && direct.optString("text").toLowerCase().contains("ai mode");
            }
            report.put("candidateAiAnswerSeen", answer);
            report.put("outcome", answer ? "POSSIBLE_AI_ANSWER_CHECK_REPORT"
                : "NO_CONFIRMED_AI_ANSWER");
            try(FileOutputStream os=new FileOutputStream(out.get())) {
                os.write(report.toString(2).getBytes(StandardCharsets.UTF_8));
            }
        }
        System.out.println("GOOGLE_AI_MODE_RESULT " + report.toString());
        // This only attests that the browser reached the probe and saved evidence.
        // Success/failure of AI Mode is explicitly reported in outcome, not this assertion.
        assertNotNull("No report generated",out.get());
    }
}