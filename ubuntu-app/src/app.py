#!/usr/bin/env python3
"""
SIC Ubuntu Desktop Application
Main entry point for the Ubuntu desktop application that integrates with
the backend server to provide clipboard synchronization, notification mirroring,
and file transfer capabilities between Linux and Android devices.
"""

import os
import sys
import json
import signal
import socket
import logging
import threading
import subprocess
import websocket
import time
from pathlib import Path
import gi

gi.require_version('Gtk', '3.0')
gi.require_version('Notify', '0.7')
from gi.repository import Gtk, GLib, Gdk, GdkPixbuf, Notify, Gio, Pango

# Set up paths
APP_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = APP_DIR.parent.parent
SERVER_DIR = PROJECT_ROOT / "linux-server"
RESOURCES_DIR = APP_DIR.parent / "resources"

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger("sic-ubuntu-app")

class SICApplication(Gtk.Application):
    """Main application class for the SIC Ubuntu App"""
    
    def __init__(self):
        super().__init__(application_id="com.sic.ubuntu",
                         flags=Gio.ApplicationFlags.FLAGS_NONE)
        self.window = None
        self.server_process = None
        self.ws_client = None
        self.connected = False
        self.device_id = None
        self.paired_devices = {}
        self.active_transfers = {}
        self.settings = {
            "clipboard_sync": True,
            "notification_mirroring": True,
            "auto_reconnect": True
        }
        self.reconnect_attempts = 0
        self.max_reconnect_attempts = 10
        self.heartbeat_timer = None
        self.current_pairing_code = None  # Store current pairing code to prevent changes
        
        # Initialize notification system
        Notify.init("SIC Ubuntu")
        
    def do_activate(self):
        """Activate the application"""
        # We only allow a single window
        if not self.window:
            # Create the main window
            self.window = SICMainWindow(application=self)
            
        self.window.present()
        
        # Start the server in the background
        self.start_server()
        
        # Connect to the server
        self.connect_to_server()
        
    def do_startup(self):
        """Startup signal handler"""
        Gtk.Application.do_startup(self)
        
        # Handle keyboard shortcuts
        self.setup_actions()
        
    def setup_actions(self):
        """Set up application actions and keyboard shortcuts"""
        # Quit action (Ctrl+Q)
        quit_action = Gio.SimpleAction.new("quit", None)
        quit_action.connect("activate", self.on_quit)
        self.add_action(quit_action)
        self.set_accels_for_action("app.quit", ["<Ctrl>Q"])
        
        # Refresh action (F5)
        refresh_action = Gio.SimpleAction.new("refresh", None)
        refresh_action.connect("activate", self.on_refresh)
        self.add_action(refresh_action)
        self.set_accels_for_action("app.refresh", ["F5"])
    
    def start_server(self):
        """Start the backend server as a subprocess"""
        if self.server_process and self.server_process.poll() is None:
            logger.info("Server is already running")
            return
            
        try:
            logger.info("Starting server...")
            # Use the Python interpreter from the virtual environment
            python_executable = str(PROJECT_ROOT / "venv_with_system_site" / "bin" / "python")
            
            cmd = [python_executable, str(SERVER_DIR / "serve.py"), 
                   "--host", "0.0.0.0",  # Listen on all interfaces so it's accessible over the network
                   "--port", "8000",
                   "--generate-qr"]  # Add the flag to generate QR code and output pairing code
            
            # Start server without opening a browser window
            env = os.environ.copy()
            env["SIC_HEADLESS"] = "1"  # Custom env var to indicate headless mode
            
            # Log the command being executed for debugging
            logger.info(f"Executing: {' '.join(cmd)}")
            
            self.server_process = subprocess.Popen(
                cmd, 
                env=env,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                universal_newlines=True
            )
            
            # Start a thread to read server output
            threading.Thread(
                target=self.monitor_server_output,
                args=(self.server_process,),
                daemon=True
            ).start()
            
            logger.info(f"Server started with PID {self.server_process.pid}")
            self.window.update_status("Server started", "success")
        except Exception as e:
            logger.error(f"Failed to start server: {e}")
            self.window.update_status(f"Server error: {e}", "error")
    
    def monitor_server_output(self, process):
        """Monitor and log server output"""
        for line in iter(process.stdout.readline, ''):
            line = line.strip()
            if line:
                if "ERROR" in line.upper() or "EXCEPTION" in line.upper():
                    logger.error(f"Server: {line}")
                else:
                    logger.info(f"Server: {line}")
                    
                # Look for the pairing code in the output - make pattern more flexible
                if "pairing code" in line.lower() or "pairingcode" in line.lower():
                    try:
                        # Extract pairing code (handle different formats)
                        if ":" in line:
                            pairing_code = line.split(":")[-1].strip()
                        else:
                            # Try to find the code as a 6-character alphanumeric string
                            import re
                            match = re.search(r"[A-Z0-9]{6}", line)
                            if match:
                                pairing_code = match.group(0)
                            else:
                                continue  # No valid code found in this line
                                
                        logger.info(f"Found pairing code: {pairing_code}")
                        self.current_pairing_code = pairing_code  # Store pairing code
                        GLib.idle_add(self.window.update_pairing_code, pairing_code)
                    except Exception as e:
                        logger.error(f"Error extracting pairing code: {e}")
        
        # Process has ended
        logger.warning("Server process has terminated")
        GLib.idle_add(self.window.update_status, "Server stopped", "warning")
        
        # Attempt to restart if needed
        if self.settings["auto_reconnect"]:
            logger.info("Attempting to restart server...")
            GLib.idle_add(self.start_server)
    
    def connect_to_server(self):
        """Connect to the WebSocket server"""
        threading.Thread(target=self._connect_ws, daemon=True).start()
    
    def _connect_ws(self):
        """WebSocket connection in a separate thread"""
        try:
            # Close existing connection if any
            if self.ws_client:
                self.ws_client.close()
            
            # Add a small delay to ensure server is ready
            time.sleep(2)
            
            # Use local IP address for better connectivity
            host = "localhost"
            port = 8000
            
            # Try to get local IP address for better connectivity
            try:
                # Get local IP by creating a temporary socket
                s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
                # Connect to any external IP to determine which interface to use
                s.connect(("8.8.8.8", 80))
                host = s.getsockname()[0]
                s.close()
                logger.info(f"Using local IP: {host}")
            except Exception as e:
                logger.warning(f"Could not determine local IP, using localhost: {e}")
            
            # Connect to WebSocket server
            ws_url = f"ws://{host}:{port}/ws/my-phone"
            logger.info(f"Connecting to WebSocket at: {ws_url}")
            
            # Create WebSocket with improved options
            self.ws_client = websocket.WebSocketApp(
                ws_url,
                on_open=self.on_ws_open,
                on_message=self.on_ws_message,
                on_error=self.on_ws_error,
                on_close=self.on_ws_close
            )
            
            # Configure WebSocket connection with improved settings
            self.ws_client.run_forever(
                ping_interval=15,       # Reduced from 30 seconds for more responsive detection
                ping_timeout=5,         # Reduced from 10 seconds
                reconnect=self.settings["auto_reconnect"],
                skip_utf8_validation=True  # For better performance
            )
            
            logger.info("WebSocket connection thread started")
            GLib.idle_add(self.window.update_status, "Connecting...", "info")
        except Exception as e:
            logger.error(f"WebSocket connection error: {e}")
            GLib.idle_add(self.window.update_status, f"Connection error: {e}", "error")
            
            # Attempt to reconnect with exponential backoff
            if self.settings["auto_reconnect"] and self.reconnect_attempts < self.max_reconnect_attempts:
                delay = min(30, 2 ** self.reconnect_attempts)  # Exponential backoff with 30s max
                logger.info(f"Reconnecting in {delay}s (attempt {self.reconnect_attempts + 1}/{self.max_reconnect_attempts})")
                self.reconnect_attempts += 1
                threading.Timer(delay, self.connect_to_server).start()
    
    def on_ws_open(self, ws):
        """WebSocket connection opened"""
        logger.info("WebSocket connected")
        self.connected = True
        self.reconnect_attempts = 0
        
        # Start heartbeat timer
        self.start_heartbeat(ws)
        
        # Update UI in the main thread
        GLib.idle_add(self.window.update_status, "Connected", "success")
        
        # Request initial status
        ws.send(json.dumps({
            "type": "admin_request",
            "action": "get_status"
        }))
    
    def start_heartbeat(self, ws):
        """Start WebSocket heartbeat"""
        def send_ping():
            if self.connected and self.ws_client:
                try:
                    ws.send(json.dumps({"type": "ping"}))
                    logger.debug("Sent heartbeat ping")
                    # Schedule next heartbeat
                    self.heartbeat_timer = threading.Timer(30.0, send_ping)
                    self.heartbeat_timer.daemon = True
                    self.heartbeat_timer.start()
                except Exception as e:
                    logger.error(f"Error sending heartbeat ping: {e}")
                    self.stop_heartbeat()
        
        # Start initial heartbeat
        self.heartbeat_timer = threading.Timer(30.0, send_ping)
        self.heartbeat_timer.daemon = True
        self.heartbeat_timer.start()
    
    def stop_heartbeat(self):
        """Stop WebSocket heartbeat"""
        if self.heartbeat_timer:
            self.heartbeat_timer.cancel()
            self.heartbeat_timer = None
            logger.debug("Stopped heartbeat timer")
    
    def on_ws_message(self, ws, message):
        """WebSocket message received"""
        try:
            data = json.loads(message)
            logger.debug(f"Received: {data}")
            
            # Handle different message types
            if data.get("type") == "status_update":
                GLib.idle_add(self.window.update_devices, data.get("devices", []))
                GLib.idle_add(self.window.update_transfers, data.get("transfers", {}))
            
            elif data.get("type") == "device_connected":
                GLib.idle_add(self.window.update_status, "Device connected", "success")
                # Request updated device list
                ws.send(json.dumps({
                    "type": "admin_request",
                    "action": "get_devices"
                }))
            
            elif data.get("type") == "device_disconnected":
                GLib.idle_add(self.window.update_status, "Device disconnected", "warning")
                # Request updated device list
                ws.send(json.dumps({
                    "type": "admin_request",
                    "action": "get_devices"
                }))
            
            elif data.get("type") == "transfer_update":
                GLib.idle_add(self.window.update_transfer, data.get("transfer", {}))
            
            elif data.get("type") == "clipboard_sync":
                if self.settings["clipboard_sync"]:
                    text = data.get("text", "")
                    if text:
                        # Set clipboard text
                        GLib.idle_add(self.set_clipboard_text, text)
            
            elif data.get("type") == "notification":
                if self.settings["notification_mirroring"]:
                    # Display notification
                    app_name = data.get("app_name", "Android")
                    summary = data.get("summary", "Notification")
                    body = data.get("body", "")
                    GLib.idle_add(self.show_notification, app_name, summary, body)
            
            elif data.get("type") == "pong":
                logger.debug("Received heartbeat pong")
        
        except Exception as e:
            logger.error(f"Error processing message: {e}")
    
    def on_ws_error(self, ws, error):
        """WebSocket error handler"""
        logger.error(f"WebSocket error: {error}")
        self.connected = False
        self.stop_heartbeat()
        GLib.idle_add(self.window.update_status, f"Connection error: {error}", "error")
    
    def on_ws_close(self, ws, close_status_code, close_msg):
        """WebSocket connection closed"""
        logger.warning(f"WebSocket connection closed: {close_status_code} {close_msg}")
        self.connected = False
        self.stop_heartbeat()
        GLib.idle_add(self.window.update_status, "Disconnected", "warning")
        
        # Attempt to reconnect if auto-reconnect is enabled
        if self.settings["auto_reconnect"] and self.reconnect_attempts < self.max_reconnect_attempts:
            delay = min(30, 2 ** self.reconnect_attempts)  # Exponential backoff with 30s max
            logger.info(f"Reconnecting in {delay}s (attempt {self.reconnect_attempts + 1}/{self.max_reconnect_attempts})")
            self.reconnect_attempts += 1
            threading.Timer(delay, self.connect_to_server).start()
        elif self.reconnect_attempts >= self.max_reconnect_attempts:
            logger.error(f"Max reconnection attempts ({self.max_reconnect_attempts}) reached")
            GLib.idle_add(self.window.update_status, "Connection failed - restart app", "error")
    
    def send_message(self, message):
        """Send a message to the WebSocket server"""
        if not self.connected or not self.ws_client:
            logger.warning("Cannot send message, not connected")
            return False
            
        try:
            self.ws_client.send(json.dumps(message))
            return True
        except Exception as e:
            logger.error(f"Error sending message: {e}")
            return False
    
    def set_clipboard_text(self, text):
        """Set the clipboard text"""
        clipboard = Gtk.Clipboard.get(Gdk.SELECTION_CLIPBOARD)
        clipboard.set_text(text, -1)
        clipboard.store()
    
    def show_notification(self, app_name, summary, body):
        """Show a system notification"""
        notification = Notify.Notification.new(
            summary,
            body,
            "dialog-information"
        )
        notification.show()
    
    def on_quit(self, action, param):
        """Handle quit action"""
        self.quit()
    
    def on_refresh(self, action, param):
        """Handle refresh action"""
        if self.connected:
            self.send_message({
                "type": "admin_request",
                "action": "get_status"
            })
            self.window.update_status("Refreshing...", "info")
    
    def do_shutdown(self):
        """Shutdown the application"""
        logger.info("Shutting down application")
        
        # Close WebSocket connection
        if self.ws_client:
            self.ws_client.close()
        
        # Stop the server process
        if self.server_process and self.server_process.poll() is None:
            logger.info("Stopping server...")
            try:
                self.server_process.terminate()
                self.server_process.wait(timeout=2)
            except subprocess.TimeoutExpired:
                logger.warning("Server did not terminate gracefully, killing")
                self.server_process.kill()
        
        # Stop heartbeat timer
        self.stop_heartbeat()
        
        # Clean up notifications
        Notify.uninit()
        
        Gtk.Application.do_shutdown(self)


