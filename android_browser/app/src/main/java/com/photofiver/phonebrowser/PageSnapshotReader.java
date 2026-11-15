package com.photofiver.phonebrowser;

import android.os.Handler;
import android.os.SystemClock;
import android.webkit.WebView;
import org.json.JSONArray;
import org.json.JSONObject;

/** Poll for Google results for up to 2.8s after the first snapshot. */
final class PageSnapshotReader {
    interface Result { void ready(JSONObject page); void error(Exception exception); }

    private static final long GOOGLE_WAIT_MS = 2800;
    private static final long RETRY_MS = 400;
    private PageSnapshotReader() {}

    static void read(WebView view, Handler handler, Result callback) {
        final long start = SystemClock.uptimeMillis();
        attempt(view, handler, callback, start, start + GOOGLE_WAIT_MS, -1, 0);
    }

    private static void attempt(WebView view, Handler handler, Result callback,
                                long start, long deadline, int previousCount, int calls) {
        view.evaluateJavascript(PageSnapshotScript.javascript(), raw -> {
            try {
                JSONObject page = new JSONObject(new JSONArray("[" + raw + "]").getString(0));
                String url = page.optString("url");
                boolean google = url.startsWith("https://www.google.com/search?")
                        || url.matches("https://www\\.google\\.[^/]+/search\\?.*");
                int count = page.optInt("totalResultLinks", 0);
                // Stop as soon as at least three results remain stable across two reads.
                // When Google serves a different layout, return diagnostics at deadline.
                if (google && SystemClock.uptimeMillis() < deadline
                        && (count < 3 || count != previousCount)) {
                    handler.postDelayed(() -> attempt(view, handler, callback,
                            start, deadline, count, calls + 1), RETRY_MS);
                    return;
                }
                page.put("snapshotAttempts", calls + 1);
                page.put("extraWaitMs", SystemClock.uptimeMillis() - start);
                callback.ready(page);
            } catch (Exception e) { callback.error(e); }
        });
    }
}
