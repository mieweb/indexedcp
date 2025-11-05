#!/usr/bin/env python3
"""
IndexedCP Client Demo

This script demonstrates various client operations including:
1. Simple file upload
2. Multiple file upload
3. Large file upload (chunked)
4. Background upload with retry

Run this after starting server_demo.py
"""

import asyncio
import tempfile
import sys
import os
from pathlib import Path
from indexedcp.client import IndexedCPClient

# Global variable to track database path for cleanup
DB_PATH = "./demo_client.db"


async def create_demo_files():
    """Create demo files for upload testing."""
    print(" Creating demo files...")
    
    demo_files = {}
    
    # 1. Small text file
    small_file = tempfile.NamedTemporaryFile(
        mode='w',
        delete=False,
        suffix='_small.txt',
        prefix='demo_'
    )
    small_file.write("Hello, IndexedCP! This is a small test file.\n")
    small_file.write("It contains just a few lines of text.\n")
    small_file.close()
    demo_files['small'] = small_file.name
    print(f"   ✓ Created small file: {Path(small_file.name).name}")
    
    # 2. Medium text file (will be chunked)
    medium_file = tempfile.NamedTemporaryFile(
        mode='w',
        delete=False,
        suffix='_medium.txt',
        prefix='demo_'
    )
    for i in range(200):
        medium_file.write(f"Line {i}: This is a medium-sized file for chunking demonstration.\n")
    medium_file.close()
    demo_files['medium'] = medium_file.name
    print(f"   ✓ Created medium file: {Path(medium_file.name).name}")
    
    # 3. Large binary file (3.5MB to create multiple chunks)
    large_file = tempfile.NamedTemporaryFile(
        mode='wb',
        delete=False,
        suffix='_large.bin',
        prefix='demo_'
    )
    large_file.write(b'X' * (3 * 1024 * 1024 + 512 * 1024))  # 3.5MB
    large_file.close()
    demo_files['large'] = large_file.name
    print(f"   ✓ Created large file: {Path(large_file.name).name} (3.5 MB)")
    
    # 4. Document file
    doc_file = tempfile.NamedTemporaryFile(
        mode='w',
        delete=False,
        suffix='_document.txt',
        prefix='report_2024_'
    )
    doc_file.write("=== IndexedCP Demo Report ===\n\n")
    doc_file.write("This demonstrates file upload functionality.\n")
    doc_file.write("The file will be chunked and uploaded to the server.\n" * 10)
    doc_file.close()
    demo_files['document'] = doc_file.name
    print(f"   ✓ Created document file: {Path(doc_file.name).name}")
    
    print()
    return demo_files


async def demo_simple_upload(client, demo_files):
    """Demo 1: Simple single file upload."""
    print("=" * 70)
    print(" Demo 1: Simple File Upload")
    print("=" * 70)
    print("Uploading a small text file...")
    print()
    
    # Add file to buffer
    file_path = demo_files['small']
    chunk_count = await client.add_file(file_path)
    print(f"   • File: {Path(file_path).name}")
    print(f"   • Size: {Path(file_path).stat().st_size} bytes")
    print(f"   • Chunks: {chunk_count}")
    print()
    
    # Pause to inspect database
    print("    Chunks stored in database: demo_client.db")
    print("   You can inspect the database now:")
    print(f"      sqlite3 {DB_PATH} \"SELECT key, length(data) as json_size FROM chunks;\"")
    print(f"      sqlite3 {DB_PATH} \"SELECT key, json_extract(data, '$.chunkIndex') as chunk FROM chunks;\"")
    print()
    input("     Press Enter to upload these chunks to server...")
    print()
    
    # Upload to server
    print("    Uploading to server...")
    results = await client.upload_buffered_files()
    
    for client_path, server_filename in results.items():
        print(f"    Uploaded successfully!")
        print(f"   • Server filename: {server_filename}")
        print(f"   • Location: ./demo_uploads/{server_filename}")
    
    print()
    input("Press Enter to continue to next demo...")
    print()


async def demo_multiple_files(client, demo_files):
    """Demo 2: Multiple files upload."""
    print("=" * 70)
    print(" Demo 2: Multiple Files Upload (Batch)")
    print("=" * 70)
    print("Uploading multiple files in one batch...")
    print()
    
    files_to_upload = ['medium', 'document']
    total_size = 0
    
    # Add all files to buffer
    for key in files_to_upload:
        file_path = demo_files[key]
        chunk_count = await client.add_file(file_path)
        file_size = Path(file_path).stat().st_size
        total_size += file_size
        
        print(f"   • Added: {Path(file_path).name}")
        print(f"     Size: {file_size:,} bytes, Chunks: {chunk_count}")
    
    print()
    print(f"   Total size: {total_size:,} bytes")
    print()
    
    # Pause to inspect database
    print("    All chunks stored in database")
    print("   Inspect chunks:")
    print(f"      sqlite3 {DB_PATH} \"SELECT COUNT(*) as total_chunks FROM chunks;\"")
    print(f"      sqlite3 {DB_PATH} \"SELECT key, json_extract(data, '$.fileName') as file FROM chunks;\"")
    print()
    input("     Press Enter to upload all chunks to server...")
    print()
    
    # Upload all files
    print("    Uploading all files to server...")
    results = await client.upload_buffered_files()
    
    print(f"    All {len(results)} files uploaded successfully!")
    for client_path, server_filename in results.items():
        print(f"      • {Path(client_path).name} → {server_filename}")
    
    print()
    input("Press Enter to continue to next demo...")
    print()