class SICMainWindow(Gtk.ApplicationWindow):
    """Main application window"""
    
    def __init__(self, application):
        super().__init__(
            application=application,
            title="SIC",
            default_width=800,
            default_height=600
        )
        
        self.app = application
        self.setup_ui()
    
    def setup_ui(self):
        """Set up the user interface"""
        # Use a header bar
        header = Gtk.HeaderBar()
        header.set_show_close_button(True)
        header.props.title = "SIC"
        self.set_titlebar(header)
        
        # Add refresh button to header
        refresh_button = Gtk.Button()
        refresh_icon = Gio.ThemedIcon(name="view-refresh-symbolic")
        refresh_image = Gtk.Image.new_from_gicon(refresh_icon, Gtk.IconSize.BUTTON)
        refresh_button.add(refresh_image)
        refresh_button.connect("clicked", self.on_refresh_clicked)
        header.pack_start(refresh_button)
        
        # Status indicator in header
        self.status_label = Gtk.Label(label="Starting...")
        self.status_label.get_style_context().add_class("status-info")
        header.pack_end(self.status_label)
        
        # Main layout - Notebook with tabs
        self.notebook = Gtk.Notebook()
        self.add(self.notebook)
        
        # Create tabs
        self.create_pairing_tab()
        self.create_devices_tab()
        self.create_transfers_tab()
        self.create_settings_tab()
        
        # Apply CSS styling
        self.apply_css()
        
        # Show all widgets
        self.show_all()
    
    def create_pairing_tab(self):
        """Create the pairing tab"""
        # Main container for the tab
        pairing_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=10)
        pairing_box.set_border_width(20)
        
        # Create card-like container
        card = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=10)
        card.get_style_context().add_class("card")
        pairing_box.pack_start(card, True, True, 0)
        
        # Card header
        header = Gtk.Label(label="Pair a new device")
        header.get_style_context().add_class("card-header")
        header.set_halign(Gtk.Align.START)
        card.pack_start(header, False, False, 0)
        
        # Instructions
        instructions = Gtk.Label(
            label="To connect your Android device, open the SIC app and scan the QR code or enter the pairing code:"
        )
        instructions.set_line_wrap(True)
        instructions.set_halign(Gtk.Align.START)
        card.pack_start(instructions, False, False, 0)
        
        # QR code placeholder (will be populated later)
        self.qr_image = Gtk.Image()
        self.qr_image.set_size_request(200, 200)
        qr_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=5)
        qr_box.set_halign(Gtk.Align.CENTER)
        qr_box.pack_start(self.qr_image, False, False, 0)
        card.pack_start(qr_box, False, False, 0)
        
        # Pairing code
        code_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=5)
        code_box.set_halign(Gtk.Align.CENTER)
        
        code_label = Gtk.Label(label="Pairing code:")
        code_box.pack_start(code_label, False, False, 0)
        
        self.pairing_code_label = Gtk.Label(label="Loading...")
        self.pairing_code_label.get_style_context().add_class("code")
        code_box.pack_start(self.pairing_code_label, False, False, 0)
        
        card.pack_start(code_box, False, False, 0)
        
        # Device info
        device_id_file = SERVER_DIR / ".device_id"
        device_id = "Unknown"
        if device_id_file.exists():
            with open(device_id_file, "r") as f:
                device_id = f.read().strip()
        
        info_box = Gtk.Grid()
        info_box.set_column_spacing(10)
        info_box.set_row_spacing(5)
        
        # Device ID
        id_label = Gtk.Label(label="Device ID:")
        id_label.set_halign(Gtk.Align.START)
        id_label.get_style_context().add_class("info-label")
        info_box.attach(id_label, 0, 0, 1, 1)
        
        id_value = Gtk.Label(label=device_id)
        id_value.set_halign(Gtk.Align.START)
        id_value.set_selectable(True)
        info_box.attach(id_value, 1, 0, 1, 1)
        
        # Hostname
        hostname_label = Gtk.Label(label="Hostname:")
        hostname_label.set_halign(Gtk.Align.START)
        hostname_label.get_style_context().add_class("info-label")
        info_box.attach(hostname_label, 0, 1, 1, 1)
        
        hostname_value = Gtk.Label(label=socket.gethostname())
        hostname_value.set_halign(Gtk.Align.START)
        info_box.attach(hostname_value, 1, 1, 1, 1)
        
        card.pack_start(info_box, False, False, 10)
        
        # Add to notebook
        pairing_label = Gtk.Label(label="Pairing")
        self.notebook.append_page(pairing_box, pairing_label)
    
    def create_devices_tab(self):
        """Create the devices tab"""
        # Main container for the tab
        devices_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=10)
        devices_box.set_border_width(20)
        
        # Create card-like container
        card = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=10)
        card.get_style_context().add_class("card")
        devices_box.pack_start(card, True, True, 0)
        
        # Card header
        header = Gtk.Label(label="Connected Devices")
        header.get_style_context().add_class("card-header")
        header.set_halign(Gtk.Align.START)
        card.pack_start(header, False, False, 0)
        
        # Scrolled window for device list
        scrolled = Gtk.ScrolledWindow()
        scrolled.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)
        scrolled.set_min_content_height(200)
        
        # List box for devices
        self.devices_list = Gtk.ListBox()
        self.devices_list.set_selection_mode(Gtk.SelectionMode.NONE)
        
        # Add a placeholder message
        placeholder = Gtk.Label(label="No devices connected")
        placeholder.set_padding(10, 10)
        self.devices_list.add(placeholder)
        
        scrolled.add(self.devices_list)
        card.pack_start(scrolled, True, True, 0)
        
        # Add to notebook
        devices_label = Gtk.Label(label="Devices")
        self.notebook.append_page(devices_box, devices_label)
    
    def create_transfers_tab(self):
        """Create the file transfers tab"""
        # Main container for the tab
        transfers_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=10)
        transfers_box.set_border_width(20)
        
        # Create card-like container
        card = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=10)
        card.get_style_context().add_class("card")
        transfers_box.pack_start(card, True, True, 0)
        
        # Card header
        header_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=10)
        
        header = Gtk.Label(label="File Transfers")
        header.get_style_context().add_class("card-header")
        header.set_halign(Gtk.Align.START)
        header_box.pack_start(header, True, True, 0)
        
        # Send file button
        send_button = Gtk.Button(label="Send File")
        send_button.connect("clicked", self.on_send_file_clicked)
        header_box.pack_end(send_button, False, False, 0)
        
        card.pack_start(header_box, False, False, 0)
        
        # Scrolled window for transfers list
        scrolled = Gtk.ScrolledWindow()
        scrolled.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)
        scrolled.set_min_content_height(200)
        
        # Box for active transfers
        self.transfers_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=10)
        
        # Add a placeholder message
        placeholder = Gtk.Label(label="No active transfers")
        placeholder.set_padding(10, 10)
        self.transfers_box.pack_start(placeholder, False, False, 0)
        
        scrolled.add(self.transfers_box)
        card.pack_start(scrolled, True, True, 0)
        
        # Add to notebook
        transfers_label = Gtk.Label(label="Transfers")
        self.notebook.append_page(transfers_box, transfers_label)
    
    def create_settings_tab(self):
        """Create the settings tab"""
        # Main container for the tab
        settings_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=10)
        settings_box.set_border_width(20)
        
        # Create card-like container
        card = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=10)
        card.get_style_context().add_class("card")
        settings_box.pack_start(card, True, True, 0)
        
        # Card header
        header = Gtk.Label(label="Settings")
        header.get_style_context().add_class("card-header")
        header.set_halign(Gtk.Align.START)
        card.pack_start(header, False, False, 0)
        
        # Settings grid
        grid = Gtk.Grid()
        grid.set_column_spacing(10)
        grid.set_row_spacing(10)
        
        # Clipboard sync setting
        clipboard_label = Gtk.Label(label="Clipboard Sync:")
        clipboard_label.set_halign(Gtk.Align.START)
        grid.attach(clipboard_label, 0, 0, 1, 1)
        
        clipboard_switch = Gtk.Switch()
        clipboard_switch.set_active(self.app.settings["clipboard_sync"])
        clipboard_switch.connect("notify::active", self.on_clipboard_switch_toggled)
        clipboard_switch.set_halign(Gtk.Align.END)
        grid.attach(clipboard_switch, 1, 0, 1, 1)
        
        # Notification mirroring setting
        notification_label = Gtk.Label(label="Notification Mirroring:")
        notification_label.set_halign(Gtk.Align.START)
        grid.attach(notification_label, 0, 1, 1, 1)
        
        notification_switch = Gtk.Switch()
        notification_switch.set_active(self.app.settings["notification_mirroring"])
        notification_switch.connect("notify::active", self.on_notification_switch_toggled)
        notification_switch.set_halign(Gtk.Align.END)
        grid.attach(notification_switch, 1, 1, 1, 1)
        
        # Auto reconnect setting
        reconnect_label = Gtk.Label(label="Auto Reconnect:")
        reconnect_label.set_halign(Gtk.Align.START)
        grid.attach(reconnect_label, 0, 2, 1, 1)
        
        reconnect_switch = Gtk.Switch()
        reconnect_switch.set_active(self.app.settings["auto_reconnect"])
        reconnect_switch.connect("notify::active", self.on_reconnect_switch_toggled)
        reconnect_switch.set_halign(Gtk.Align.END)
        grid.attach(reconnect_switch, 1, 2, 1, 1)
        
        card.pack_start(grid, False, False, 10)
        
        # Add to notebook
        settings_label = Gtk.Label(label="Settings")
        self.notebook.append_page(settings_box, settings_label)
    
    def apply_css(self):
        """Apply CSS styling to the window"""
        css_provider = Gtk.CssProvider()
        css = """
            .card {
                border: 1px solid alpha(currentColor, 0.2);
                border-radius: 6px;
                padding: 15px;
                background-color: alpha(currentColor, 0.05);
            }
            .card-header {
                font-weight: bold;
                font-size: 18px;
                border-bottom: 1px solid alpha(currentColor, 0.1);
                padding-bottom: 10px;
                margin-bottom: 10px;
            }
            .code {
                font-family: monospace;
                background-color: alpha(currentColor, 0.07);
                padding: 6px;
                border-radius: 4px;
            }
            .info-label {
                font-weight: bold;
            }
            .status-info {
                color: #2196F3;
            }
            .status-success {
                color: #4CAF50;
            }
            .status-warning {
                color: #FF9800;
            }
            .status-error {
                color: #F44336;
            }
            .device-row {
                padding: 8px;
                border-bottom: 1px solid alpha(currentColor, 0.1);
            }
            .transfer-card {
                border: 1px solid alpha(currentColor, 0.1);
                border-radius: 4px;
                padding: 10px;
                margin-bottom: 8px;
            }
        """
        css_provider.load_from_data(css.encode())
        
        Gtk.StyleContext.add_provider_for_screen(
            Gdk.Screen.get_default(),
            css_provider,
            Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION
        )
    
    def update_status(self, message, status_type="info"):
        """Update the status message"""
        self.status_label.set_text(message)
        
        # Remove existing status classes
        context = self.status_label.get_style_context()
        for status in ["info", "success", "warning", "error"]:
            context.remove_class(f"status-{status}")
        
        # Add appropriate status class
        context.add_class(f"status-{status_type}")
    
    def update_pairing_code(self, code):
        """Update the pairing code display"""
        self.pairing_code_label.set_text(code)
        
        # Generate a QR code if possible
        try:
            from qrcode import QRCode
            import io
            from PIL import Image
            
            # Generate QR code
            device_id_file = SERVER_DIR / ".device_id"
            device_id = "unknown"
            if device_id_file.exists():
                with open(device_id_file, "r") as f:
                    device_id = f.read().strip()
            
            qr = QRCode(version=1, box_size=10, border=4)
            qr.add_data(f"sic://{device_id}/{code}")
            qr.make(fit=True)
            
            # Create PIL image
            img = qr.make_image(fill_color="black", back_color="white")
            
            # Convert PIL image to GdkPixbuf
            data = io.BytesIO()
            img.save(data, format='PNG')
            data.seek(0)
            loader = GdkPixbuf.PixbufLoader.new_with_type('png')
            loader.write(data.read())
            loader.close()
            
            pixbuf = loader.get_pixbuf()
            self.qr_image.set_from_pixbuf(pixbuf)
            
        except ImportError:
            logger.warning("qrcode or Pillow package not installed, QR code not displayed")
            self.qr_image.set_from_icon_name("image-missing", Gtk.IconSize.DIALOG)
    
    def update_devices(self, devices):
        """Update the devices list"""
        # Clear existing items
        for child in self.devices_list.get_children():
            self.devices_list.remove(child)
        
        # Add devices or placeholder
        if not devices:
            placeholder = Gtk.Label(label="No devices connected")
            placeholder.set_padding(10, 10)
            self.devices_list.add(placeholder)
        else:
            for device in devices:
                device_row = Gtk.ListBoxRow()
                device_row.get_style_context().add_class("device-row")
                
                hbox = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=10)
                
                # Status indicator
                status_icon = Gtk.Image()
                if device.get("online", False):
                    status_icon.set_from_icon_name("user-available", Gtk.IconSize.MENU)
                else:
                    status_icon.set_from_icon_name("user-offline", Gtk.IconSize.MENU)
                hbox.pack_start(status_icon, False, False, 0)
                
                # Device name and type
                name = device.get("name", "Unknown")
                device_type = device.get("type", "unknown")
                label = Gtk.Label(label=f"{name} ({device_type})")
                label.set_halign(Gtk.Align.START)
                hbox.pack_start(label, True, True, 0)
                
                # Unpair button
                unpair_button = Gtk.Button(label="Unpair")
                unpair_button.connect("clicked", self.on_unpair_clicked, device.get("id"))
                hbox.pack_end(unpair_button, False, False, 0)
                
                device_row.add(hbox)
                self.devices_list.add(device_row)
        
        self.devices_list.show_all()
    
    def update_transfers(self, transfers):
        """Update the transfers list"""
        # Clear existing items
        for child in self.transfers_box.get_children():
            self.transfers_box.remove(child)
        
        # Add transfers or placeholder
        if not transfers:
            placeholder = Gtk.Label(label="No active transfers")
            placeholder.set_padding(10, 10)
            self.transfers_box.pack_start(placeholder, False, False, 0)
        else:
            for transfer_id, transfer in transfers.items():
                self.add_or_update_transfer(transfer)
        
        self.transfers_box.show_all()
    
    def update_transfer(self, transfer):
        """Update a single transfer"""
        self.add_or_update_transfer(transfer)
        self.transfers_box.show_all()
        
    def add_or_update_transfer(self, transfer):
        """Add or update a transfer card"""
        transfer_id = transfer.get("file_id")
        
        # Look for existing transfer card
        existing_card = None
        for child in self.transfers_box.get_children():
            if hasattr(child, 'transfer_id') and child.transfer_id == transfer_id:
                existing_card = child
                break
        
        # If transfer is complete or failed and there's an existing card, remove it
        status = transfer.get("status", "")
        if status in ["completed", "failed", "canceled"] and existing_card:
            self.transfers_box.remove(existing_card)
            
            # Add "No active transfers" if this was the last one
            if len(self.transfers_box.get_children()) == 0:
                placeholder = Gtk.Label(label="No active transfers")
                placeholder.set_padding(10, 10)
                self.transfers_box.pack_start(placeholder, False, False, 0)
                
            return
        
        # If this is a new transfer, make sure there's no placeholder
        if not existing_card:
            # Remove "No active transfers" placeholder if it exists
            for child in self.transfers_box.get_children():
                if isinstance(child, Gtk.Label) and child.get_text() == "No active transfers":
                    self.transfers_box.remove(child)
                    break
        
        # Create or update transfer card
        if existing_card:
            card = existing_card
            # Update progress
            progress_bar = None
            for child in card.get_children()[0].get_children():
                if isinstance(child, Gtk.ProgressBar):
                    progress_bar = child
                    break
            
            if progress_bar:
                progress = transfer.get("progress", 0) / 100.0
                progress_bar.set_fraction(progress)
                
                # Also update the info label
                info_label = None
                for child in card.get_children()[0].get_children():
                    if isinstance(child, Gtk.Label) and hasattr(child, 'is_info_label'):
                        info_label = child
                        break
                
                if info_label:
                    direction = transfer.get("direction", "transfer")
                    bytes_transferred = transfer.get("bytes_transferred", 0)
                    total_bytes = transfer.get("total_bytes", 0)
                    
                    direction_text = "Downloading from" if direction == "download" else "Uploading to"
                    info_label.set_text(
                        f"{direction_text} device\n"
                        f"{bytes_transferred // 1024} KB / {total_bytes // 1024} KB"
                    )
        else:
            # Create a new card
            card = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=5)
            card.transfer_id = transfer_id
            card.get_style_context().add_class("transfer-card")
            
            # File name header
            file_name = transfer.get("file_name", "Unknown file")
            header = Gtk.Label(label=file_name)
            header.set_halign(Gtk.Align.START)
            header.set_ellipsize(Pango.EllipsizeMode.MIDDLE)
            header.get_style_context().add_class("card-header")
            card.pack_start(header, False, False, 0)
            
            # Transfer info
            direction = transfer.get("direction", "transfer")
            bytes_transferred = transfer.get("bytes_transferred", 0)
            total_bytes = transfer.get("total_bytes", 0)
            
            direction_text = "Downloading from" if direction == "download" else "Uploading to"
            info = Gtk.Label()
            info.is_info_label = True  # Custom attribute to find it later
            info.set_text(
                f"{direction_text} device\n"
                f"{bytes_transferred // 1024} KB / {total_bytes // 1024} KB"
            )
            info.set_halign(Gtk.Align.START)
            info.set_line_wrap(True)
            card.pack_start(info, False, False, 0)
            
            # Progress bar
            progress = transfer.get("progress", 0) / 100.0
            progress_bar = Gtk.ProgressBar()
            progress_bar.set_fraction(progress)
            card.pack_start(progress_bar, False, False, 0)
            
            # Cancel button
            cancel_button = Gtk.Button(label="Cancel")
            cancel_button.connect("clicked", self.on_cancel_transfer_clicked, transfer_id)
            cancel_button.set_halign(Gtk.Align.END)
            card.pack_start(cancel_button, False, False, 0)
            
            # Add to transfers box
            self.transfers_box.pack_start(card, False, False, 0)
    
    def on_refresh_clicked(self, button):
        """Handle refresh button click"""
        self.app.on_refresh(None, None)
    
    def on_send_file_clicked(self, button):
        """Handle send file button click"""
        dialog = Gtk.FileChooserDialog(
            title="Select a file to send",
            parent=self,
            action=Gtk.FileChooserAction.OPEN
        )
        dialog.add_button(Gtk.STOCK_CANCEL, Gtk.ResponseType.CANCEL)
        dialog.add_button(Gtk.STOCK_OPEN, Gtk.ResponseType.OK)
        
        response = dialog.run()
        if response == Gtk.ResponseType.OK:
            file_path = dialog.get_filename()
            
            # Show device selection dialog if there are devices
            if self.app.paired_devices:
                self.show_device_selection_dialog(file_path)
            else:
                self.show_error_dialog("No paired devices", "Please pair a device first.")
        
        dialog.destroy()
    
    def show_device_selection_dialog(self, file_path):
        """Show a dialog to select which device to send the file to"""
        dialog = Gtk.Dialog(
            title="Select Device",
            parent=self,
            flags=0,
            buttons=(
                Gtk.STOCK_CANCEL, Gtk.ResponseType.CANCEL,
                "Send", Gtk.ResponseType.OK
            )
        )
        
        content_area = dialog.get_content_area()
        content_area.set_border_width(15)
        
        label = Gtk.Label(label="Select a device to send the file to:")
        content_area.pack_start(label, False, False, 10)
        
        # Device list
        device_combo = Gtk.ComboBoxText()
        for device_id, device in self.app.paired_devices.items():
            if device.get("online", False):
                device_combo.append(device_id, device.get("name", "Unknown"))
        
        # Select first device
        device_combo.set_active(0)
        content_area.pack_start(device_combo, False, False, 5)
        
        dialog.show_all()
        response = dialog.run()
        
        if response == Gtk.ResponseType.OK:
            selected_device = device_combo.get_active_id()
            if selected_device:
                # Send file to selected device
                self.send_file_to_device(file_path, selected_device)
            else:
                self.show_error_dialog("Error", "No device selected.")
        
        dialog.destroy()
    
    def send_file_to_device(self, file_path, device_id):
        """Send a file to the selected device"""
        # This is a stub - in a real implementation, this would call
        # into the server backend to initiate a file transfer
        self.app.send_message({
            "type": "admin_request",
            "action": "send_file",
            "file_path": file_path,
            "device_id": device_id
        })
        
        self.update_status(f"Sending file to device...", "info")
    
    def on_unpair_clicked(self, button, device_id):
        """Handle unpair button click"""
        dialog = Gtk.MessageDialog(
            transient_for=self,
            flags=0,
            message_type=Gtk.MessageType.QUESTION,
            buttons=Gtk.ButtonsType.YES_NO,
            text="Unpair Device"
        )
        dialog.format_secondary_text("Are you sure you want to unpair this device?")
        
        response = dialog.run()
        if response == Gtk.ResponseType.YES:
            # Send unpair request to server
            self.app.send_message({
                "type": "admin_request",
                "action": "unpair_device",
                "device_id": device_id
            })
        
        dialog.destroy()
    
    def on_cancel_transfer_clicked(self, button, transfer_id):
        """Handle cancel transfer button click"""
        # Send cancel request to server
        self.app.send_message({
            "type": "admin_request",
            "action": "cancel_transfer",
            "transfer_id": transfer_id
        })
    
    def on_clipboard_switch_toggled(self, switch, gparam):
        """Handle clipboard sync setting toggle"""
        active = switch.get_active()
        self.app.settings["clipboard_sync"] = active
        
        # Send setting to server
        self.app.send_message({
            "type": "admin_request",
            "action": "set_setting",
            "setting": "clipboard_sync",
            "value": active
        })
    
    def on_notification_switch_toggled(self, switch, gparam):
        """Handle notification mirroring setting toggle"""
        active = switch.get_active()
        self.app.settings["notification_mirroring"] = active
        
        # Send setting to server
        self.app.send_message({
            "type": "admin_request",
            "action": "set_setting",
            "setting": "notification_mirroring",
            "value": active
        })
    
    def on_reconnect_switch_toggled(self, switch, gparam):
        """Handle auto reconnect setting toggle"""
        active = switch.get_active()
        self.app.settings["auto_reconnect"] = active
        
        # Send setting to server
        self.app.send_message({
            "type": "admin_request",
            "action": "set_setting",
            "setting": "auto_reconnect",
            "value": active
        })
    
    def show_error_dialog(self, title, message):
        """Show an error dialog"""
        dialog = Gtk.MessageDialog(
            transient_for=self,
            flags=0,
            message_type=Gtk.MessageType.ERROR,
            buttons=Gtk.ButtonsType.OK,
            text=title
        )
        dialog.format_secondary_text(message)
        dialog.run()
        dialog.destroy()


def main():
    """Main application entry point"""
    app = SICApplication()
    return app.run(sys.argv)

if __name__ == "__main__":
    sys.exit(main())