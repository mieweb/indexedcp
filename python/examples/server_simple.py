#!/usr/bin/env python3
"""
Simple IndexedCP Server Example

This example demonstrates the simple server mode without authentication,
useful for development and testing.
"""

import sys
from pathlib import Path

# Add the parent directory to path for importing indexedcp
sys.path.insert(0, str(Path(__file__).parent.parent))

from indexedcp import create_simple_server


def main():
    """Run a simple IndexedCP server without authentication."""
    print("Starting Simple IndexedCP Server (No Authentication)...")
    print("This server is for development/testing only!")
    
    # Create simple server
    server = create_simple_server(
        output_file="./simple_upload.txt",  # All chunks appended to this file
        port=3002
    )
    
    print("\nTo test this server:")
    print("curl -X POST -d 'test data' http://localhost:3002/upload")
    print("")
    
    # Start the server
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nShutting down server...")
        server.shutdown()
        server.server_close()


if __name__ == "__main__":
    main()
