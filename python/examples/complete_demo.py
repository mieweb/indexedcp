#!/usr/bin/env python3
"""
Complete IndexedCP Client-Server Example

This example demonstrates both client and server working together
in the same script for testing purposes.
"""

import sys
import time
import threading
from pathlib import Path

# Add the parent directory to path for importing indexedcp
sys.path.insert(0, str(Path(__file__).parent.parent))

from indexedcp import IndexCPClient, IndexCPServer


def create_test_file():
    """Create a test file to upload."""
    test_file = "test_upload.txt"
    with open(test_file, 'w') as f:
        f.write("This is a test file for IndexedCP upload.\n")
        f.write("It contains multiple lines of text.\n")
        f.write("The client will chunk this file and upload it.\n")
        f.write("The server will reassemble the chunks.\n")
    return test_file


def run_server(api_key):
    """Run the server in a separate thread."""
    server = IndexCPServer(
        output_dir="./demo_uploads",
        port=3003,
        api_key=api_key
    )
    
    def server_ready():
        print("✓ Server is ready for uploads!")
    
    server.listen(callback=server_ready)


def run_client(api_key):
    """Run the client after server is ready."""
    print("\n=== CLIENT OPERATIONS ===")
    
    # Create test file
    test_file = create_test_file()
    print(f"✓ Created test file: {test_file}")
    
    # Create client
    client = IndexCPClient(chunk_size=32)  # Small chunks for demo
    client.api_key = api_key
    
    # Add file to buffer
    chunks = client.add_file(test_file)
    print(f"✓ Added file to buffer ({chunks} chunks)")
    
    # List buffered files
    buffered = client.get_buffered_files()
    print(f"✓ Buffered files: {buffered}")
    
    # Upload to server
    print("✓ Uploading to server...")
    results = client.upload_buffered_files("http://localhost:3003/upload")
    
    print(f"✓ Upload complete! Results: {results}")
    
    # Clean up
    import os
    os.remove(test_file)
    client.clear_buffer()
    print("✓ Cleaned up test file and buffer")


def main():
    """Run the complete client-server demo."""
    print("=== IndexedCP Complete Demo ===")
    print("This demo will:")
    print("1. Start a server")
    print("2. Create a test file")
    print("3. Upload the file using the client")
    print("4. Show the results")
    print("")
    
    # Shared API key
    api_key = "demo-api-key-12345"
    
    # Start server in background thread
    print("=== STARTING SERVER ===")
    server_thread = threading.Thread(target=run_server, args=(api_key,), daemon=True)
    server_thread.start()
    
    # Wait for server to start
    time.sleep(2)
    
    try:
        # Run client
        run_client(api_key)
        
        print("\n=== DEMO COMPLETE ===")
        print("Check the ./demo_uploads directory for the uploaded file!")
        
    except Exception as e:
        print(f"Error during demo: {e}")
    
    print("\nPress Ctrl+C to exit...")
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        print("\nExiting demo...")


if __name__ == "__main__":
    main()
