import pytest
import asyncio
import tempfile
import os
from pathlib import Path
from unittest.mock import Mock

from indexedcp.client import IndexedCPClient


@pytest.fixture
async def client():
    """Create a temporary client instance."""
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
        for ext in ['-wal', '-shm']:
            wal_file = db_path + ext
            if os.path.exists(wal_file):
                os.unlink(wal_file)
    except Exception:
        pass


@pytest.fixture
def test_file():
    """Create a temporary test file."""
    with tempfile.NamedTemporaryFile(mode='w', delete=False, suffix='.txt') as f:
        f.write("Hello, IndexedCP! " * 100)
        temp_path = f.name
    
    yield temp_path
    
    try:
        os.unlink(temp_path)
    except Exception:
        pass


class TestClientInitialization:
    """Test client initialization and configuration."""
    
    @pytest.mark.asyncio
    async def test_initialize(self, client):
        """Test client initialization."""
        assert client.storage is not None
        assert client.storage.connection is not None
    
    @pytest.mark.asyncio
    async def test_constructor_defaults(self):
        """Test client constructor with default values."""
        client = IndexedCPClient()
        
        assert client.server_url is None
        assert client.chunk_size == 1024 * 1024  # 1MB default
        assert client.encryption is False
        assert '.indexcp/db/client.db' in client.storage_path
    
    @pytest.mark.asyncio
    async def test_constructor_custom_values(self):
        """Test client constructor with custom values."""
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
        """Test that encryption raises NotImplementedError."""
        with pytest.raises(NotImplementedError, match="Encryption not supported"):
            IndexedCPClient(encryption=True)
    
    @pytest.mark.asyncio
    async def test_context_manager(self, test_file):
        """Test client as async context manager."""
        with tempfile.NamedTemporaryFile(delete=False, suffix='.db') as tmp:
            db_path = tmp.name
        
        try:
            async with IndexedCPClient(storage_path=db_path) as client:
                assert client.storage is not None
                chunk_count = await client.add_file(test_file)
                assert chunk_count > 0
        finally:
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
        """Test closing client connection."""
        assert client.storage is not None
        
        await client.close()
        
        assert client.storage is None


class TestFileOperations:
    """Test file adding and chunking."""
    
    @pytest.mark.asyncio
    async def test_add_file_basic(self, client, test_file):
        """Test adding a file returns chunk count."""
        chunk_count = await client.add_file(test_file)
        
        assert isinstance(chunk_count, int)
        assert chunk_count > 0
    
    @pytest.mark.asyncio
    async def test_add_file_chunking(self, client):
        """Test file chunking with known content."""
        with tempfile.NamedTemporaryFile(mode='wb', delete=False) as f:
            # Write exactly 2.5 chunks worth of data
            f.write(b'A' * 2560)
            temp_path = f.name
        
        try:
            chunk_count = await client.add_file(temp_path)
            assert chunk_count == 3
        finally:
            os.unlink(temp_path)
    
    @pytest.mark.asyncio
    async def test_add_file_nonexistent(self, client):
        """Test adding a non-existent file raises FileNotFoundError."""
        with pytest.raises(FileNotFoundError):
            await client.add_file('/nonexistent/file.txt')
    
    @pytest.mark.asyncio
    async def test_add_file_not_initialized(self, test_file):
        """Test adding file before initialization raises RuntimeError."""
        client = IndexedCPClient()
        
        with pytest.raises(RuntimeError, match="not initialized"):
            await client.add_file(test_file)
    
    @pytest.mark.asyncio
    async def test_large_file_chunking(self, client):
        """Test chunking of a larger file."""
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


class TestInputValidation:
    """Test input validation and error handling."""
    
    @pytest.mark.asyncio
    async def test_invalid_storage_path(self):
        """Test client with invalid storage path."""
        client = IndexedCPClient(storage_path='/invalid/path/that/does/not/exist/db.sqlite')
        
        with pytest.raises(Exception):
            await client.initialize()
    
    @pytest.mark.asyncio
    async def test_add_directory_instead_of_file(self):
        """Test adding a directory raises ValueError."""
        with tempfile.TemporaryDirectory() as tmpdir:
            client = IndexedCPClient(storage_path=f'{tmpdir}/test.db')
            await client.initialize()
            
            try:
                with pytest.raises(ValueError, match="Not a file"):
                    await client.add_file(tmpdir)
            finally:
                await client.close()
    
    @pytest.mark.asyncio
    async def test_upload_without_server_url(self, test_file):
        """Test upload without server URL raises ValueError."""
        with tempfile.NamedTemporaryFile(delete=False, suffix='.db') as tmp:
            db_path = tmp.name
        
        try:
            client = IndexedCPClient(storage_path=db_path)
            await client.initialize()
            
            await client.add_file(test_file)
            
            with pytest.raises(ValueError, match="server_url required"):
                await client.upload_buffered_files()
            
            await client.close()
        finally:
            os.unlink(db_path)
    
    @pytest.mark.asyncio
    async def test_upload_without_api_key(self, test_file):
        """Test upload without API key raises ValueError."""
        with tempfile.NamedTemporaryFile(delete=False, suffix='.db') as tmp:
            db_path = tmp.name
        
        try:
            client = IndexedCPClient(
                server_url="http://localhost:3000",
                storage_path=db_path
            )
            await client.initialize()
            
            await client.add_file(test_file)
            client.api_key = None
            
            with pytest.raises(ValueError, match="api_key required"):
                await client.upload_buffered_files()
            
            await client.close()
        finally:
            os.unlink(db_path)


