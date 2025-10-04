"""
IndexedCP Python Package

A Python implementation of the IndexedCP file transfer system,
now with IndexedDB-like storage for better JavaScript compatibility.
"""

from .server import IndexCPServer, create_simple_server
from .client import IndexCPClient
from .indexeddb import openDB, open_db, open_db_sync

__version__ = "1.0.0"
__all__ = [
    "IndexCPServer", 
    "create_simple_server", 
    "IndexCPClient",
    "openDB",
    "open_db", 
    "open_db_sync"
]