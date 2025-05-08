package com.ecosync;

import android.service.notification.NotificationListenerService;
import android.service.notification.StatusBarNotification;
import android.util.Log;

/**
 * A service that listens for system notifications posted by any application.
 * Requires the {@link android.Manifest.permission#BIND_NOTIFICATION_LISTENER_SERVICE} permission,
 * and the user must explicitly enable this listener in the device's notification settings.
 *
 * Responsibilities:
 * 1. Detecting when new notifications are posted or existing ones are removed.
 * 2. Extracting relevant information from notifications (e.g., app name, title, text).
 * 3. Sending this notification data to the Linux server for mirroring.
 */
public class NotificationListener extends NotificationListenerService {

    private static final String TAG = "NotificationListener";

    /**
     * Called by the system when this service is first created.
     */
    @Override
    public void onCreate() {
        super.onCreate();
        Log.i(TAG, "NotificationListener Service Created");
        // TODO: Initialize any components needed for communication with the server.
    }

    /**
     * Called by the system when a new notification is posted.
     *
     * @param sbn A {@link StatusBarNotification} object containing all the notification details.
     */
    @Override
    public void onNotificationPosted(StatusBarNotification sbn) {
        if (sbn == null) return;

        String packageName = sbn.getPackageName();
        // Consider filtering out notifications from this app itself or system apps if desired.
        // String appName = sbn.getApplicationInfo().loadLabel(getPackageManager()).toString(); // Requires API 30 for getApplicationInfo
        // For broader compatibility for app name:
        // android.app.Notification notification = sbn.getNotification();
        // String title = notification.extras.getString(android.app.Notification.EXTRA_TITLE);
        // CharSequence text = notification.extras.getCharSequence(android.app.Notification.EXTRA_TEXT);

        Log.i(TAG, "Notification Posted: Package=" + packageName +
                ", ID=" + sbn.getId() +
                ", Ticker=" + (sbn.getNotification().tickerText != null ? sbn.getNotification().tickerText : "N/A"));

        // TODO: Extract more details: title, text, subText, icon, actions, etc.
        // TODO: Format the notification data (e.g., into JSON).
        // TODO: Send the formatted data to the Linux server via a network service/handler.
        // TODO: Implement a strategy to avoid sending duplicate or overly frequent notifications if needed.
    }

    /**
     * Called by the system when a notification is removed.
     *
     * @param sbn A {@link StatusBarNotification} object representing the removed notification.
     */
    @Override
    public void onNotificationRemoved(StatusBarNotification sbn) {
        if (sbn == null) return;

        Log.i(TAG, "Notification Removed: Package=" + sbn.getPackageName() + ", ID=" + sbn.getId());
        // TODO: Determine if information about removed notifications needs to be sent to the server.
        //       This might be useful for dismissing mirrored notifications on the desktop.
    }

    /**
     * Called by the system when the service is no longer used and is being destroyed.
     */
    @Override
    public void onDestroy() {
        super.onDestroy();
        Log.i(TAG, "NotificationListener Service Destroyed");
        // TODO: Clean up any resources, like network connections.
    }
}