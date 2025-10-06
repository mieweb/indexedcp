#!/usr/bin/env python3
"""
Simple unit tests for the IndexedCP Python client.
"""

import sys
import os
import tempfile
import sqlite3
from pathlib import Path

# Add the current directory to Python path so we can import indexedcp
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
    """Test database operations."""
    print("Testing database operations...")
    
    # Create temporary client
    with tempfile.TemporaryDirectory() as temp_dir:
        # Override the db path to use temp directory
        client = IndexCPClient(db_name="test")
        client.db_path = Path(temp_dir) / "test.db"
        client._init_db()
        
        # Verify database was created with correct schema
        with sqlite3.connect(client.db_path) as conn:
            cursor = conn.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='chunks'")
            assert cursor.fetchone() is not None
            
            # Test table structure
            cursor = conn.execute("PRAGMA table_info(chunks)")
            columns = [row[1] for row in cursor.fetchall()]
            expected_columns = ['id', 'file_name', 'chunk_index', 'data']
            assert all(col in columns for col in expected_columns)
    
    print("✓ Database operations test passed")


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
        client.db_path = Path(temp_dir) / "test.db"
        client._init_db()
        
        # Add file and verify chunks
        chunk_count = client.add_file(str(test_file))
        assert chunk_count == 3  # 150 bytes / 50 bytes per chunk = 3 chunks
        
        # Verify chunk data in database
        with sqlite3.connect(client.db_path) as conn:
            cursor = conn.execute("SELECT chunk_index, data FROM chunks ORDER BY chunk_index")
            chunks = cursor.fetchall()
            
            assert len(chunks) == 3
            assert len(chunks[0][1]) == 50  # First chunk: 50 bytes
            assert len(chunks[1][1]) == 50  # Second chunk: 50 bytes  
            assert len(chunks[2][1]) == 50  # Third chunk: 50 bytes
            
            # Verify content
            reconstructed = b"".join(chunk[1] for chunk in chunks)
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