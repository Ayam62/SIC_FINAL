"""
Notification capture and forwarding module for the Linux server.
Uses dbus to intercept system notifications and forward them to paired devices.
"""

import logging
import threading
import json
import time
from typing import Callable, Dict, Any, Optional
import subprocess

# Optional dbus import - we'll try to use it but provide fallback if not available
try:
    import dbus
    from dbus.mainloop.glib import DBusGMainLoop
    from gi.repository import GLib
    DBUS_AVAILABLE = True
except ImportError:
    DBUS_AVAILABLE = False
    logging.warning("dbus not available, notification mirroring will be limited")

logger = logging.getLogger(__name__)

# Store callbacks for notification events
_notification_callbacks = []
_mainloop = None
_notification_thread = None
_should_monitor = False

def register_notification_callback(callback: Callable[[Dict[str, Any]], None]) -> None:
    """
    Register a callback to be called when new notifications arrive.
    
    Args:
        callback: Function taking notification details dictionary
    """
    _notification_callbacks.append(callback)

def _on_notification_received(*args, **kwargs) -> None:
    """
    Handle incoming notification from dbus.
    Formats notification data and calls all registered callbacks.
    """
    try:
        app_name = str(args[0]) if args and len(args) > 0 else "Unknown"
        replaces_id = int(args[1]) if args and len(args) > 1 and isinstance(args[1], (str, int)) else 0
        app_icon = str(args[2]) if args and len(args) > 2 else ""
        summary = str(args[3]) if args and len(args) > 3 else ""
        body = str(args[4]) if args and len(args) > 4 else ""

        # Construct notification object
        notification = {
            "type": "notification",
            "app_name": app_name,
            "replaces_id": replaces_id,
            "app_icon": app_icon,
            "summary": summary,
            "body": body,
            "timestamp": time.time()
        }

        logger.info(f"Notification captured: {app_name} - {summary}")

        # Call all registered callbacks
        for callback in _notification_callbacks:
            try:
                callback(notification)
            except Exception as e:
                logger.error(f"Error in notification callback: {e}")

    except Exception as e:
        logger.error(f"Error processing notification: {e}")

def _dbus_notification_monitor() -> None:
    """
    Start dbus mainloop to monitor for notifications.
    """
    global _mainloop
    
    logger.info("Starting dbus notification monitor")
    DBusGMainLoop(set_as_default=True)
    
    bus = dbus.SessionBus()
    bus.add_match_string_non_blocking(
        "interface='org.freedesktop.Notifications',member='Notify'"
    )
    bus.add_message_filter(_on_notification_received)
    
    _mainloop = GLib.MainLoop()
    _mainloop.run()
    logger.info("Dbus notification monitor stopped")

def _fallback_notification_monitor() -> None:
    """
    Fallback notification monitoring using command line tools if dbus is not available.
    This will use a notify-send hook or other methods depending on what's available.
    """
    logger.info("Starting fallback notification monitor with notify-send hook")
    
    # This is a placeholder. In a full implementation, you might use a tool like:
    # - A custom dunst hook script 
    # - A notify-send wrapper
    # - Monitoring a notification log file
    
    while _should_monitor:
        # Simulated notification check
        time.sleep(5)
        
        # In a real implementation, check for new notifications here
        # and call the callbacks when notifications are detected
    
    logger.info("Fallback notification monitor stopped")

def start_monitoring() -> bool:
    """
    Start monitoring for system notifications.
    Uses dbus if available, otherwise falls back to alternative methods.
    
    Returns:
        bool: True if started, False otherwise
    """
    global _notification_thread, _should_monitor
    
    if _notification_thread and _notification_thread.is_alive():
        logger.warning("Notification monitoring already running")
        return False
    
    _should_monitor = True
    
    if DBUS_AVAILABLE:
        _notification_thread = threading.Thread(target=_dbus_notification_monitor, daemon=True)
    else:
        _notification_thread = threading.Thread(target=_fallback_notification_monitor, daemon=True)
    
    _notification_thread.start()
    logger.info("Notification monitoring started")
    return True

def stop_monitoring() -> None:
    """Stop notification monitoring."""
    global _should_monitor, _mainloop
    
    _should_monitor = False
    
    if DBUS_AVAILABLE and _mainloop:
        _mainloop.quit()
    
    if _notification_thread:
        _notification_thread.join(timeout=1.0)
        logger.info("Notification monitoring stopped")

def send_test_notification(title: str = "Test Notification", 
                          body: str = "This is a test notification from SIC") -> None:
    """
    Send a test notification to verify the system is working.
    
    Args:
        title: Notification title
        body: Notification body
    """
    try:
        subprocess.run(['notify-send', title, body])
        logger.info("Test notification sent")
    except Exception as e:
        logger.error(f"Failed to send test notification: {e}")