"""
Clipboard monitoring and synchronization module for the Linux server.
Uses pyperclip for clipboard operations and provides mechanisms to prevent infinite sync loops.
"""

import pyperclip
import threading
import time
import logging
import asyncio
from typing import Callable, Optional, Any, Awaitable, Union

logger = logging.getLogger(__name__)

# Global flag to prevent clipboard sync loops
_clipboard_last_sync = None
_clipboard_lock = threading.Lock()
_clipboard_callback = None
_monitoring_thread = None
_should_monitor = False
_main_event_loop = None

def set_clipboard_text(text: str) -> bool:
    """
    Set the clipboard text and mark it as the last sync value to prevent loops.
    
    Args:
        text: Text to set in clipboard
        
    Returns:
        bool: True if successful, False otherwise
    """
    global _clipboard_last_sync
    
    try:
        with _clipboard_lock:
            _clipboard_last_sync = text  # Mark this as coming from sync
            pyperclip.copy(text)
        return True
    except Exception as e:
        logger.error(f"Failed to set clipboard: {e}")
        return False

def get_clipboard_text() -> str:
    """
    Get current clipboard text.
    
    Returns:
        str: Current clipboard content
    """
    try:
        return pyperclip.paste()
    except Exception as e:
        logger.error(f"Failed to get clipboard: {e}")
        return ""

def register_clipboard_change_callback(callback: Callable[[str], Any], loop: Optional[asyncio.AbstractEventLoop] = None) -> None:
    """
    Register a callback to be called when clipboard content changes locally.
    
    Args:
        callback: Function that takes clipboard text and does something with it
        loop: Event loop to use for async callbacks
    """
    global _clipboard_callback, _main_event_loop
    _clipboard_callback = callback
    _main_event_loop = loop or asyncio.get_event_loop()

def _monitor_clipboard() -> None:
    """
    Monitor clipboard for changes in a separate thread.
    When changes occur and they don't match the last sync value,
    the registered callback is called.
    """
    global _clipboard_last_sync, _should_monitor, _main_event_loop
    
    last_content = get_clipboard_text()
    logger.info("Clipboard monitoring started")
    
    while _should_monitor:
        try:
            current_content = get_clipboard_text()
            
            # Only notify if content changed and it's not from a sync operation
            with _clipboard_lock:
                if (current_content != last_content and 
                    current_content != _clipboard_last_sync and
                    current_content.strip()):
                    
                    logger.debug(f"Clipboard changed locally: {current_content[:50]}...")
                    
                    if _clipboard_callback:
                        # Call the callback function safely
                        try:
                            _clipboard_callback(current_content)
                        except RuntimeError as e:
                            if "no current event loop" in str(e).lower():
                                logger.debug("No event loop in thread, using stored main loop")
                                if _main_event_loop:
                                    try:
                                        # If we have the main event loop, use it
                                        if asyncio.iscoroutine(_clipboard_callback(current_content)):
                                            asyncio.run_coroutine_threadsafe(
                                                _clipboard_callback(current_content), 
                                                _main_event_loop
                                            )
                                    except Exception as inner_e:
                                        logger.error(f"Error dispatching to main event loop: {inner_e}")
                            else:
                                logger.error(f"Runtime error in callback: {e}")
                        except Exception as e:
                            logger.error(f"Error in clipboard callback: {e}")
                    
                # Reset the last sync indicator after we've checked it    
                if _clipboard_last_sync == current_content:
                    _clipboard_last_sync = None
                
            last_content = current_content
            
        except Exception as e:
            logger.error(f"Error in clipboard monitoring: {e}")
            
        # Polling interval
        time.sleep(0.5)
    
    logger.info("Clipboard monitoring stopped")

def start_monitoring() -> bool:
    """
    Start the clipboard monitoring thread.
    
    Returns:
        bool: True if started, False otherwise
    """
    global _monitoring_thread, _should_monitor
    
    if _monitoring_thread and _monitoring_thread.is_alive():
        logger.warning("Clipboard monitoring already running")
        return False
    
    _should_monitor = True
    _monitoring_thread = threading.Thread(target=_monitor_clipboard, daemon=True)
    _monitoring_thread.start()
    return True

def stop_monitoring() -> None:
    """Stop the clipboard monitoring thread."""
    global _should_monitor
    _should_monitor = False
    
    if _monitoring_thread:
        _monitoring_thread.join(timeout=1.0)