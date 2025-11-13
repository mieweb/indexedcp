"""
IndexedCP - Python implementation
A minimal file upload system with optional encryption support.
"""

from .logger import create_logger
from .storage import BaseStorage, SQLiteStorage, create_storage
from .client import IndexedCPClient
from .server import IndexedCPServer
from .crypto_utils import CryptoUtils
from .keystores import BaseKeyStore, FileSystemKeyStore, create_keystore

__version__ = "0.1.0"
__all__ = [
    "create_logger",
    "BaseStorage",
    "SQLiteStorage",
    "create_storage",
    "IndexedCPClient",
    "IndexedCPServer",
    "CryptoUtils",
    "BaseKeyStore",
    "FileSystemKeyStore",
    "create_keystore"
]
