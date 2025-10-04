#!/usr/bin/env python3
"""
Test script for IndexedDB-like interface in Python IndexedCP
"""

import sys
import os
from pathlib import Path

# Add the parent directory to path for importing indexedcp
sys.path.insert(0, str(Path(__file__).parent))

from indexedcp import IndexCPClient, openDB


def test_indexeddb_interface():
    """Test the IndexedDB-like interface."""
    print("Testing IndexedDB-like interface...")
    
    # Test direct IndexedDB usage
    def upgrade_db(db):
        if 'test_store' not in db.object_store_names:
            db.create_object_store('test_store', {'keyPath': 'id'})
    
    db = openDB('test_db', 1, upgrade_db)
    
    # Test adding data
    test_data = {
        'id': 'test1',
        'fileName': 'test.txt',
        'chunkIndex': 0,
        'data': b'Hello, IndexedDB!'
    }
    
    db.add('test_store', test_data)
    print("✓ Data added to IndexedDB-like store")
    
    # Test retrieving data
    retrieved = db.get('test_store', 'test1')
    print(f"✓ Data retrieved: {retrieved['fileName']}")
    
    # Test getting all data
    all_data = db.get_all('test_store')
    print(f"✓ All data count: {len(all_data)}")
    
    # Test client with IndexedDB-like storage
    print("\nTesting IndexCPClient with IndexedDB-like storage...")
    client = IndexCPClient(db_name="test_client")
    
    # Create a test file
    test_file = Path(__file__).parent / "test_file.txt"
    with open(test_file, 'w') as f:
        f.write("This is a test file for IndexedCP with IndexedDB-like storage!")
    
    try:
        # Add file to buffer
        chunk_count = client.add_file(str(test_file))
        print(f"✓ File added with {chunk_count} chunks")
        
        # Check buffered files
        buffered = client.get_buffered_files()
        print(f"✓ Buffered files: {buffered}")
        
        # Clear buffer
        client.clear_buffer()
        print("✓ Buffer cleared")
        
        print("\n🎉 All tests passed! IndexedDB-like interface is working!")
        
    finally:
        # Clean up
        if test_file.exists():
            test_file.unlink()
        db.close()


if __name__ == "__main__":
    test_indexeddb_interface()
