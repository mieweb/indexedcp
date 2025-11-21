#!/usr/bin/env python3
"""
Demo: Packets Storage
Shows how encrypted packets are created and stored in packets.json
"""

import asyncio
import sys
import os
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent / 'src'))

from indexedcp import IndexedCPClient


async def main():
    print("IndexedCP Client Demo - Encrypted Upload")
    print("-" * 40)
    
    # Setup demo directory
    demo_dir = Path(__file__).parent / 'demo_data'
    demo_dir.mkdir(exist_ok=True)
    
    # Create encrypted client with real server
    client = IndexedCPClient(
        server_url="http://localhost:3000/upload",
        api_key="demo-key-12345",
        storage_path=str(demo_dir / 'client.db'),
        encryption=True,
        chunk_size=1024,
        log_level="INFO"
    )
    
    await client.initialize()
    print("Client initialized")
    
    # Fetch the real server public key
    print("\nFetching server public key...")
    import urllib.request
    import json as json_lib
    
    try:
        public_key_url = "http://localhost:3000/public-key"
        req = urllib.request.Request(public_key_url)
        with urllib.request.urlopen(req) as response:
            key_data = json_lib.loads(response.read().decode('utf-8'))
        
        import time
        current_time_ms = time.time() * 1000
        
        # Cache the public key
        await client.storage.save_public_key({
            'kid': key_data['kid'],
            'publicKey': key_data['publicKey'],
            'fetchedAt': current_time_ms,
            'expiresAt': current_time_ms + (86400 * 1000)
        })
        print(f"Public key fetched (kid: {key_data['kid']})")
    except Exception as e:
        print(f"ERROR: Failed to fetch public key: {e}")
        print("Make sure server is running at http://localhost:3000")
        return
    
    # Create test file
    test_file = demo_dir / 'test_data.txt'
    with open(test_file, 'w') as f:
        f.write("This is test data for packet demo. " * 150)
    
    file_size = test_file.stat().st_size
    expected_packets = (file_size + 1023) // 1024
    
    print(f"\nCreated test file: {test_file.name} ({file_size} bytes)")
    print(f"Expected packets: {expected_packets}")
    
    print("\n" + "=" * 40)
    print("ENCRYPTING FILE")
    print("=" * 40)
    
    session_id = await client.start_stream(test_file.name)
    print(f"Session started: {session_id}")
    
    input("\nPress ENTER to encrypt and create packets...")
    print()
    
    # Encrypt file (creates packets)
    print("Encrypting and creating packets...")
    
    # Read and encrypt file in chunks
    with open(test_file, 'rb') as f:
        seq = 0
        while True:
            chunk = f.read(client.chunk_size)
            if not chunk:
                break
            
            await client.add_packet(session_id, chunk, seq)
            print(f"  Packet {seq} created ({len(chunk)} bytes)")
            seq += 1
    
    print(f"\nCreated {seq} encrypted packets")
    
    input("\nPress ENTER to view packet details...")
    
    print("\n" + "=" * 40)
    print("PACKET DETAILS")
    print("=" * 40)
    
    # Get all packets for this session
    packets = await client.storage.get_packets_by_session(session_id)
    print(f"\nTotal packets: {len(packets)}")
    
    for packet in packets[:2]:
        print(f"\nPacket {packet['seq']}:")
        print(f"  ID: {packet['id']}")
        print(f"  Status: {packet['status']}")
        print(f"  Ciphertext: {packet['ciphertext'][:50]}...")
    
    if len(packets) > 2:
        print(f"\n... and {len(packets) - 2} more packets")
    
    input("\nPress ENTER to upload packets to server...")
    print()
    
    print("\n" + "=" * 40)
    print("UPLOADING TO SERVER")
    print("=" * 40)
    
    print(f"\nUploading {len(packets)} packets to http://localhost:3000")
    
    try:
        result = await client.upload_buffered_files()
        
        print("Upload successful!")
        print(f"Server response: {result}")
        
        # Check updated packet statuses
        packets_after = await client.storage.get_packets_by_session(session_id)
        if packets_after:
            uploaded_count = sum(1 for p in packets_after if p['status'] == 'uploaded')
            print(f"Packets uploaded: {uploaded_count}/{len(packets_after)}")
        else:
            print("Packets cleaned up after upload")
        
    except Exception as e:
        print(f"\nUpload failed: {e}")
        print("Make sure server is running at http://localhost:3000")
    
    input("\nPress ENTER to cleanup packets...")
    
    # Cleanup session (removes packets and session)
    print("\nCleaning up...")
    await client.storage.cleanup_session(session_id)
    print("Session and packets cleaned up")
    
    await client.close()
    print("Demo complete!")


if __name__ == '__main__':
    asyncio.run(main())
