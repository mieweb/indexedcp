#!/usr/bin/env python3
"""
Integration test for IndexedCP Python client with Python server.

This test verifies that the Python client and Python server work together correctly,
providing a complete end-to-end test of the Python IndexedCP implementation.
"""

import sys
import os
import time
import threading
import requests
from pathlib import Path

# Add the current directory to Python path so we can import indexedcp
sys.path.insert(0, str(Path(__file__).parent))

from indexedcp import IndexCPClient, IndexCPServer


def wait_for_server(url, timeout=10):
    """Wait for server to be ready."""
    start_time = time.time()
    while time.time() - start_time < timeout:
        try:
            response = requests.get(url, timeout=1)
            return True
        except requests.RequestException:
            time.sleep(0.5)
    return False


def test_integration():
    """Test Python client with Python server."""
    
    # Create test file
    test_file = Path(__file__).parent / "integration_test.txt"
    test_content = "Hello from Python IndexedCP client integration test!\n" * 100
    
    with open(test_file, "w") as f:
        f.write(test_content)
    
    print(f"Created test file: {test_file} ({len(test_content)} bytes)")
    
    # Setup server
    uploads_dir = Path(__file__).parent / "test_uploads"
    uploads_dir.mkdir(exist_ok=True)
    
    # Create Python server
    api_key = "test-api-key-for-integration"
    server = IndexCPServer(
        output_dir=str(uploads_dir),
        port=3001,  # Use different port to avoid conflicts
        api_key=api_key
    )
    
    try:
        print("Starting Python IndexedCP server...")
        
        # Start server in background thread
        def server_ready():
            print("Server started successfully!")
        
        server.start(callback=server_ready)
        
        # Wait for server to start
        if not wait_for_server("http://localhost:3001", timeout=10):
            print("Server failed to start in time")
            return False
        
        # Test Python client
        print("\n=== Testing Python Client ===")
        
        # Set API key for client
        os.environ["INDEXCP_API_KEY"] = api_key
        
        client = IndexCPClient()
        
        # Test 1: Add file to buffer
        print("1. Adding file to buffer...")
        chunk_count = client.add_file(str(test_file))
        print(f"   Added file with {chunk_count} chunks")
        
        # Test 2: List buffered files
        print("2. Listing buffered files...")
        buffered_files = client.get_buffered_files()
        print(f"   Buffered files: {buffered_files}")
        
        # Test 3: Upload buffered files
        print("3. Uploading buffered files...")
        try:
            results = client.upload_buffered_files("http://localhost:3001/upload")
            print(f"   Upload results: {results}")
            
            # Check if file was uploaded
            uploaded_files = list(uploads_dir.glob("*"))
            print(f"   Files in upload directory: {[f.name for f in uploaded_files]}")
            
            if uploaded_files:
                uploaded_file = uploaded_files[0]
                with open(uploaded_file, "r") as f:
                    uploaded_content = f.read()
                
                if uploaded_content == test_content:
                    print("   ✓ File content matches!")
                else:
                    print("   ✗ File content mismatch!")
                    return False
            else:
                print("   ✗ No files found in upload directory!")
                return False
                
        except Exception as e:
            print(f"   Upload failed: {e}")
            return False
        
        # Test 4: Direct upload (buffer and upload)
        print("4. Testing direct upload...")
        
        # Create another test file
        test_file2 = Path(__file__).parent / "integration_test2.txt"
        with open(test_file2, "w") as f:
            f.write("Direct upload test content!\n" * 50)
        
        try:
            client.buffer_and_upload(str(test_file2), "http://localhost:3001/upload")
            print("   ✓ Direct upload completed!")
        except Exception as e:
            print(f"   Direct upload failed: {e}")
            return False
        finally:
            test_file2.unlink(missing_ok=True)
        
        print("\n✓ All tests passed!")
        return True
        
    except Exception as e:
        print(f"Integration test failed: {e}")
        import traceback
        traceback.print_exc()
        return False
        
    finally:
        # Clean up
        test_file.unlink(missing_ok=True)
        
        # Shutdown server
        if server:
            print("\nShutting down server...")
            server.close()
        
        # Clean up upload directory
        if uploads_dir.exists():
            for f in uploads_dir.glob("*"):
                f.unlink(missing_ok=True)
            uploads_dir.rmdir()


if __name__ == "__main__":
    success = test_integration()
    sys.exit(0 if success else 1)