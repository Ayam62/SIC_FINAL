# EcoSync Android App Developer Guide

Welcome to the Android client for EcoSync! This guide is intended for developers looking to understand, build, and contribute to the EcoSync Android application.

## 1. Introduction

The EcoSync Android app is a key component of the EcoSync project, designed to seamlessly integrate your Android device with your Linux computer. It enables features like clipboard synchronization, notification mirroring, and file transfer, all operating over your local network without internet dependency.

## 2. Project Structure

The Android app is a standard Gradle-based project. Here's an overview of the important files and directories within `android-app/`:

```
android-app/
├── app/
│   ├── build.gradle                # App-level Gradle build script: Manages dependencies, SDK versions, and build settings.
│   ├── src/
│   │   ├── main/
│   │   │   ├── AndroidManifest.xml     # Core configuration file: Declares app components, permissions, and features.
│   │   │   ├── java/com/ecosync/       # Main directory for all Java source code.
│   │   │   │   ├── MainActivity.java   # The primary screen (Activity) users see when they launch the app.
│   │   │   │   ├── ClipboardService.java # Background service to manage clipboard data synchronization.
│   │   │   │   ├── NotificationListener.java # Service to listen for system notifications and relay them.
│   │   │   │   ├── FileTransferService.java # Service to handle sending and receiving files.
│   │   │   │   └── ClipboardAccessibilityService.java # Accessibility service for reliable clipboard monitoring.
│   │   │   ├── res/                    # Resource directory for all non-code assets.
│   │   │   │   ├── layout/             # XML files defining the User Interface (UI) for Activities.
│   │   │   │   ├── xml/                # XML configuration files (e.g., for the accessibility service).
│   │   │   │   ├── values/             # XML files for strings, colors, dimensions, styles, themes. (Standard - create as needed)
│   │   │   │   └── mipmap/             # Launcher icons for different screen densities. (Standard - create as needed)
│   │   └── ... (other build-related files and directories)
└── README.md                       # This file.
```

## 3. Core Functionality and Code Flow

The app is built around several key Android components, primarily Services, to perform tasks in the background.

### 3.1. Clipboard Synchronization
-   **Detection**: The `ClipboardAccessibilityService` is crucial for reliably detecting clipboard changes in the background, especially on newer Android versions. It listens for specific accessibility events that often correlate with copy actions.
    -   *User Action*: The user must manually enable this service in Android Settings > Accessibility.
-   **Processing & Communication**: Once a change is detected (or the app sets new clipboard content), the `ClipboardAccessibilityService` can notify the `ClipboardService`.
-   `ClipboardService` (a Foreground Service) will be responsible for:
    -   Getting the actual clipboard content.
    -   Sending the content to the Linux server via the local network.
    -   Receiving clipboard content from the server and updating the Android clipboard using `ClipboardManager`.

### 3.2. Notification Mirroring
-   **Listening**: `NotificationListener` (extends `NotificationListenerService`) is a system service that, once enabled by the user, receives callbacks when notifications are posted or removed.
    -   *User Action*: The user must grant "Notification Access" permission to the app in Android Settings.
-   **Relaying**: When `onNotificationPosted()` is called, this service extracts relevant information (app name, title, text) from the `StatusBarNotification` object.
-   It then sends this information to the Linux server.

### 3.3. File Transfer
-   `FileTransferService` (likely a Foreground Service) will manage the sending and receiving of files.
-   **Sending**: The user might select a file through `MainActivity`. The path or content URI will be passed to this service, which then handles the streaming of data to the Linux server.
-   **Receiving**: The service will listen for incoming file transfer requests from the server, save the file to the device's storage, and potentially notify the user.

### 3.4. Main User Interface (`MainActivity.java`)
-   This is the entry point for the user.
-   Its responsibilities include:
    -   Displaying the app's status (e.g., connection to server, service status).
    -   Providing UI elements (buttons, switches) to:
        -   Start/stop services.
        -   Initiate file transfers.
        -   Guide the user to enable necessary permissions (Notification Access, Accessibility Service).
        -   Configure server connection details (if not using mDNS or if mDNS fails).

## 4. Key Android Concepts Utilized