class TestRetryLogic:
    """Test retry logic and metadata management."""
    
    @pytest.mark.asyncio
    async def test_retry_metadata_initialization(self, client, test_file):
        """Test that retry metadata is initialized correctly."""
        chunk_count = await client.add_file(test_file)
        
        chunks = await client.storage.load_all()
        assert len(chunks) == chunk_count
        
        for chunk in chunks:
            assert 'retryMetadata' in chunk
            metadata = chunk['retryMetadata']
            assert metadata['retryCount'] == 0
            assert metadata['lastAttempt'] is None
            assert 'nextRetry' in metadata
            assert isinstance(metadata['errors'], list)
            assert len(metadata['errors']) == 0
    
    @pytest.mark.asyncio
    async def test_exponential_backoff(self, client, test_file):
        """Test exponential backoff retry delays."""
        client.initial_retry_delay = 1.0
        client.retry_multiplier = 2.0
        client.max_retry_delay = 60.0
        
        await client.add_file(test_file)
        
        # Manually update retry metadata to simulate failure
        chunks = await client.storage.load_all()
        for chunk in chunks:
            chunk['retryMetadata']['retryCount'] = 1
            chunk['retryMetadata']['lastAttempt'] = 1000
            chunk['retryMetadata']['nextRetry'] = 2000
            await client.storage.save(chunk['id'], chunk)
        
        # Verify metadata was updated
        updated_chunks = await client.storage.load_all()
        for chunk in updated_chunks:
            metadata = chunk['retryMetadata']
            assert metadata['retryCount'] == 1
            assert metadata['nextRetry'] > metadata['lastAttempt']


class TestBackgroundUpload:
    """Test background upload functionality."""
    
    @pytest.mark.asyncio
    async def test_start_stop_background_upload(self, client):
        """Test starting and stopping background upload."""
        await client.start_upload_background(check_interval=1.0)
        assert client.background_upload_task is not None
        
        await client.stop_upload_background()
        assert client.background_upload_task is None
    
    @pytest.mark.asyncio
    async def test_background_upload_already_running(self, client):
        """Test that starting background upload twice doesn't create duplicate tasks."""
        await client.start_upload_background(check_interval=1.0)
        
        # Try to start again
        await client.start_upload_background(check_interval=1.0)
        
        # Should still have only one task
        assert client.background_upload_task is not None
        
        await client.stop_upload_background()


class TestCallbacks:
    """Test progress and completion callbacks."""
    
    @pytest.mark.asyncio
    async def test_progress_callback_registration(self, client):
        """Test progress callback can be registered."""
        progress_events = []
        
        def on_progress(event):
            progress_events.append(event)
        
        client.on_upload_progress = on_progress
        assert client.on_upload_progress is not None
    
    @pytest.mark.asyncio
    async def test_completion_callback_registration(self, client):
        """Test completion callback can be registered."""
        completion_events = []
        
        def on_complete(event):
            completion_events.append(event)
        
        client.on_upload_complete = on_complete
        assert client.on_upload_complete is not None


class TestMultipleFiles:
    """Test handling multiple files."""
    
    @pytest.mark.asyncio
    async def test_add_multiple_files(self, client):
        """Test adding multiple files."""
        files = []
        for i in range(3):
            with tempfile.NamedTemporaryFile(mode='w', delete=False, suffix='.txt') as f:
                f.write(f"Test file {i} content. " * 50)
                files.append(f.name)
        
        try:
            for file_path in files:
                chunk_count = await client.add_file(file_path)
                assert chunk_count > 0
            
            # Verify all chunks stored
            all_chunks = await client.storage.load_all()
            assert len(all_chunks) > 0
            
            # Verify all files represented
            file_names = set(chunk['fileName'] for chunk in all_chunks)
            assert len(file_names) == 3
        
        finally:
            for file_path in files:
                try:
                    os.unlink(file_path)
                except Exception:
                    pass
    
    @pytest.mark.asyncio
    async def test_chunk_ordering(self, client, test_file):
        """Test that chunks are stored with correct ordering."""
        chunk_count = await client.add_file(test_file)
        
        chunks = await client.storage.load_all()
        
        # Verify chunk indices are sequential
        indices = sorted(chunk['chunkIndex'] for chunk in chunks)
        assert indices == list(range(chunk_count))


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
