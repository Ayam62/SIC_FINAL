"""
Secure file transfer module for the Linux server.
Handles encrypted file transfers between devices using AES-256 encryption.
Supports chunked transfer for large files and provides progress tracking.
"""

import os
import json
import logging
import time
import base64
import hashlib
from pathlib import Path
from typing import Dict, Any, Optional, Callable, BinaryIO
import uuid
import asyncio

from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes
from cryptography.hazmat.primitives import padding
from cryptography.hazmat.backends import default_backend

logger = logging.getLogger(__name__)

# Default download directory
DEFAULT_DOWNLOAD_DIR = Path.home() / "Downloads" / "SIC-Transfers"
os.makedirs(DEFAULT_DOWNLOAD_DIR, exist_ok=True)

# Track active transfers
active_transfers = {}
transfer_callbacks = {}

class FileTransfer:
    """Class to handle file transfer state and operations"""
    
    def __init__(self, file_id: str, file_path: str, file_name: str, 
                 file_size: int, direction: str, device_id: str):
        """
        Initialize a new file transfer
        
        Args:
            file_id: Unique identifier for the transfer
            file_path: Path where the file is being saved or read from
            file_name: Original file name
            file_size: Total file size in bytes
            direction: 'upload' or 'download'
            device_id: ID of the remote device
        """
        self.file_id = file_id
        self.file_path = file_path
        self.file_name = file_name
        self.file_size = file_size
        self.direction = direction
        self.device_id = device_id
        self.bytes_transferred = 0
        self.status = "initializing"  # initializing, in_progress, completed, failed, canceled
        self.start_time = time.time()
        self.last_update_time = time.time()
        self.file_handle: Optional[BinaryIO] = None
        self.encryption_key = None
        self.iv = None
        
    def open_file(self):
        """Open the file handle for reading or writing"""
        try:
            mode = "rb" if self.direction == "upload" else "wb"
            self.file_handle = open(self.file_path, mode)
            self.status = "in_progress"
            return True
        except Exception as e:
            logger.error(f"Failed to open file {self.file_path}: {e}")
            self.status = "failed"
            return False
    
    def close_file(self):
        """Close the file handle"""
        if self.file_handle:
            self.file_handle.close()
            self.file_handle = None
    
    def update_progress(self, bytes_chunk: int):
        """Update transfer progress"""
        self.bytes_transferred += bytes_chunk
        self.last_update_time = time.time()
        
        # Calculate progress percentage
        progress = (self.bytes_transferred / self.file_size) * 100 if self.file_size > 0 else 0
        
        # Call progress callback if defined for this transfer
        if self.file_id in transfer_callbacks:
            transfer_callbacks[self.file_id](self, progress)
    
    def get_progress_info(self) -> Dict[str, Any]:
        """Get progress information for the transfer"""
        duration = time.time() - self.start_time
        bytes_per_sec = self.bytes_transferred / duration if duration > 0 else 0
        progress = (self.bytes_transferred / self.file_size) * 100 if self.file_size > 0 else 0
        
        # Calculate estimated time remaining
        if bytes_per_sec > 0 and self.bytes_transferred < self.file_size:
            remaining_bytes = self.file_size - self.bytes_transferred
            eta_seconds = remaining_bytes / bytes_per_sec
        else:
            eta_seconds = 0
            
        return {
            "file_id": self.file_id,
            "file_name": self.file_name,
            "direction": self.direction,
            "status": self.status,
            "progress": progress,
            "bytes_transferred": self.bytes_transferred,
            "total_bytes": self.file_size,
            "speed_bps": bytes_per_sec,
            "eta_seconds": eta_seconds
        }

def generate_transfer_id() -> str:
    """Generate a unique file transfer ID"""
    return str(uuid.uuid4())

def generate_encryption_key() -> Dict[str, bytes]:
    """
    Generate a secure AES-256 encryption key and initialization vector.
    
    Returns:
        Dict with 'key' and 'iv' as bytes
    """
    key = os.urandom(32)  # 256 bits = 32 bytes
    iv = os.urandom(16)   # 128 bits = 16 bytes for AES
    return {
        'key': key,
        'iv': iv
    }

