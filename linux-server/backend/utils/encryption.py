"""
Encryption utilities for secure data transmission between devices.
Provides AES-256 encryption/decryption for clipboard data, notifications, and messages.
"""

import os
import base64
import json
from typing import Dict, Any, Union
from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes
from cryptography.hazmat.primitives import padding
from cryptography.hazmat.backends import default_backend
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
from cryptography.hazmat.primitives import hashes

def generate_key(password: str, salt: bytes = None) -> Dict[str, bytes]:
    """
    Generate a secure AES-256 key from a password using PBKDF2.
    
    Args:
        password: Password to derive key from
        salt: Optional salt bytes, random if not provided
        
    Returns:
        Dict with 'key' and 'salt' bytes
    """
    if salt is None:
        salt = os.urandom(16)
    
    kdf = PBKDF2HMAC(
        algorithm=hashes.SHA256(),
        length=32,  # 32 bytes = 256 bits
        salt=salt,
        iterations=100000,
        backend=default_backend()
    )
    
    key = kdf.derive(password.encode())
    
    return {
        'key': key,
        'salt': salt
    }

def encrypt_data(data: Union[str, bytes, Dict[str, Any]], key: bytes) -> Dict[str, str]:
    """
    Encrypt data with AES-256 in CBC mode.
    
    Args:
        data: Data to encrypt (string, bytes or JSON-serializable dict)
        key: 32-byte encryption key
        
    Returns:
        Dict with base64-encoded 'data' and 'iv'
    """
    # Convert data to bytes
    if isinstance(data, dict):
        data_bytes = json.dumps(data).encode()
    elif isinstance(data, str):
        data_bytes = data.encode()
    else:
        data_bytes = data
    
    # Generate random IV
    iv = os.urandom(16)
    
    # Pad data to block size
    padder = padding.PKCS7(algorithms.AES.block_size).padder()
    padded_data = padder.update(data_bytes) + padder.finalize()
    
    # Encrypt
    cipher = Cipher(algorithms.AES(key), modes.CBC(iv), backend=default_backend())
    encryptor = cipher.encryptor()
    encrypted_data = encryptor.update(padded_data) + encryptor.finalize()
    
    # Encode as base64 for transmission
    return {
        'data': base64.b64encode(encrypted_data).decode('utf-8'),
        'iv': base64.b64encode(iv).decode('utf-8')
    }

def decrypt_data(encrypted_data: str, iv: str, key: bytes) -> bytes:
    """
    Decrypt data that was encrypted with AES-256 in CBC mode.
    
    Args:
        encrypted_data: Base64-encoded encrypted data
        iv: Base64-encoded initialization vector
        key: 32-byte encryption key
        
    Returns:
        Decrypted data as bytes
    """
    # Decode base64
    encrypted_bytes = base64.b64decode(encrypted_data)
    iv_bytes = base64.b64decode(iv)
    
    # Decrypt
    cipher = Cipher(algorithms.AES(key), modes.CBC(iv_bytes), backend=default_backend())
    decryptor = cipher.decryptor()
    padded_data = decryptor.update(encrypted_bytes) + decryptor.finalize()
    
    # Unpad
    unpadder = padding.PKCS7(algorithms.AES.block_size).unpadder()
    return unpadder.update(padded_data) + unpadder.finalize()

def decrypt_json(encrypted_data: str, iv: str, key: bytes) -> Dict[str, Any]:
    """
    Decrypt and parse JSON data.
    
    Args:
        encrypted_data: Base64-encoded encrypted data
        iv: Base64-encoded initialization vector
        key: 32-byte encryption key
        
    Returns:
        Parsed JSON as dict
    """
    decrypted_bytes = decrypt_data(encrypted_data, iv, key)
    return json.loads(decrypted_bytes.decode('utf-8'))

def secure_message(data: Dict[str, Any], shared_key: bytes) -> Dict[str, str]:
    """
    Create a secure message for transmission.
    
    Args:
        data: Message data as dictionary
        shared_key: Shared encryption key
        
    Returns:
        Dict with encrypted message ready for transmission
    """
    encrypted = encrypt_data(data, shared_key)
    return {
        'encrypted_data': encrypted['data'],
        'iv': encrypted['iv']
    }

def decrypt_message(message: Dict[str, str], shared_key: bytes) -> Dict[str, Any]:
    """
    Decrypt a secure message.
    
    Args:
        message: Encrypted message dict with 'encrypted_data' and 'iv'
        shared_key: Shared encryption key
        
    Returns:
        Decrypted message data as dict
    """
    return decrypt_json(
        message['encrypted_data'],
        message['iv'],
        shared_key
    )

def encrypt_to_json_string(data: Dict[str, Any], shared_key: bytes) -> str:
    """
    Encrypt and convert to JSON string for WebSocket transmission.
    
    Args:
        data: Data to encrypt
        shared_key: Shared encryption key
        
    Returns:
        JSON string ready for transmission
    """
    encrypted = secure_message(data, shared_key)
    encrypted['type'] = 'encrypted'  # Mark as encrypted message
    return json.dumps(encrypted)