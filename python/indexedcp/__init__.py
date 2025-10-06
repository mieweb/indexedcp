"""
IndexedCP Python Client and Server

A Python implementation of the IndexedCP client and server for secure, efficient, and resumable file transfer.
"""

from .client import IndexCPClient
from .server import IndexCPServer, create_simple_server

__version__ = "1.0.0"
__all__ = ["IndexCPClient", "IndexCPServer", "create_simple_server"]