def encrypt_file_chunk(chunk: bytes, key: bytes, iv: bytes) -> bytes:
    """
    Encrypt a chunk of file data using AES-256.
    
    Args:
        chunk: Data chunk to encrypt
        key: AES-256 key (32 bytes)
        iv: Initialization vector (16 bytes)
        
    Returns:
        Encrypted data
    """
    # Ensure the chunk is padded to the block size
    padder = padding.PKCS7(algorithms.AES.block_size).padder()
    padded_data = padder.update(chunk) + padder.finalize()
    
    # Encrypt the data
    cipher = Cipher(algorithms.AES(key), modes.CBC(iv), backend=default_backend())
    encryptor = cipher.encryptor()
    encrypted_data = encryptor.update(padded_data) + encryptor.finalize()
    
    return encrypted_data

def decrypt_file_chunk(encrypted_chunk: bytes, key: bytes, iv: bytes) -> bytes:
    """
    Decrypt a chunk of file data using AES-256.
    
    Args:
        encrypted_chunk: Encrypted data chunk
        key: AES-256 key (32 bytes)
        iv: Initialization vector (16 bytes)
        
    Returns:
        Decrypted data
    """
    # Decrypt the data
    cipher = Cipher(algorithms.AES(key), modes.CBC(iv), backend=default_backend())
    decryptor = cipher.decryptor()
    padded_data = decryptor.update(encrypted_chunk) + decryptor.finalize()
    
    # Remove padding
    unpadder = padding.PKCS7(algorithms.AES.block_size).unpadder()
    try:
        # In the last chunk, we need to remove padding
        data = unpadder.update(padded_data) + unpadder.finalize()
    except ValueError:
        # If this is not the last chunk, just return the padded data
        return padded_data
        
    return data

def register_transfer_callback(transfer_id: str, callback: Callable[[FileTransfer, float], None]) -> None:
    """
    Register a callback function for transfer progress updates
    
    Args:
        transfer_id: ID of the transfer to monitor
        callback: Function that takes a FileTransfer object and progress percentage
    """
    transfer_callbacks[transfer_id] = callback

def get_transfer_info(transfer_id: str) -> Optional[Dict[str, Any]]:
    """
    Get information about a specific file transfer
    
    Args:
        transfer_id: ID of the transfer
        
    Returns:
        Dictionary with transfer information or None if not found
    """
    if transfer_id in active_transfers:
        return active_transfers[transfer_id].get_progress_info()
    return None

def get_all_transfers() -> Dict[str, Dict[str, Any]]:
    """
    Get information about all active file transfers
    
    Returns:
        Dictionary mapping transfer IDs to transfer information
    """
    return {
        transfer_id: transfer.get_progress_info() 
        for transfer_id, transfer in active_transfers.items()
    }

async def prepare_upload_transfer(file_path: str, device_id: str) -> Dict[str, Any]:
    """
    Prepare a file for uploading to a remote device
    
    Args:
        file_path: Path to the file to upload
        device_id: ID of the device to upload to
        
    Returns:
        Dictionary with transfer details
    """
    try:
        path = Path(file_path)
        if not path.exists():
            raise FileNotFoundError(f"File not found: {file_path}")
        
        file_id = generate_transfer_id()
        file_name = path.name
        file_size = path.stat().st_size
        
        # Generate encryption details
        crypto = generate_encryption_key()
        key_b64 = base64.b64encode(crypto['key']).decode('utf-8')
        iv_b64 = base64.b64encode(crypto['iv']).decode('utf-8')
        
        # Create hash for verification
        file_hash = hashlib.sha256()
        with open(file_path, 'rb') as f:
            for byte_block in iter(lambda: f.read(4096), b""):
                file_hash.update(byte_block)
        file_hash_hex = file_hash.hexdigest()
        
        # Create transfer
        transfer = FileTransfer(
            file_id=file_id,
            file_path=file_path,
            file_name=file_name,
            file_size=file_size,
            direction="upload",
            device_id=device_id
        )
        
        transfer.encryption_key = crypto['key']
        transfer.iv = crypto['iv']
        
        # Store in active transfers
        active_transfers[file_id] = transfer
        
        # Return initialization data
        return {
            "file_id": file_id,
            "file_name": file_name,
            "file_size": file_size,
            "key": key_b64,
            "iv": iv_b64,
            "hash": file_hash_hex,
            "chunk_size": 65536  # 64KB chunks
        }
        
    except Exception as e:
        logger.error(f"Error preparing file upload: {e}")
        raise

