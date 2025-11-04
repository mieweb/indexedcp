"""
Unit tests for basic IndexedCPClient implementation
"""

import pytest
import asyncio
import tempfile
import os
from pathlib import Path

from indexedcp.client import IndexedCPClient


class TestIndexedCPClient:
    """Test suite for basic IndexedCPClient implementation"""
    
    @pytest.fixture
    async def client(self):
        """Create a temporary client instance"""
        with tempfile.NamedTemporaryFile(delete=False, suffix='.db') as tmp:
            db_path = tmp.name
        
        client = IndexedCPClient(
            server_url="http://localhost:3000",
            api_key="test-key",
            storage_path=db_path,
            chunk_size=1024  # Small chunks for testing
        )
        
        await client.initialize()
        
        yield client
        
        await client.close()
        
        # Cleanup
        try:
            os.unlink(db_path)
            # Also remove WAL and SHM files if they exist
            for ext in ['-wal', '-shm']:
                wal_file = db_path + ext
                if os.path.exists(wal_file):
                    os.unlink(wal_file)
        except Exception:
            pass
    
    @pytest.fixture
    def test_file(self):
        """Create a temporary test file"""
        with tempfile.NamedTemporaryFile(mode='w', delete=False, suffix='.txt') as f:
            f.write("Hello, IndexedCP! " * 100)  # Write some content
            temp_path = f.name
        
        yield temp_path
        
        # Cleanup
        try:
            os.unlink(temp_path)
        except Exception:
            pass
    
    @pytest.mark.asyncio
    async def test_initialize(self, client):
        """Test client initialization"""
        assert client.storage is not None
        
        # Verify storage was initialized  
        assert client.storage.connection is not None
    
    @pytest.mark.asyncio
    async def test_constructor_defaults(self):
        """Test client constructor with default values"""
        client = IndexedCPClient()
        
        assert client.server_url is None
        assert client.chunk_size == 1024 * 1024  # 1MB default
        assert client.encryption is False
        # Default storage path is in home directory
        assert '.indexcp/db/client.db' in client.storage_path
    
    @pytest.mark.asyncio
    async def test_constructor_custom_values(self):
        """Test client constructor with custom values"""
        client = IndexedCPClient(
            server_url="http://example.com",
            api_key="custom-key",
            storage_path="./custom.db",
            chunk_size=2048
        )
        
        assert client.server_url == "http://example.com"
        assert client.api_key == "custom-key"
        assert client.storage_path == "./custom.db"
        assert client.chunk_size == 2048
    
    @pytest.mark.asyncio
    async def test_encryption_not_supported(self):
        """Test that encryption raises NotImplementedError"""
        with pytest.raises(NotImplementedError, match="Encryption not supported"):
            IndexedCPClient(encryption=True)
    
    @pytest.mark.asyncio
    async def test_add_file_basic(self, client, test_file):
        """Test adding a file returns chunk count"""
        chunk_count = await client.add_file(test_file)
        
        assert isinstance(chunk_count, int)
        assert chunk_count > 0
    
    @pytest.mark.asyncio
    async def test_add_file_chunking(self, client):
        """Test file chunking with known content"""
        # Create a file with known size
        with tempfile.NamedTemporaryFile(mode='wb', delete=False) as f:
            # Write exactly 2.5 chunks worth of data (2560 bytes with 1024 chunk size)
            f.write(b'A' * 2560)
            temp_path = f.name
        
        try:
            chunk_count = await client.add_file(temp_path)
            
            assert chunk_count == 3  # Should create 3 chunks
        finally:
            os.unlink(temp_path)
    
    @pytest.mark.asyncio
    async def test_add_file_nonexistent(self, client):
        """Test adding a non-existent file raises FileNotFoundError"""
        with pytest.raises(FileNotFoundError):
            await client.add_file('/nonexistent/file.txt')
    
    @pytest.mark.asyncio
    async def test_add_file_not_initialized(self, test_file):
        """Test adding file before initialization raises RuntimeError"""
        client = IndexedCPClient()
        
        with pytest.raises(RuntimeError, match="not initialized"):
            await client.add_file(test_file)
    
    @pytest.mark.asyncio
    async def test_context_manager(self, test_file):
        """Test client as async context manager"""
        with tempfile.NamedTemporaryFile(delete=False, suffix='.db') as tmp:
            db_path = tmp.name
        
        try:
            async with IndexedCPClient(storage_path=db_path) as client:
                assert client.storage is not None
                
                # Should be able to use client within context
                chunk_count = await client.add_file(test_file)
                assert chunk_count > 0
            
            # Connection should be closed after context exit
            # (We can't check this directly, but verify cleanup worked)
        finally:
            # Cleanup
            try:
                os.unlink(db_path)
                for ext in ['-wal', '-shm']:
                    wal_file = db_path + ext
                    if os.path.exists(wal_file):
                        os.unlink(wal_file)
            except Exception:
                pass
    
    @pytest.mark.asyncio
    async def test_close(self, client):
        """Test closing client connection"""
        assert client.storage is not None
        
        await client.close()
        
        assert client.storage is None
    
    @pytest.mark.asyncio
    async def test_large_file_chunking(self, client):
        """Test chunking of a larger file"""
        # Create a 5KB file (should create 5 chunks with 1024 byte chunk size)
        with tempfile.NamedTemporaryFile(mode='wb', delete=False) as f:
            f.write(b'X' * 5120)
            temp_path = f.name
        
        try:
            chunk_count = await client.add_file(temp_path)
            
            assert chunk_count == 5
            
            # Verify all chunks stored
            all_chunks = await client.storage.load_all()
            file_chunks = [c for c in all_chunks if c.get('fileName') == temp_path]
            assert len(file_chunks) == 5
        finally:
            os.unlink(temp_path)


