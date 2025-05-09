from fastapi import FastAPI, WebSocket, WebSocketDisconnect, Request
from fastapi.templating import Jinja2Templates
from fastapi.staticfiles import StaticFiles
import uvicorn
import os
import logging
from pathlib import Path
import socket
import json
import uuid
import threading
from zeroconf import ServiceInfo, Zeroconf
import time
import random
import string
from fastapi.middleware.cors import CORSMiddleware
from typing import Dict

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)

# Create FastAPI app
app = FastAPI(title="Offline Device Integration System")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Allow all origins, adjust for security in production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# Set up Jinja2 templates
BASE_DIR = Path(__file__).resolve().parent.parent
templates = Jinja2Templates(directory=str(BASE_DIR / "templates"))

# Create templates directory if it doesn't exist
os.makedirs(BASE_DIR / "templates", exist_ok=True)

# Create static directory if it doesn't exist
os.makedirs(BASE_DIR / "static", exist_ok=True)

# Mount static files directory
app.mount("/static", StaticFiles(directory=str(BASE_DIR / "static")), name="static")

# Generate a unique device ID if not already saved
DEVICE_ID_FILE = BASE_DIR / ".device_id"
if DEVICE_ID_FILE.exists():
    with open(DEVICE_ID_FILE, "r") as f:
        DEVICE_ID = f.read().strip()
else:
    DEVICE_ID = str(uuid.uuid4())
    with open(DEVICE_ID_FILE, "w") as f:
        f.write(DEVICE_ID)

# Generate a random pairing code for initial device pairing
def generate_pairing_code(length=6):
    return ''.join(random.choices(string.ascii_uppercase + string.digits, k=length))

PAIRING_CODE = generate_pairing_code()
PAIRED_DEVICES = {}  # Store MAC address / device ID of paired devices
PAIRING_FILE = BASE_DIR / ".paired_devices"

# Load any previously paired devices
if PAIRING_FILE.exists():
    try:
        with open(PAIRING_FILE, "r") as f:
            PAIRED_DEVICES = json.load(f)
    except:
        logger.warning("Failed to load paired devices file")

# Save paired devices
def save_paired_devices():
    with open(PAIRING_FILE, "w") as f:
        json.dump(PAIRED_DEVICES, f)

# Connection manager for WebSockets
class ConnectionManager:
    def __init__(self):
        self.active_connections: Dict[str, WebSocket] = {}  # Map device ID to connection
        self.clipboard_last_sync = None  # Track last clipboard sync to prevent loops
        self.pending_pairings = {}  # Temporary store for devices in pairing process

    async def connect(self, websocket: WebSocket, device_id: str = None):
        # If the device ID is provided and recognized/paired, store the connection
        if device_id and device_id in PAIRED_DEVICES:
            self.active_connections[device_id] = websocket
            logger.info(f"Paired device {device_id} connected. Total connections: {len(self.active_connections)}")
        else:
            # For unpaired/new connections, use websocket object as key temporarily
            temp_id = str(id(websocket))
            self.active_connections[temp_id] = websocket
            logger.info(f"New unpaired connection {temp_id}. Total connections: {len(self.active_connections)}")
        return device_id or temp_id

    def disconnect(self, connection_id: str):
        if connection_id in self.active_connections:
            del self.active_connections[connection_id]
            logger.info(f"Connection {connection_id} closed. Total connections: {len(self.active_connections)}")

    async def broadcast(self, message_dict: dict, exclude: str = None):
        message = json.dumps(message_dict)
        for conn_id, connection in self.active_connections.items():
            if exclude != conn_id:
                try:
                    await connection.send_text(message)
                except Exception as e:
                    logger.error(f"Error sending to {conn_id}: {e}")
                    # We'll handle reconnection elsewhere, just log for now

    async def send_to_device(self, device_id: str, message_dict: dict):
        if device_id in self.active_connections:
            try:
                await self.active_connections[device_id].send_text(json.dumps(message_dict))
                return True
            except Exception as e:
                logger.error(f"Error sending to device {device_id}: {e}")
                return False
        return False

manager = ConnectionManager()

# mDNS Service setup
def setup_mdns():
    hostname = socket.gethostname()
    local_ip = socket.gethostbyname(hostname)
    port = 8000  # Our FastAPI server port

    logger.info(f"Setting up mDNS with IP: {local_ip}")

    # Create ServiceInfo object
    service_info = ServiceInfo(
        "_sic-sync._tcp.local.",  # Service type
        f"{hostname}-sic-sync._sic-sync._tcp.local.",  # Service name
        addresses=[socket.inet_aton(local_ip)],
        port=port,
        weight=0,
        priority=0,
        properties={
            b'deviceid': DEVICE_ID.encode('utf-8'),
            b'type': b'linux-server',
            b'hostname': hostname.encode('utf-8'),
        }
    )

    zeroconf = Zeroconf()
    zeroconf.register_service(service_info, allow_name_change=True)
    logger.info(f"mDNS service registered: {service_info.name}")

    # Return zeroconf and service_info for later unregistration
    return zeroconf, service_info