async def prepare_download_transfer(file_info: Dict[str, Any], device_id: str) -> Dict[str, Any]:
    """
    Prepare to receive a file from a remote device
    
    Args:
        file_info: Dict with file details from prepare_upload_transfer
        device_id: ID of the device sending the file
        
    Returns:
        Dictionary with transfer details including save path
    """
    try:
        file_id = file_info.get('file_id')
        file_name = file_info.get('file_name')
        file_size = file_info.get('file_size')
        key_b64 = file_info.get('key')
        iv_b64 = file_info.get('iv')
        
        if not all([file_id, file_name, file_size, key_b64, iv_b64]):
            raise ValueError("Missing required file information")
        
        # Decode encryption key and IV
        key = base64.b64decode(key_b64)
        iv = base64.b64decode(iv_b64)
        
        # Generate save path
        save_path = DEFAULT_DOWNLOAD_DIR / file_name
        # Ensure unique filename
        counter = 1
        while save_path.exists():
            save_path = DEFAULT_DOWNLOAD_DIR / f"{Path(file_name).stem} ({counter}){Path(file_name).suffix}"
            counter += 1
        
        # Create transfer
        transfer = FileTransfer(
            file_id=file_id,
            file_path=str(save_path),
            file_name=file_name,
            file_size=file_size,
            direction="download",
            device_id=device_id
        )
        
        transfer.encryption_key = key
        transfer.iv = iv
        
        if not transfer.open_file():
            raise IOError(f"Failed to open file for writing: {save_path}")
        
        # Store in active transfers
        active_transfers[file_id] = transfer
        
        return {
            "file_id": file_id,
            "save_path": str(save_path),
            "status": "ready"
        }
        
    except Exception as e:
        logger.error(f"Error preparing file download: {e}")
        raise

async def process_file_chunk(file_id: str, chunk_data: bytes, chunk_index: int, final_chunk: bool) -> Dict[str, Any]:
    """
    Process a received chunk of file data
    
    Args:
        file_id: Transfer ID
        chunk_data: Base64 encoded and encrypted chunk data
        chunk_index: Sequence number of the chunk
        final_chunk: Whether this is the last chunk
        
    Returns:
        Dictionary with status information
    """
    try:
        if file_id not in active_transfers:
            raise ValueError(f"Unknown transfer ID: {file_id}")
        
        transfer = active_transfers[file_id]
        if transfer.direction != "download":
            raise ValueError(f"Transfer {file_id} is not a download")
        
        if not transfer.file_handle:
            if not transfer.open_file():
                raise IOError(f"Failed to open file: {transfer.file_path}")
        
        # Decode and decrypt the chunk
        encrypted_data = base64.b64decode(chunk_data)
        decrypted_data = decrypt_file_chunk(encrypted_data, transfer.encryption_key, transfer.iv)
        
        # Write the chunk to the file
        transfer.file_handle.write(decrypted_data)
        transfer.update_progress(len(decrypted_data))
        
        # If this is the final chunk, close the file
        if final_chunk:
            transfer.close_file()
            transfer.status = "completed"
            # Keep the transfer in active_transfers for a while so clients can check status
            asyncio.create_task(_cleanup_transfer(file_id))
        
        return {
            "file_id": file_id,
            "chunk_index": chunk_index,
            "status": "received" if not final_chunk else "completed",
            "bytes_received": transfer.bytes_transferred,
            "progress": (transfer.bytes_transferred / transfer.file_size) * 100 if transfer.file_size > 0 else 0
        }
        
    except Exception as e:
        logger.error(f"Error processing file chunk: {e}")
        
        # Clean up on error
        if file_id in active_transfers:
            transfer = active_transfers[file_id]
            transfer.close_file()
            transfer.status = "failed"
            
            # Try to delete the partial file
            try:
                if os.path.exists(transfer.file_path):
                    os.remove(transfer.file_path)
            except:
                pass
            
        raise

