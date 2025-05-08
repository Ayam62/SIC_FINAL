package com.ecosync;

import android.app.Activity;
import android.os.Bundle;
import android.widget.TextView;

/**
 * The main entry point Activity for the EcoSync application.
 * This Activity is launched when the user opens the app.
 * It will be responsible for displaying the main UI, allowing users to manage services,
 * initiate actions like file transfers, and navigate to settings or permission requests.
 */
public class MainActivity extends Activity {

    /**
     * Called when the activity is first created.
     * This is where you should do all of your normal static set up: create views,
     * bind data to lists, etc. This method also provides you with a Bundle containing
     * the activity's previously frozen state, if there was one.
     *
     * @param savedInstanceState If the activity is being re-initialized after
     *     previously being shut down then this Bundle contains the data it most
     *     recently supplied in onSaveInstanceState(Bundle). Otherwise it is null.
     */
    @Override
    protected void onCreate(Bundle savedInstanceState) {
        super.onCreate(savedInstanceState); // Always call the superclass method first

        // Set a simple TextView as the content view for now.
        // This will be replaced by a more complex layout defined in an XML file (e.g., res/layout/activity_main.xml).
        TextView textView = new TextView(this);
        textView.setText("EcoSync App - Welcome!");
        setContentView(textView);

        // TODO: Initialize UI elements from an XML layout file (e.g., using findViewById or ViewBinding).
        // TODO: Implement UI logic: buttons for starting/stopping services, status indicators, etc.
        // TODO: Implement runtime permission requests for Notification Access, Accessibility Service, Storage, etc.
        //       Guide users to the respective system settings if needed.
    }

    // Additional lifecycle methods (onStart, onResume, onPause, onStop, onDestroy) can be overridden here
    // to manage resources and app state.

    // Methods for handling user interactions (e.g., button clicks) will also be added here.
}