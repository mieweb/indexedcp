#!/usr/bin/env python3
"""
IndexedCP Server with Custom Filename Generator

This example shows how to use a custom filename generator function
to control how uploaded files are named on the server.
"""

import sys
import os
import time
from pathlib import Path

# Add the parent directory to path for importing indexedcp
sys.path.insert(0, str(Path(__file__).parent.parent))

from indexedcp import IndexCPServer


def custom_filename_generator(client_filename, chunk_index, request_handler):
    """
    Custom filename generator that adds timestamp and ensures unique names.
    
    Args:
        client_filename: Original filename from client
        chunk_index: Current chunk index
        request_handler: HTTP request handler instance
    
    Returns:
        Generated filename to use on server
    """
    # Get base name and extension
    base_name = os.path.splitext(os.path.basename(client_filename))[0]
    extension = os.path.splitext(client_filename)[1]
    
    # Add timestamp to make filename unique
    timestamp = int(time.time())
    
    # Generate filename: basename_timestamp.ext
    return f"{base_name}_{timestamp}{extension}"


def main():
    """Run IndexedCP server with custom filename generator."""
    print("Starting IndexedCP Server with Custom Filename Generator...")
    
    # Create server with custom filename generator
    server = IndexCPServer(
        output_dir="./custom_uploads",
        port=3001,
        api_key="custom-server-key-123",
        filename_generator=custom_filename_generator
    )
    
    print("\nThis server will:")
    print("- Add timestamps to uploaded filenames")
    print("- Save files to ./custom_uploads directory")
    print("- Use API key: custom-server-key-123")
    print("")
    
    # Start the server
    try:
        server.listen()
    except KeyboardInterrupt:
        print("\nShutting down server...")
        server.close()


if __name__ == "__main__":
    main()
