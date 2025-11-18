#!/usr/bin/env python3
"""
IndexedCP Client Demo

Uploads files to the IndexedCP server running on port 3000.

Prerequisites:
    Run server_demo.py in another terminal first!
    
    Terminal 1: python examples/server_demo.py
    Terminal 2: python examples/client_demo.py
"""

import asyncio
import tempfile
import sys
import os
import time
import urllib.request
import urllib.error
import urllib.parse
from pathlib import Path
from indexedcp import IndexedCPClient


def check_server_running(url: str, max_attempts: int = 3) -> bool:
    """Check if the server is running by attempting to connect."""
    # Try to connect to the base URL (remove /upload)
    base_url = url.replace('/upload', '')
    
    for attempt in range(max_attempts):
        try:
            # Try to establish a connection to the server
            import socket
            parsed = urllib.parse.urlparse(base_url)
            host = parsed.hostname or 'localhost'
            port = parsed.port or 3000
            
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.settimeout(2)
            result = sock.connect_ex((host, port))
            sock.close()
            
            if result == 0:
                return True
        except Exception:
            pass
        
        if attempt < max_attempts - 1:
            time.sleep(1)
    
    return False


async def main():
    """Upload demo files to the server."""
    
    # Server configuration (must match server_demo.py)
    server_url = "http://localhost:3000/upload"
    api_key = "demo-key-12345"
    
    # Check if server is running
    if not check_server_running(server_url):
        print("ERROR: Server not running!")
        print("Start server first: python examples/server_demo.py")
        sys.exit(1)
    
    print("Server is running")
    
    # Create demo files
    
    # Small text file
    with tempfile.NamedTemporaryFile(mode='w', delete=False, suffix='.txt') as f:
        f.write("Hello, IndexedCP!\n")
        f.write("This is a test file from the Python client.\n")
        f.write("=" * 50 + "\n")
        f.write(f"Timestamp: {time.strftime('%Y-%m-%d %H:%M:%S')}\n")
        small_file = f.name
    
    # Larger file (multipart upload test)
    with tempfile.NamedTemporaryFile(mode='w', delete=False, suffix='_large.txt') as f:
        for i in range(100):
            f.write(f"Line {i}: This is test data for demonstrating chunked uploads.\n")
        large_file = f.name
    
    # Create client
    client = IndexedCPClient(
        server_url=server_url,
        api_key=api_key,
        chunk_size=1024,  # 1KB chunks for demo
        log_level="INFO"
    )
    
    try:
        await client.initialize()
        
        # Upload files
        await client.add_file(small_file)
        await client.add_file(large_file)
        
        results = await client.upload_buffered_files()
        
        print(f"\nUploaded {len(results)} file(s)")
        for client_file, server_file in results.items():
            print(f"  {Path(client_file).name} -> {server_file}")
        
    except Exception as e:
        print(f"ERROR: {e}")
        sys.exit(1)
        
    finally:
        await client.close()
        
        # Cleanup temp files
        try:
            os.unlink(small_file)
            os.unlink(large_file)
        except:
            pass


if __name__ == "__main__":
    asyncio.run(main())
