#!/usr/bin/env python3
"""
SIC
Main entry point for starting the Linux-Android integration system.
"""

import os
import sys
import argparse
import subprocess
import signal
import time
from pathlib import Path

# Set up base paths
PROJECT_ROOT = Path(__file__).parent.resolve()
LINUX_SERVER_PATH = PROJECT_ROOT / "linux-server"

def start_server(args):
    """
    Start the Linux server process with command line arguments.
    Creates a subprocess running the server script with appropriate flags.
    Returns the subprocess object for monitoring and control.
    """
    cmd = [sys.executable, str(LINUX_SERVER_PATH / "serve.py")]
    
    # Add arguments
    if args.host:
        # If a specific host address is provided, add it to the command
        cmd.extend(["--host", args.host])
    
    if args.port:
        # If a specific port number is provided, add it to the command
        cmd.extend(["--port", str(args.port)])
    
    if args.debug:
        # If debug mode is enabled, add the debug flag
        cmd.append("--debug")
    
    if args.reload:
        # If auto-reload is enabled (for development), add the reload flag
        cmd.append("--reload")
    
    if args.no_clipboard:
        # If clipboard synchronization should be disabled, add the flag
        cmd.append("--no-clipboard")
    
    if args.no_notifications:
        # If notification mirroring should be disabled, add the flag
        cmd.append("--no-notifications")
    
    if args.generate_qr:
        # If QR code generation for easy pairing is requested, add the flag
        cmd.append("--generate-qr")
    
    # Start server
    print(f"Starting SIC server: {' '.join(cmd)}")
    return subprocess.Popen(cmd)

def check_dependencies():
    """
    Verify that all required Python packages are installed.
    Attempts to import each dependency and reports any missing packages.
    Returns True if all dependencies are met, False otherwise.
    """
    try:
        # Try to import required packages
        import fastapi
        import uvicorn
        import websockets
        import cryptography
        import pyperclip
        import zeroconf
        
        print("✅ All basic dependencies are installed.")
        return True
    except ImportError as e:
        # If any import fails, inform the user about the missing dependency
        print(f"❌ Missing dependency: {e}")
        print("Please run: pip install -r requirements.txt")
        return False

def install_systemd_service():
    """
    Create and install a systemd user service file for auto-starting SIC.
    Generates the service file in the user's systemd configuration directory.
    Provides instructions for enabling and starting the service.
    """
    service_path = Path.home() / ".config" / "systemd" / "user"
    service_path.mkdir(parents=True, exist_ok=True)
    
    service_file = service_path / "sic.service"
    
    service_content = f"""[Unit]
Description=SIC
After=network.target

[Service]
Type=simple
ExecStart={sys.executable} {PROJECT_ROOT / "run.py"}
Restart=on-failure
RestartSec=5

[Install]
WantedBy=default.target
"""
    
    with open(service_file, "w") as f:
        f.write(service_content)
    
    print(f"Created systemd service file at: {service_file}")
    print("To enable auto-start on login, run:")
    print("  systemctl --user enable sic.service")
    print("To start the service now, run:")
    print("  systemctl --user start sic.service")

def main():
    """
    Main entry point for the SIC application.
    Parses command line arguments, checks dependencies, and manages the server process.
    Handles graceful shutdown when interrupted (Ctrl+C).
    """
    parser = argparse.ArgumentParser(description="SIC")
    parser.add_argument("--host", type=str, help="Host to bind the server to")
    parser.add_argument("--port", type=int, help="Port to bind the server to")
    parser.add_argument("--debug", action="store_true", help="Enable debug logging")
    parser.add_argument("--reload", action="store_true", help="Enable auto-reload for development")
    parser.add_argument("--no-clipboard", action="store_true", help="Disable clipboard synchronization")
    parser.add_argument("--no-notifications", action="store_true", help="Disable notification mirroring")
    parser.add_argument("--generate-qr", action="store_true", help="Generate QR code for pairing")
    parser.add_argument("--install-service", action="store_true", help="Install systemd user service")
    
    args = parser.parse_args()
    
    if args.install_service:
        # If the user requested to install service, do that and exit
        install_systemd_service()
        return
    
    if not check_dependencies():
        # Abort if required dependencies are missing
        return
    
    print("Starting SIC")
    print("Press Ctrl+C to exit")
    
    server_process = start_server(args)
    
    try:
        # Keep the main process running while the server is active
        while server_process.poll() is None:
            time.sleep(1)
    except KeyboardInterrupt:
        # Handle graceful shutdown when user presses Ctrl+C
        print("Shutting down...")
        server_process.send_signal(signal.SIGINT)
        server_process.wait()

if __name__ == "__main__":
    main()