#!/usr/bin/env python3
"""
IndexedCP Python Client Tests

Test suite for the IndexedCP Python client implementation using IndexedDB-like storage.
"""

import os
import sys
import tempfile
import unittest
from pathlib import Path

# Add the parent directory to path for importing indexedcp
sys.path.insert(0, str(Path(__file__).parent))

from indexedcp import IndexCPClient


def test_client_initialization():
    """Test client initialization."""
    print("Testing client initialization...")
    
    client = IndexCPClient()
    assert client.db_name == "indexcp"
    assert client.chunk_size == 1024 * 1024
    assert client.api_key is None
    
    # Test custom parameters
    custom_client = IndexCPClient(db_name="test", chunk_size=64*1024)
    assert custom_client.db_name == "test"
    assert custom_client.chunk_size == 64*1024
    
    print("✓ Client initialization test passed")


def test_database_operations():
    """Test IndexedDB-like database operations."""
    print("Testing IndexedDB-like database operations...")
    
    # Create temporary client
    with tempfile.TemporaryDirectory() as temp_dir:
        # Create client with custom database name
        client = IndexCPClient(db_name="test")
        
        # Verify database was created and can store data
        test_record = {
            'id': 'test-chunk-1',
            'fileName': 'test.txt',
            'chunkIndex': 0,
            'data': b'test data'
        }
        
        # Add test record
        client.db.add('chunks', test_record)
        
        # Retrieve and verify
        retrieved = client.db.get('chunks', 'test-chunk-1')
        assert retrieved is not None
        assert retrieved['fileName'] == 'test.txt'
        assert retrieved['chunkIndex'] == 0
        assert retrieved['data'] == b'test data'
        
        # Test get_all
        all_records = client.db.get_all('chunks')
        assert len(all_records) == 1
        
        # Test delete
        deleted = client.db.delete('chunks', 'test-chunk-1')
        assert deleted is True
        
        # Verify deletion
        retrieved_after_delete = client.db.get('chunks', 'test-chunk-1')
        assert retrieved_after_delete is None
    
    print("✓ IndexedDB-like database operations test passed")


def test_file_operations():
    """Test file operations."""
    print("Testing file operations...")
    
    with tempfile.TemporaryDirectory() as temp_dir:
        # Create test file
        test_file = Path(temp_dir) / "test.txt"
        test_content = "Hello, IndexedCP!\n" * 100
        with open(test_file, "w") as f:
            f.write(test_content)
        
        # Create client with temp db
        client = IndexCPClient(db_name="test", chunk_size=100)  # Small chunks for testing
        client.db_path = Path(temp_dir) / "test.db"
        client._init_db()
        
        # Test adding file
        chunk_count = client.add_file(str(test_file))
        assert chunk_count > 0
        
        # Test listing buffered files
        buffered_files = client.get_buffered_files()
        assert str(test_file) in buffered_files
        
        # Test clearing buffer
        client.clear_buffer()
        buffered_files = client.get_buffered_files()
        assert len(buffered_files) == 0
    
    print("✓ File operations test passed")


def test_api_key_handling():
    """Test API key handling."""
    print("Testing API key handling...")
    
    client = IndexCPClient()
    
    # Test environment variable
    original_key = os.environ.get("INDEXCP_API_KEY")
    try:
        os.environ["INDEXCP_API_KEY"] = "test-key-from-env"
        key = client.get_api_key_sync()
        assert key == "test-key-from-env"
        
        # Test cached key
        key2 = client.get_api_key_sync()
        assert key2 == "test-key-from-env"
        
        # Test direct setting
        client.api_key = "direct-key"
        key3 = client.get_api_key_sync()
        assert key3 == "direct-key"
        
    finally:
        if original_key:
            os.environ["INDEXCP_API_KEY"] = original_key
        elif "INDEXCP_API_KEY" in os.environ:
            del os.environ["INDEXCP_API_KEY"]
    
    print("✓ API key handling test passed")


def test_chunk_operations():
    """Test chunk creation and handling."""
    print("Testing chunk operations...")
    
    with tempfile.TemporaryDirectory() as temp_dir:
        # Create test file with known content
        test_file = Path(temp_dir) / "chunk_test.txt"
        test_content = b"A" * 150  # 150 bytes
        with open(test_file, "wb") as f:
            f.write(test_content)
        
        # Create client with small chunk size
        client = IndexCPClient(db_name="test", chunk_size=50)  # 50 byte chunks
        
        # Add file and verify chunks
        chunk_count = client.add_file(str(test_file))
        assert chunk_count == 3  # 150 bytes / 50 bytes per chunk = 3 chunks
        
        # Verify chunk data using IndexedDB-like interface
        all_chunks = client.db.get_all('chunks')
        
        assert len(all_chunks) == 3
        
        # Sort chunks by index for verification
        all_chunks.sort(key=lambda x: x['chunkIndex'])
        
        assert len(all_chunks[0]['data']) == 50  # First chunk: 50 bytes
        assert len(all_chunks[1]['data']) == 50  # Second chunk: 50 bytes  
        assert len(all_chunks[2]['data']) == 50  # Third chunk: 50 bytes
        
        # Verify content
        reconstructed = b"".join(chunk['data'] for chunk in all_chunks)
        assert reconstructed == test_content
    
    print("✓ Chunk operations test passed")


def run_all_tests():
    """Run all tests."""
    print("Running IndexedCP Python client tests...\n")
    
    try:
        test_client_initialization()
        test_database_operations()
        test_file_operations()
        test_api_key_handling()
        test_chunk_operations()
        
        print("\n✓ All tests passed!")
        return True
        
    except Exception as e:
        print(f"\n✗ Test failed: {e}")
        import traceback
        traceback.print_exc()
        return False


if __name__ == "__main__":
    success = run_all_tests()
    sys.exit(0 if success else 1)