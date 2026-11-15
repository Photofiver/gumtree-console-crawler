package com.photofiver.phonebrowser;

import android.app.Notification;
import android.app.NotificationChannel;
import android.app.NotificationManager;
import android.app.Service;
import android.content.Intent;
import android.os.IBinder;

/** Keeps the phone browser's process active while ChatGPT is in the foreground.
 * It does not read browser content, passwords or GitHub credentials.
 */
public class BrowserKeepAliveService extends Service {
    private static final String CHANNEL = "chat_browser_session";

    @Override public void onCreate() {
        super.onCreate();
        NotificationManager manager = getSystemService(NotificationManager.class);
        manager.createNotificationChannel(new NotificationChannel(
                CHANNEL, "Chat browser session", NotificationManager.IMPORTANCE_LOW));
        Notification notification = new Notification.Builder(this, CHANNEL)
                .setSmallIcon(android.R.drawable.ic_menu_view)
                .setContentTitle("Chat Phone Browser")
                .setContentText("Browser listening for GitHub commands")
                .setOngoing(true)
                .build();
        startForeground(8642, notification);
    }

    @Override public int onStartCommand(Intent intent, int flags, int startId) {
        return START_NOT_STICKY;
    }

    @Override public IBinder onBind(Intent intent) { return null; }
}