class TestClientValidation:
    """Test suite for client input validation and error handling"""
    
    @pytest.mark.asyncio
    async def test_invalid_storage_path(self):
        """Test client with invalid storage path"""
        client = IndexedCPClient(storage_path='/invalid/path/that/does/not/exist/db.sqlite')
        
        # Should raise error during initialization due to invalid path
        with pytest.raises(Exception):
            await client.initialize()
    
    @pytest.mark.asyncio
    async def test_add_directory_instead_of_file(self):
        """Test adding a directory raises ValueError"""
        with tempfile.TemporaryDirectory() as tmpdir:
            client = IndexedCPClient(storage_path=f'{tmpdir}/test.db')
            await client.initialize()
            
            try:
                with pytest.raises(ValueError, match="Not a file"):
                    await client.add_file(tmpdir)
            finally:
                await client.close()
    
    @pytest.mark.asyncio
    async def test_upload_without_server_url(self):
        """Test upload without server URL raises ValueError"""
        with tempfile.NamedTemporaryFile(delete=False, suffix='.db') as tmp:
            db_path = tmp.name
        
        try:
            client = IndexedCPClient(storage_path=db_path)
            await client.initialize()
            
            with pytest.raises(ValueError, match="server_url required"):
                await client.upload_buffered_files()
            
            await client.close()
        finally:
            os.unlink(db_path)
    
    @pytest.mark.asyncio
    async def test_upload_without_api_key(self):
        """Test upload without API key raises ValueError"""
        with tempfile.NamedTemporaryFile(delete=False, suffix='.db') as tmp:
            db_path = tmp.name
        
        try:
            client = IndexedCPClient(
                server_url="http://localhost:3000",
                storage_path=db_path
            )
            await client.initialize()
            
            # Create a test file and add it
            with tempfile.NamedTemporaryFile(mode='w', delete=False) as f:
                f.write("test")
                test_file = f.name
            
            try:
                await client.add_file(test_file)
                
                # Clear API key
                client.api_key = None
                
                with pytest.raises(ValueError, match="api_key required"):
                    await client.upload_buffered_files()
            finally:
                os.unlink(test_file)
                await client.close()
        finally:
            os.unlink(db_path)
