#!/usr/bin/env python3
"""
SIC Ubuntu Desktop Application Launcher
Run this script to start the Ubuntu desktop application.
"""

import os
import sys
from pathlib import Path
from notifypy import Notify



APP_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = APP_DIR.parent

# Add the app directory to path so we can import from it
sys.path.insert(0, str(APP_DIR / "src"))

if __name__ == "__main__":
    # Change to project directory to ensure relative paths work
    os.chdir(str(PROJECT_ROOT))
    
    # Import and run the application
    try:
        from app import main
        sys.exit(main())
    except ImportError as e:
        print(f"Error importing app module: {e}")
        print("Make sure PyGObject (GTK) dependencies are installed:")
        print("  sudo apt install python3-gi python3-gi-cairo gir1.2-gtk-3.0")
        sys.exit(1)
    except Exception as e:
        print(f"Error starting application: {e}")
        sys.exit(1)