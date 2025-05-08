"""
Main server file for the Linux-Android SIC system.
Runs the FastAPI application with WebSocket support for real-time communication.
Integrates clipboard synchronization, notification mirroring, and secure file transfer.
"""

import os
import sys
import logging
import uvicorn
import asyncio
from pathlib import Path
import argparse

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    handlers=[
        logging.StreamHandler(sys.stdout)
    ]
)
logger = logging.getLogger("sic-server")

# Make backend module available for import
SERVER_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(SERVER_DIR))

# Run server
if __name__ == "__main__":
    parser = argparse.ArgumentParser(description='SIC server')
    parser.add_argument('--host', type=str, default='0.0.0.0', help='Host to bind')
    parser.add_argument('--port', type=int, default=8001, help='Port to bind')
    parser.add_argument('--reload', action='store_true', help='Enable auto-reload for development')
    parser.add_argument('--debug', action='store_true', help='Enable debug logging')
    parser.add_argument('--no-notifications', action='store_true', help='Disable notification mirroring')
    parser.add_argument('--no-clipboard', action='store_true', help='Disable clipboard sync')
    parser.add_argument('--generate-qr', action='store_true', help='Generate pairing QR code')
    parser.add_argument('--mdns-name', type=str, default=None, help='Custom mDNS service name to avoid conflicts')
    args = parser.parse_args()
    
    # Set logging level
    if args.debug:
        logging.getLogger().setLevel(logging.DEBUG)
    
    # Import and run app
    from backend.main import app, manager
    
    # Set up features
    if not args.no_clipboard:
        from backend.clipboard import start_monitoring, register_clipboard_change_callback
        
        # Register callback to send clipboard changes to connected devices
        def on_clipboard_change(text):
            logger.debug(f"Local clipboard changed, sending to {len(manager.active_connections)} devices")
            # Create async task to send clipboard update
            try:
                loop = asyncio.get_running_loop()
            except RuntimeError:
                # Create a new event loop if there isn't one running
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)
            
            asyncio.run_coroutine_threadsafe(
                manager.broadcast({
                    "type": "clipboard_sync",
                    "text": text,
                    "source": "linux-server"
                }),
                loop
            )
        
        # Create a new event loop instead of getting the current one
        current_loop = asyncio.new_event_loop()
        asyncio.set_event_loop(current_loop)
        register_clipboard_change_callback(on_clipboard_change, current_loop)
        start_monitoring()
        logger.info("Clipboard synchronization enabled")
    
    if not args.no_notifications:
        from backend.notifier import start_monitoring, register_notification_callback
        
        # Register callback to send notifications to connected devices
        def on_notification(notification_data):
            # Create async task to send notification update
            try:
                loop = asyncio.get_running_loop()
            except RuntimeError:
                # Create a new event loop if there isn't one running
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)
                
            asyncio.run_coroutine_threadsafe(
                manager.broadcast(notification_data),
                loop
            )
        
        register_notification_callback(on_notification)
        start_monitoring()
        logger.info("Notification mirroring enabled")
    
    # Print pairing info
    if args.generate_qr:
        try:
            import qrcode
            from backend.main import DEVICE_ID, PAIRING_CODE
            
            # Generate pairing data
            pairing_data = f"sic://{DEVICE_ID}/{PAIRING_CODE}"
            
            # Generate and display QR code in terminal
            qr = qrcode.QRCode()
            qr.add_data(pairing_data)
            qr.make(fit=True)
            qr.print_ascii()
            
            logger.info(f"Pairing code: {PAIRING_CODE}")
            logger.info(f"Device ID: {DEVICE_ID}")
            logger.info(f"Scan this QR code with the Android app to pair")
        except ImportError:
            logger.warning("qrcode package not installed. Run 'pip install qrcode' to enable QR code generation.")
            logger.info(f"Manual pairing is still available at http://{args.host}:{args.port}")
    
    # Set custom mDNS name if provided
    if args.mdns_name:
        os.environ["SIC_MDNS_NAME"] = args.mdns_name
    
    # Run the server
    logger.info(f"Starting server at http://{args.host}:{args.port}")
    uvicorn.run("backend.main:app", host=args.host, port=args.port, reload=args.reload)