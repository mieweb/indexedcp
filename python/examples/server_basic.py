#!/usr/bin/env python3
"""
Basic IndexedCP Python Server Example

This example demonstrates how to create and run a basic IndexedCP server
that can receive chunked file uploads from clients.
"""

import sys
import os
from pathlib import Path

# Add the parent directory to path for importing indexedcp
sys.path.insert(0, str(Path(__file__).parent.parent))

from indexedcp import IndexCPServer


def main():
    """Run a basic IndexedCP server."""
    print("Starting Basic IndexedCP Server Example...")
    
    # Create server with default settings
    server = IndexCPServer(
        output_dir="./uploads",  # Save files to uploads directory
        port=3000,               # Listen on port 3000
        # api_key will be auto-generated
    )
    
    # Start the server (blocking call)
    try:
        server.listen()
    except KeyboardInterrupt:
        print("\nShutting down server...")
        server.close()


if __name__ == "__main__":
    main()
