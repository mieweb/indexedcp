#!/usr/bin/env python3
"""
IndexedCP Python Client Example

This example demonstrates how to use the IndexedCP Python client
to upload files with chunked transfer and buffering.
"""

import sys
import os
from pathlib import Path

# Add the parent directory to Python path so we can import indexedcp
sys.path.insert(0, str(Path(__file__).parent.parent))

from indexedcp import IndexCPClient


def main():
    """Example demonstrating basic client usage."""
    
    # Create a test file
    test_file = Path(__file__).parent / "test_file.txt"
    with open(test_file, "w") as f:
        f.write("Hello from IndexedCP Python client!\n" * 100)
    
    print(f"Created test file: {test_file}")
    
    # Initialize client
    client = IndexCPClient()
    
    # Example 1: Add file to buffer and upload later
    print("\n=== Example 1: Buffered Upload ===")
    
    # Add file to buffer
    chunk_count = client.add_file(str(test_file))
    print(f"Added file to buffer with {chunk_count} chunks")
    
    # List buffered files
    buffered_files = client.get_buffered_files()
    print(f"Buffered files: {buffered_files}")
    
    # Upload buffered files (requires server to be running)
    # Uncomment the following lines when you have a server running:
    # try:
    #     results = client.upload_buffered_files("http://localhost:3000/upload")
    #     print(f"Upload results: {results}")
    # except Exception as e:
    #     print(f"Upload failed (server not running?): {e}")
    
    # Clear buffer for next example
    client.clear_buffer()
    
    # Example 2: Direct upload without buffering
    print("\n=== Example 2: Direct Upload (Buffer and Upload) ===")
    
    # Uncomment the following lines when you have a server running:
    # try:
    #     client.buffer_and_upload(str(test_file), "http://localhost:3000/upload")
    #     print("Direct upload completed!")
    # except Exception as e:
    #     print(f"Direct upload failed (server not running?): {e}")
    
    # Example 3: Custom chunk size
    print("\n=== Example 3: Custom Chunk Size ===")
    
    # Create client with smaller chunk size (64KB instead of 1MB)
    small_chunk_client = IndexCPClient(chunk_size=64 * 1024)
    chunk_count = small_chunk_client.add_file(str(test_file))
    print(f"Added file with 64KB chunks: {chunk_count} chunks")
    
    # Clean up
    small_chunk_client.clear_buffer()
    test_file.unlink()  # Delete test file
    print(f"Cleaned up test file: {test_file}")
    
    print("\n=== Example Complete ===")
    print("To test uploads, start the IndexedCP server:")
    print("  cd ../.. && node bin/indexcp server 3000 ./uploads")
    print("Then uncomment the upload examples in this script.")


if __name__ == "__main__":
    main()