-   **Activities (`android.app.Activity`)**: Provide the user interface. `MainActivity` is the primary example.
-   **Services (`android.app.Service`)**: Perform long-running operations in the background without a UI.
    -   **Foreground Services**: Services that the user is actively aware of (e.g., music player, ongoing file download). They show a persistent notification. `ClipboardService` and `FileTransferService` will likely be foreground services.
    -   **Background Services**: Services that perform work not directly noticed by the user. Subject to more restrictions on newer Android versions.
    -   **Accessibility Services (`android.accessibilityservice.AccessibilityService`)**: Specialized services to assist users with disabilities. With user permission, they can monitor system-wide events, making `ClipboardAccessibilityService` vital for clipboard monitoring.
    -   **Notification Listener Service (`android.service.notification.NotificationListenerService`)**: A special service to receive system notifications.
-   **`AndroidManifest.xml`**: The app's "Table of Contents." It declares all Activities, Services, permissions, and other essential metadata.
-   **`build.gradle`**: The build configuration script. It defines how the app is compiled, what libraries (dependencies) it uses, SDK versions, and more.
-   **Permissions**: The app requests permissions in `AndroidManifest.xml` (e.g., `INTERNET`, `BIND_ACCESSIBILITY_SERVICE`, `BIND_NOTIFICATION_LISTENER_SERVICE`). Some sensitive permissions also require runtime requests or direct user enablement in settings.
-   **UI Layouts (XML)**: Located in `res/layout/`, these XML files define the structure and appearance of the app's user interface.
-   **Resources (`res/`)**: Contains all non-code assets like layouts, strings (for localization), images, colors, styles.

## 5. Setting Up Your Development Environment

1.  **Install Android Studio**: The official IDE for Android development. Download it from [developer.android.com/studio](https://developer.android.com/studio).
2.  **Import the Project**:
    -   Open Android Studio.
    -   Select "Open" or "Import Project".
    -   Navigate to the `ecosync/android-app` directory and select it.
    -   Android Studio will use the `build.gradle` file to set up the project.
3.  **SDK Versions**:
    -   `compileSdk` (e.g., 34): The API level the app is compiled against.
    -   `minSdk` (e.g., 21): The minimum Android version the app supports.
    -   `targetSdk` (e.g., 34): The API level the app is designed and tested for.
    These are defined in `android-app/app/build.gradle`. Ensure you have the required Android SDK Platform installed via Android Studio's SDK Manager.

## 6. Building and Running the App

1.  **Connect a Device or Start an Emulator**:
    -   **Physical Device**: Enable Developer Options and USB Debugging on your Android device, then connect it to your computer.
    -   **Emulator**: Create and start an Android Virtual Device (AVD) using the AVD Manager in Android Studio.
2.  **Build and Run**:
    -   In Android Studio, select your device/emulator from the target device dropdown.
    -   Click the "Run" button (green play icon) or use the menu: `Run > Run 'app'`.
    -   Android Studio will build the APK and install it on the target.
3.  **Enable Permissions**:
    -   **Notification Access**: The app (likely `MainActivity`) should guide you to Settings > Apps & notifications > Special app access > Notification access to enable it for EcoSync.
    -   **Accessibility Service**: Similarly, navigate to Settings > Accessibility > Installed services (or similar path depending on Android version/OEM) and enable `EcoSync Clipboard Service`.
    -   Other permissions (like Storage for file transfer) might be requested at runtime.

## 7. How to Contribute & Next Steps

-   **Review TODOs**: Look for `// TODO:` comments in the Java files. These mark areas that need implementation or improvement.
-   **Implement Core Logic**:
    -   Flesh out the networking code in the services to communicate with the Linux server (e.g., using WebSockets or a simple HTTP client like OkHttp).
    -   Refine the clipboard detection logic in `ClipboardAccessibilityService`.
    -   Build the UI in `MainActivity` to control services and display status.
    -   Implement file selection and transfer mechanisms.
-   **Testing**: Write unit tests and instrumented tests to ensure reliability.
-   **Debugging**: Use Android Studio's debugger, Logcat (for viewing app logs: `Log.d(TAG, "message")`), and Layout Inspector to troubleshoot issues.

We hope this guide helps you get started with the EcoSync Android app development!