async def demo_large_file(client, demo_files):
    """Demo 3: Large file with chunking."""
    print("=" * 70)
    print(" Demo 3: Large File Upload (Chunked)")
    print("=" * 70)
    print("Uploading a large binary file with automatic chunking...")
    print()
    
    file_path = demo_files['large']
    file_size = Path(file_path).stat().st_size
    
    print(f"   • File: {Path(file_path).name}")
    print(f"   • Size: {file_size:,} bytes ({file_size / 1024:.1f} KB)")
    print(f"   • Chunk size: 1 MB")
    print()
    
    # Add file with progress tracking
    print("    Chunking file...")
    chunk_count = await client.add_file(file_path)
    
    print(f"    File split into {chunk_count} chunks")
    print()
    
    # Pause to inspect database
    print("    Large file chunks stored in database")
    print("   Each chunk is stored separately. Inspect with:")
    print(f"      sqlite3 {DB_PATH} \"SELECT key, json_extract(data, '$.chunkIndex') as idx, length(json_extract(data, '$.data'))/2 as bytes FROM chunks WHERE key LIKE '%large%';\"")
    print()
    print("    Data structure explanation:")
    print("      • Each row is a JSON object with: id, fileName, chunkIndex, data (hex), retryMetadata")
    print("      • 'data' field contains file content as hex string (2 chars per byte)")
    print(f"      • This {chunk_count}-chunk file will reassemble correctly on the server")
    print()
    input("     Press Enter to upload and reassemble on server...")
    print()
    
    print(f"    Uploading {chunk_count} chunks to server...")
    
    # Upload with visual feedback
    results = await client.upload_buffered_files()
    
    for client_path, server_filename in results.items():
        print(f"    Upload complete!")
        print(f"      • Server filename: {server_filename}")
        print(f"      • All {chunk_count} chunks reassembled on server")
    
    print()
    input("Press Enter to continue to next demo...")
    print()


async def demo_background_upload(client, demo_files):
    """Demo 4: Background upload with retry."""
    print("=" * 70)
    print(" Demo 4: Background Upload (Automatic)")
    print("=" * 70)
    print("Demonstrating background upload with automatic processing...")
    print()
    
    # Add multiple files
    files_to_upload = ['small', 'medium', 'document']
    print("    Adding files to buffer...")
    
    for key in files_to_upload:
        file_path = demo_files[key]
        await client.add_file(file_path)
        print(f"      • Buffered: {Path(file_path).name}")
    
    print()
    print("    Starting background upload process...")
    print("   Files will be uploaded automatically in the background")
    print()
    
    # Start background upload
    await client.start_upload_background(check_interval=1.0)
    
    # Wait and show progress
    print("    Uploading (this happens in background)...")
    for i in range(5):
        await asyncio.sleep(1)
        remaining = await client.storage.load_all()
        if len(remaining) == 0:
            print(f"    All files uploaded! ({i+1}s)")
            break
        print(f"      • {len(remaining)} chunks remaining...")
    
    # Stop background upload
    await client.stop_upload_background()
    
    print()
    print("    Background upload completed!")
    print("   This is useful for unreliable networks - retries automatically")
    
    print()
    input("Press Enter to finish demo...")
    print()


async def cleanup_demo_files(demo_files):
    """Clean up temporary demo files."""
    print(" Cleaning up demo files...")
    for file_path in demo_files.values():
        try:
            Path(file_path).unlink()
        except Exception:
            pass
    print("   ✓ Demo files cleaned up")
    print()


def cleanup_database():
    """Clean up database files."""
    print(" Cleaning up database files...")
    try:
        if os.path.exists(DB_PATH):
            os.unlink(DB_PATH)
        for ext in ['-wal', '-shm']:
            db_file = DB_PATH + ext
            if os.path.exists(db_file):
                os.unlink(db_file)
        print("   ✓ Database files cleaned up")
    except Exception as e:
        print(f"     Could not clean database: {e}")
    print()


async def main():
    """Run all client demos."""
    print()
    print("=" * 70)
    print(" IndexedCP Client Demo")
    print("=" * 70)
    print()
    print("This demo will showcase various upload features:")
    print("   1. Simple single file upload")
    print("   2. Multiple files batch upload")
    print("   3. Large file with chunking")
    print("   4. Background upload with auto-retry")
    print()
    print("  Make sure the server is running (python server_demo.py)")
    print()
    
    response = input("Is the server running? (y/n): ")
    if response.lower() != 'y':
        print()
        print("Please start the server first:")
        print("   python examples/server_demo.py")
        print()
        return
    
    print()
    print("=" * 70)
    print(" Setting Up Client")
    print("=" * 70)
    
    # Create demo files
    demo_files = await create_demo_files()
    
    # Initialize client
    print(" Connecting to server...")
    client = IndexedCPClient(
        server_url="http://localhost:3000/upload",
        api_key="demo-key-12345",
        storage_path=DB_PATH,
        chunk_size=1024 * 1024,  # 1MB chunks
        log_level="INFO"
    )
    
    await client.initialize()
    print("   ✓ Client initialized")
    print()
    
    input("Press Enter to start demos...")
    print()
    
    try:
        # Run demos
        await demo_simple_upload(client, demo_files)
        await demo_multiple_files(client, demo_files)
        await demo_large_file(client, demo_files)
        await demo_background_upload(client, demo_files)
        
        # Final summary
        print("=" * 70)
        print(" Demo Complete!")
        print("=" * 70)
        print()
        print(" Uploaded files are located in: ./demo_uploads/")
        print()
        print("To view uploaded files:")
        print("   ls -lh demo_uploads/")
        print()
        print("=" * 70)
        
    finally:
        await client.close()
        await cleanup_demo_files(demo_files)
        cleanup_database()


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print()
        print("\n Demo interrupted by user")
        cleanup_database()
        sys.exit(0)