async def read_file_chunk(file_id: str, chunk_index: int, chunk_size: int = 65536) -> Dict[str, Any]:
    """
    Read a chunk from a file being uploaded
    
    Args:
        file_id: Transfer ID
        chunk_index: Index of the chunk to read
        chunk_size: Size of each chunk in bytes
        
    Returns:
        Dictionary with chunk data and metadata
    """
    try:
        if file_id not in active_transfers:
            raise ValueError(f"Unknown transfer ID: {file_id}")
        
        transfer = active_transfers[file_id]
        if transfer.direction != "upload":
            raise ValueError(f"Transfer {file_id} is not an upload")
        
        if not transfer.file_handle:
            if not transfer.open_file():
                raise IOError(f"Failed to open file: {transfer.file_path}")
        
        # Seek to the right position
        transfer.file_handle.seek(chunk_index * chunk_size)
        
        # Read the chunk
        chunk_data = transfer.file_handle.read(chunk_size)
        if not chunk_data and chunk_index > 0:
            # End of file reached
            transfer.close_file()
            transfer.status = "completed"
            asyncio.create_task(_cleanup_transfer(file_id))
            return {
                "file_id": file_id,
                "chunk_index": chunk_index,
                "final_chunk": True,
                "status": "completed",
                "chunk_data": ""
            }
        
        # Encrypt the chunk
        encrypted_data = encrypt_file_chunk(chunk_data, transfer.encryption_key, transfer.iv)
        
        # Encode as base64 for transmission
        chunk_b64 = base64.b64encode(encrypted_data).decode('utf-8')
        
        # Update progress
        transfer.update_progress(len(chunk_data))
        
        # Check if this is the last chunk
        next_chunk_pos = (chunk_index + 1) * chunk_size
        final_chunk = next_chunk_pos >= transfer.file_size
        
        if final_chunk:
            transfer.close_file()
            transfer.status = "completed"
            asyncio.create_task(_cleanup_transfer(file_id))
        
        return {
            "file_id": file_id,
            "chunk_index": chunk_index,
            "chunk_data": chunk_b64,
            "final_chunk": final_chunk,
            "progress": (transfer.bytes_transferred / transfer.file_size) * 100 if transfer.file_size > 0 else 0
        }
        
    except Exception as e:
        logger.error(f"Error reading file chunk: {e}")
        
        # Clean up on error
        if file_id in active_transfers:
            transfer = active_transfers[file_id]
            transfer.close_file()
            transfer.status = "failed"
            
        raise

async def cancel_transfer(file_id: str) -> Dict[str, Any]:
    """
    Cancel an active file transfer
    
    Args:
        file_id: Transfer ID
        
    Returns:
        Dictionary with cancellation status
    """
    if file_id not in active_transfers:
        return {"status": "error", "message": f"Unknown transfer ID: {file_id}"}
    
    transfer = active_transfers[file_id]
    transfer.close_file()
    transfer.status = "canceled"
    
    # If download, remove the partial file
    if transfer.direction == "download":
        try:
            if os.path.exists(transfer.file_path):
                os.remove(transfer.file_path)
        except Exception as e:
            logger.error(f"Error removing partial download: {e}")
    
    # Schedule cleanup
    asyncio.create_task(_cleanup_transfer(file_id))
    
    return {
        "file_id": file_id,
        "status": "canceled",
        "message": "Transfer canceled successfully"
    }

async def _cleanup_transfer(file_id: str, delay: float = 60.0) -> None:
    """
    Remove a completed/failed/canceled transfer from active transfers after a delay
    
    Args:
        file_id: Transfer ID
        delay: Seconds to wait before removing
    """
    await asyncio.sleep(delay)
    if file_id in active_transfers:
        transfer = active_transfers[file_id]
        transfer.close_file()
        del active_transfers[file_id]
    
    if file_id in transfer_callbacks:
        del transfer_callbacks[file_id]