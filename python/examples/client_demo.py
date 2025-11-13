#!/usr/bin/env python3
"""
IndexedCP Client Demo

Simple demonstration of uploading a file to the server.
Run this after starting server_demo.py
"""

import asyncio
import tempfile
import sys
from indexedcp import IndexedCPClient


async def main():
    # Check if server is running
    print("\n   Make sure the server is running first:")
    print("   python examples/server_demo.py")
    print()
    response = input("Is the server running? (y/n): ")
    if response.lower() != 'y':
        print("\nPlease start the server first.\n")
        sys.exit(0)
    
    # Create a demo file
    with tempfile.NamedTemporaryFile(mode='w', delete=False, suffix='.txt') as f:
        f.write("Hello, IndexedCP! This is a test file.\n")
        demo_file = f.name
    
    print(f"\n Uploading file: {demo_file}")
    print("=" * 50)
    
    # Create client and upload
    client = IndexedCPClient(
        server_url="http://localhost:3000/upload",
        api_key="demo-key-12345"
    )
    
    await client.initialize()
    await client.add_file(demo_file)
    results = await client.upload_buffered_files()
    await client.close()
    
    print(f"   Upload successful!")
    print(f"   Server filename: {list(results.values())[0]}")
    print(f"   Location: ./demo_uploads/\n")


if __name__ == "__main__":
    asyncio.run(main())
