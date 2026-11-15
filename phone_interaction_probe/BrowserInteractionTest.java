package com.photofiver.phonebrowser;

import android.os.SystemClock;
import android.view.MotionEvent;
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
import java.util.concurrent.CountDownLatch;
import java.util.concurrent.TimeUnit;
import java.util.concurrent.atomic.AtomicReference;
import static org.junit.Assert.*;

@RunWith(AndroidJUnit4.class)
public class BrowserInteractionTest {
    private static WebView browser(MainActivity activity) {
        try {
            Field field = MainActivity.class.getDeclaredField("browser");
            field.setAccessible(true);
            return (WebView) field.get(activity);
        } catch (Exception e) { throw new RuntimeException(e); }
    }

    private static String js(ActivityScenario<MainActivity> scenario, String source) throws Exception {
        CountDownLatch done = new CountDownLatch(1);
        AtomicReference<String> value = new AtomicReference<>("");
        scenario.onActivity(activity -> browser(activity).evaluateJavascript(source, answer -> {
            value.set(answer);
            done.countDown();
        }));
        assertTrue("Javascript did not answer", done.await(6, TimeUnit.SECONDS));
        return new JSONArray("[" + value.get() + "]").getString(0);
    }

    private static void tap(ActivityScenario<MainActivity> scenario, String selector) throws Exception {
        String measure = "(()=>{let r=document.querySelector(" + JSONObject.quote(selector)
            + ").getBoundingClientRect();return JSON.stringify({x:(r.left+r.width/2)"
            + "*window.innerWidth/" + "window.innerWidth,y:r.top+r.height/2,"
            + "vw:window.innerWidth})})()";
        JSONObject css = new JSONObject(js(scenario, measure));
        scenario.onActivity(activity -> {
            WebView view = browser(activity);
            float ratio = (float)view.getWidth() / (float)css.optDouble("vw", 400);
            float x = (float)css.optDouble("x") * ratio;
            float y = (float)css.optDouble("y") * ratio;
            long start = SystemClock.uptimeMillis();
            MotionEvent down = MotionEvent.obtain(start, start, MotionEvent.ACTION_DOWN, x, y, 0);
            MotionEvent up = MotionEvent.obtain(start, start + 90, MotionEvent.ACTION_UP, x, y, 0);
            view.dispatchTouchEvent(down);
            view.dispatchTouchEvent(up);
            down.recycle();
            up.recycle();
        });
        Thread.sleep(500);
    }

    @Test public void testRealTouchMenuFormLinkBackAndScroll() throws Exception {
        JSONObject report = new JSONObject();
        report.put("kind","Native WebView touch plus production SafeFormScript fill and GET submit");
        report.put("menuTap","NOT_TESTED");
        report.put("fillAction","NOT_TESTED");
        report.put("buttonFormSubmit","NOT_TESTED");
        report.put("searchFormAction","NOT_TESTED");
        report.put("linkTap","NOT_TESTED");
        report.put("back","NOT_TESTED");
        report.put("scroll","NOT_TESTED");
        File saved;
        try(ActivityScenario<MainActivity> scenario = ActivityScenario.launch(MainActivity.class)) {
            CountDownLatch loaded = new CountDownLatch(1);
            AtomicReference<File> reportFile = new AtomicReference<>();
            final String html = "<!DOCTYPE html><html><head><meta name='viewport' "
                + "content='width=device-width, initial-scale=1'></head>"
                + "<body style='font-size:18px;margin:14px'>"
                + "<button id='menu' style='height:56px;width:180px' "
                + "onclick=\"document.getElementById('panel').hidden=false\">Open menu</button>"
                + "<div id='panel' hidden>MENU OPENED</div>"
                + "<form id='form' onsubmit=\"event.preventDefault();"
                + "document.getElementById('answer').textContent='SEARCHED: '+"
                + "document.getElementById('query').value\">"
                + "<input id='query' aria-label='Search term' style='height:50px;width:210px'>"
                + "<button id='submit' style='height:55px;width:140px'>Search</button></form>"
                + "<p id='answer'>NO SEARCH YET</p>"
                + "<a id='next' href='#destination' style='display:block;padding:16px'>"
                + "Read next section</a>"
                + "<div style='height:1500px'>SCROLL SPACE</div>"
                + "<h2 id='destination'>SECOND SECTION</h2></body></html>";
            scenario.onActivity(activity -> {
                reportFile.set(new File(activity.getExternalFilesDir(null), "browser-interaction.json"));
                browser(activity).setWebViewClient(new WebViewClient() {
                    @Override public void onPageFinished(WebView view, String url) {
                        if (url.startsWith("https://example.org/interaction"))
                            loaded.countDown();
                    }
                });
                browser(activity).loadDataWithBaseURL("https://example.org/interaction", html,
                    "text/html","UTF-8",null);
            });
            assertTrue("Local interactive page did not load", loaded.await(12,TimeUnit.SECONDS));
            tap(scenario,"#menu");
            String menu=js(scenario,"String(document.querySelector('#panel').hidden)");
            report.put("menuTap", "false".equals(menu) ? "PASS" : "FAIL");

            // Fill through the same SafeFormScript used by GitHub-controlled app commands.
            String fillResult=js(scenario,SafeFormScript.fill("#query","Belfast"));
            String entered=js(scenario,"document.querySelector('#query').value");
            report.put("fillAction", "FILLED".equals(fillResult) && "Belfast".equals(entered) ? "PASS" : "FAIL");
            report.put("entered",entered);
            report.put("nativeKeyboardTyping","NOT_VERIFIED");

            tap(scenario,"#submit");
            String answer=js(scenario,"document.querySelector('#answer').innerText");
            report.put("buttonFormSubmit","SEARCHED: Belfast".equals(answer)?"PASS":"FAIL");
            report.put("formResponse",answer);

            String searchSubmit=js(scenario,SafeFormScript.submitSearch("#form"));
            report.put("searchFormAction","SUBMITTED".equals(searchSubmit)?"PASS":"FAIL");
            report.put("searchFormResult",searchSubmit);

            tap(scenario,"#next");
            String hash=js(scenario,"location.hash");
            report.put("linkTap", "#destination".equals(hash) ? "PASS" : "FAIL");
            scenario.onActivity(activity -> browser(activity).goBack());
            Thread.sleep(700);
            String back=js(scenario,"location.hash");
            report.put("back",back.isEmpty() ? "PASS":"FAIL");

            js(scenario,"window.scrollTo(0,0);'done'");
            js(scenario,"window.scrollBy(0,500);'done'");
            Thread.sleep(350);
            String y=js(scenario,"String(window.scrollY)");
            report.put("scroll", Double.parseDouble(y)>40?"PASS":"FAIL");
            report.put("scrollY",y);
            saved=reportFile.get();
            try(FileOutputStream stream=new FileOutputStream(saved)){
                stream.write(report.toString(2).getBytes(StandardCharsets.UTF_8));
            }
        }
        System.out.println("INTERACTION_TEST_RESULT " + report);
        for(String action:new String[]{"menuTap","fillAction","buttonFormSubmit","searchFormAction","linkTap","back","scroll"}) {
            assertEquals("Interaction failed: " + action + " " + report,
                "PASS",report.optString(action));
        }
    }
}
