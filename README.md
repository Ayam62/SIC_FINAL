# EcoSync

![Version](https://img.shields.io/badge/version-0.1.0-blue)
![Python](https://img.shields.io/badge/Python-3.8%2B-brightgreen)
![License](https://img.shields.io/badge/license-MIT-green)

> Create your own ecosystem between Linux and Android devices with seamless, offline integration.

EcoSync enables a unified device experience between your Linux computer and Android device without requiring internet connectivity. Copy, share files, and view notifications across devices with zero friction.

<div align="center">
  <img src="https://via.placeholder.com/800x400?text=EcoSync:+Linux-Android+Integration" alt="EcoSync Banner" width="80%">
</div>

## ✨ Key Features

- 📋 **Clipboard Synchronization** - Copy on one device, paste on another instantly
- 🔔 **Notification Mirroring** - View Android notifications on your Linux desktop
- 📂 **File Transfer** - Send files between devices without cables or internet
- 🔌 **Offline Operation** - Everything works on your local network (Wi-Fi/LAN) only
- 🛡️ **Secure Communication** - Data encrypted during transfer
- 🔄 **Zero-Interaction Workflow** - Set it up once and forget about it

## 🗂️ Project Structure

```
ecosync
├── linux-server
│   ├── src
│   │   ├── main.py              # Main server file
│   │   ├── clipboard.py         # Clipboard synchronization module
│   │   ├── notifications.py     # Notification mirroring module
│   │   ├── filetransfer.py      # File transfer functionality
│   │   ├── discovery.py         # Device discovery via mDNS
│   │   └── utils
│   │       └── encryption.py    # Encryption utilities
│   ├── templates                # Web interface templates
│   ├── requirements.txt         # Python dependencies
│   └── README.md                # Linux server documentation
├── android-app
│   ├── app
│   │   ├── src
│   │   │   ├── main
│   │   │   │   ├── java/com/ecosync
│   │   │   │   │   ├── MainActivity.java
│   │   │   │   │   ├── ClipboardService.java
│   │   │   │   │   ├── NotificationListener.java
│   │   │   │   │   └── FileTransferService.java
│   │   │   │   ├── res
│   │   │   │   │   └── layout
│   │   │   │   └── AndroidManifest.xml
│   │   └── build.gradle
├── shared
│   └── protocol.md             # Shared protocol documentation
└── README.md                   # This file
```

## 🚀 Getting Started

### Prerequisites

- Python 3.8 or higher
- `pip` for installing dependencies
- Linux system with X11/Wayland
- Android device (to use with the Android app or test client)
- Devices must be on the same local network

### Linux Server Setup

1. **Clone the repository**:
   ```bash
   git clone https://github.com/yourusername/ecosync.git
   cd ecosync
   ```

2. **Install dependencies**:
   ```bash
   cd linux-server
   pip install -r requirements.txt
   ```

3. **Run the server**:
   ```bash
   cd src
   python main.py
   ```

### Set up as System Service (Recommended)

For a true "set it and forget it" experience, install as a system service:

1. **Make the installer executable**:
   ```bash
   chmod +x install_service.sh
   ```

2. **Run the installer**:
   ```bash
   ./install_service.sh
   ```

### Android Setup (Coming Soon)

1. Build the app from the `android-app` directory or download the pre-built APK
2. Install on your Android device
3. Open the app and configure the server address
4. Grant required permissions (clipboard, notifications, file storage)

## 📊 How It Works

### Clipboard Synchronization
EcoSync monitors clipboard changes on all connected devices and automatically propagates changes to others, enabling seamless copy-paste between devices.

### Notification Mirroring
Android notifications are captured and sent to your Linux desktop, letting you view and interact with phone notifications without switching devices.

### File Transfer
Send files of any size between devices with simple drag-and-drop or through the integrated file selector. Files are encrypted during transfer.

### Device Discovery
Automatic device discovery via mDNS means you don't need to manually enter IP addresses - devices find each other on the local network.

## 🛡️ Security

- All data is transferred only within your local network
- Communications are encrypted
- No data is stored on external servers
- Paired devices require mutual authentication

## 🛠️ Troubleshooting

### Connection Issues
- Ensure both devices are on the same network
- Check that no firewalls are blocking the connection
- Verify the correct IP address if using manual connection

### Clipboard Not Syncing
- Check that the clipboard service is running
- Try restarting the client application
- Ensure clipboard permission is granted on Android

### Notifications Not Appearing
- Verify notification access is granted on Android
- Check notification settings in the EcoSync app
- Restart the notification service

## 🔮 Future Enhancements

- [ ] URL sharing between devices
- [ ] Remote command execution
- [ ] Screen mirroring/sharing
- [ ] Shared clipboard history
- [ ] Multi-device support (more than two)
- [ ] Bluetooth connectivity option
- [ ] Remote media control

## 👥 Contributing

Contributions are welcome! Here's how you can help:

1. **Fork** the repository
2. **Create** a new feature branch (`git checkout -b feature/amazing-feature`)
3. **Commit** your changes (`git commit -m 'Add amazing feature'`)
4. **Push** to your branch (`git push origin feature/amazing-feature`)
5. **Open** a Pull Request

## 📜 License

This project is licensed under the MIT License - see the LICENSE file for details.

## 🙏 Acknowledgements

- [FastAPI](https://fastapi.tiangolo.com/) - Web framework
- [pyperclip](https://github.com/asweigart/pyperclip) - Cross-platform clipboard functions
- [websockets](https://websockets.readthedocs.io/) - WebSocket implementation
- [zeroconf](https://github.com/jstasiak/python-zeroconf) - mDNS implementation

---

<div align="center">
  <p>Made with ❤️ for seamless device integration</p>
  <p>© 2025 EcoSync Project</p>
</div>