# Initialize mDNS on server startup
@app.on_event("startup")
async def startup_event():
    # Start mDNS service in a separate thread to avoid blocking
    threading.Thread(target=setup_mdns, daemon=True).start()
    logger.info(f"Server started with device ID: {DEVICE_ID}")
    logger.info(f"Initial pairing code: {PAIRING_CODE}")



@app.get("/")
async def get_home(request: Request):
    """Serve the homepage with WebSocket client"""
    hostname = socket.gethostname()
    return templates.TemplateResponse("index.html", {
        "request": request,
        "device_id": DEVICE_ID,
        "hostname": hostname,
        "pairing_code": PAIRING_CODE,
    })

@app.websocket("/ws/{client_id}")
async def websocket_endpoint(websocket: WebSocket, client_id: str):
    await websocket.accept()
    connection_id = await manager.connect(websocket, client_id)
    
    try:
        while True:
            try:
                raw_data = await websocket.receive_text()
                data = json.loads(raw_data)
                logger.info(f"Message from {connection_id}: {raw_data}")
                
                message_type = data.get('type')
                if message_type in ['clipboard_update', 'clipboard_sync']:  # Accept both types
                    await handle_clipboard(websocket, connection_id, data)
                elif message_type == "pairing_request":
                    await handle_pairing(websocket, connection_id, data)
                else:
                    logger.warning(f"Unknown message type: {message_type}")
            except json.JSONDecodeError:
                logger.error(f"Invalid JSON from {connection_id}: {raw_data}")
    except WebSocketDisconnect:
        manager.disconnect(connection_id)
        logger.info(f"Client {connection_id} disconnected")
    except Exception as e:
        logger.error(f"WebSocket error: {e}")
        manager.disconnect(connection_id)

async def handle_admin_request(websocket: WebSocket, data: dict):
    """Handle administrative requests"""
    try:
        action = data['action']
        
        if action == "get_status":
            await websocket.send_text(json.dumps({
                "type": "admin_response",
                "status": "running",
                "server_id": DEVICE_ID,
                "paired_devices": len(PAIRED_DEVICES),
                "timestamp": time.time()
            }))
        else:
            await websocket.send_text(json.dumps({
                "type": "error",
                "message": f"Unsupported admin action: {action}"
            }))
            
    except KeyError:
        await websocket.send_text(json.dumps({
            "type": "error",
            "message": "Admin requests require 'action' field"
        }))

# Handler functions for different message types
async def handle_pairing(websocket: WebSocket, connection_id: str, data: dict):
    """Handle device pairing requests"""
    global PAIRING_CODE
    if data.get("code") == PAIRING_CODE:
        device_id = data.get("device_id")
        device_name = data.get("device_name", "Unknown Device")
        device_type = data.get("device_type", "unknown")

        # Store the pairing and save
        PAIRED_DEVICES[device_id] = {
            "name": device_name,
            "type": device_type,
            "paired_at": time.time()
        }
        save_paired_devices()

        # Send confirmation and rotate pairing code
        await websocket.send_text(json.dumps({
            "type": "pairing_response",
            "success": True,
            "message": "Pairing successful",
            "server_id": DEVICE_ID,
            "server_name": socket.gethostname()
        }))

        # Generate a new code for security
        PAIRING_CODE = generate_pairing_code()
        logger.info(f"Device {device_name} ({device_id}) paired successfully. New pairing code: {PAIRING_CODE}")
    else:
        await websocket.send_text(json.dumps({
            "type": "pairing_response",
            "success": False,
            "message": "Invalid pairing code"
        }))
        logger.warning(f"Failed pairing attempt from {connection_id}")



async def handle_clipboard(websocket: WebSocket, connection_id: str, data: dict):
    """Handle clipboard sync messages"""
    try:
        # Get text content (required)
        text = data.get("text", "")
        if not text:
            logger.warning("Clipboard update with empty text")
            return

        # Get device ID (optional for new connections)
        device_id = data.get("device_id", connection_id)
        
        # Log the update regardless of pairing status
        logger.info(f"Clipboard update received from {device_id}")

        # Only check pairing if we have a proper device_id (not connection_id)
        if 'device_id' in data and device_id not in PAIRED_DEVICES:
            logger.warning(f"Unpaired device {device_id} attempted clipboard sync")
            return

        # Import clipboard handlers (modified to handle missing module)
        try:
            from .clipboard import set_clipboard_text
            manager.clipboard_last_sync = text
            set_clipboard_text(text)
            logger.info(f"Clipboard updated successfully from {device_id}")
        except ImportError:
            logger.error("Clipboard module not available - running in demo mode")
            manager.clipboard_last_sync = text
            print(f"[DEMO] Would set clipboard to: {text}")
    except Exception as e:
        logger.error(f"Error handling clipboard: {str(e)}")



async def handle_notification(connection_id: str, data: dict):
    """Handle notification messages"""
    # Process notification - will be implemented in notifier.py
    pass


async def handle_file_transfer_init(websocket: WebSocket, connection_id: str, data: dict):
    """Handle file transfer initialization"""
    # File transfer handling - will be implemented in filetransfer.py
    pass


async def handle_file_transfer_chunk(connection_id: str, data: dict):
    """Handle file transfer data chunks"""
    # File chunk handling - will be implemented in filetransfer.py
    pass


if __name__ == "__main__":
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)
