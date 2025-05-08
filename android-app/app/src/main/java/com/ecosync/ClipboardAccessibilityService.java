package com.ecosync;

import android.accessibilityservice.AccessibilityService;
import android.accessibilityservice.AccessibilityServiceInfo;
import android.content.ClipData;
import android.content.ClipboardManager;
import android.content.Context;
import android.util.Log;
import android.view.accessibility.AccessibilityEvent;

/**
 * An AccessibilityService to reliably monitor clipboard changes.
 * This service requires explicit user permission from Settings > Accessibility.
 * It listens to accessibility events and checks the clipboard for new content.
 *
 * The configuration for this service (event types, feedback type, etc.)
 * is primarily defined in `res/xml/accessibility_service_config.xml`.
 */
public class ClipboardAccessibilityService extends AccessibilityService {

    private static final String TAG = "ClipboardAccessService";
    private ClipboardManager clipboardManager;
    private CharSequence lastClipboardText = null; // To avoid processing the same content repeatedly

    @Override
    public void onCreate() {
        super.onCreate();
        clipboardManager = (ClipboardManager) getSystemService(Context.CLIPBOARD_SERVICE);
        Log.i(TAG, "ClipboardAccessibilityService created.");
    }

    /**
     * Callback for {@link AccessibilityEvent}s.
     *
     * @param event The new event.
     */
    @Override
    public void onAccessibilityEvent(AccessibilityEvent event) {
        // Logging every event can be very verbose. Uncomment for debugging specific event types.
        // Log.d(TAG, "Event: type=" + AccessibilityEvent.eventTypeToString(event.getEventType()) + ", text=" + event.getText());

        // The actual detection of a "copy" action via accessibility events is complex and heuristic.
        // A simpler, though potentially less immediate, approach is to check the clipboard
        // content when significant UI events occur that *might* involve a copy.
        // The configuration in accessibility_service_config.xml filters the events we receive.

        // Check clipboard content. This might be triggered more often than actual copy events,
        // so we need to compare with the last known content.
        if (clipboardManager != null && clipboardManager.hasPrimaryClip()) {
            ClipData clipData = clipboardManager.getPrimaryClip();
            if (clipData != null && clipData.getItemCount() > 0) {
                CharSequence currentText = clipData.getItemAt(0).getText();
                if (currentText != null && !currentText.equals(lastClipboardText)) {
                    lastClipboardText = currentText;
                    Log.i(TAG, "New clipboard content detected: " + currentText.toString());
                    // TODO: Send this 'currentText' to ClipboardService or a central data handler.
                    //       This handler would then communicate with the Linux server.
                    //       Ensure this communication is efficient and doesn't overwhelm the network or server.
                } else if (currentText == null && lastClipboardText != null) {
                    // Clipboard was cleared or contains non-text data
                    lastClipboardText = null;
                    Log.i(TAG, "Clipboard cleared or non-text content.");
                }
            }
        }
    }

    /**
     * Called when the system wants to interrupt the feedback this service is providing.
     */
    @Override
    public void onInterrupt() {
        Log.w(TAG, "Accessibility service interrupted.");
        // This method is typically used to interrupt speech or haptic feedback.
        // For clipboard monitoring, there might not be specific actions to take here.
    }

    /**
     * Called by the system when it successfully connects to this accessibility service.
     * This is where you can configure the service dynamically if not fully done by XML.
     */
    @Override
    protected void onServiceConnected() {
        super.onServiceConnected();
        // The service is configured via res/xml/accessibility_service_config.xml.
        // If dynamic configuration was needed, it would be done here using AccessibilityServiceInfo.
        // Example (though we use XML):
        // AccessibilityServiceInfo info = getServiceInfo();
        // info.eventTypes = AccessibilityEvent.TYPE_VIEW_TEXT_CHANGED | AccessibilityEvent.TYPE_WINDOW_CONTENT_CHANGED;
        // info.feedbackType = AccessibilityServiceInfo.FEEDBACK_GENERIC;
        // setServiceInfo(info);   
        Log.i(TAG, "ClipboardAccessibilityService connected. Ensure it is enabled in system settings.");
        // TODO: MainActivity should ideally check if this service is enabled and guide the user if not.
    }

    @Override
    public void onDestroy() {
        super.onDestroy();
        Log.i(TAG, "ClipboardAccessibilityService destroyed.");
    }
}
