"""
Integration tests for IndexedCPClient upload functionality with retry logic
"""

import pytest
import asyncio
import tempfile
import os
import json
from pathlib import Path
from unittest.mock import Mock, patch, MagicMock
from http.server import HTTPServer, BaseHTTPRequestHandler
import threading
import urllib.error

from indexedcp.client import IndexedCPClient


class MockServerHandler(BaseHTTPRequestHandler):
    """Mock HTTP server handler for testing"""
    
    # Class-level storage for test configuration
    fail_count = 0
    total_requests = 0
    api_key = "test-api-key"
    
    def log_message(self, format, *args):
        """Suppress server logs during tests"""
        pass
    
    def do_POST(self):
        """Handle POST requests"""
        MockServerHandler.total_requests += 1
        
        # Check authentication
        auth_header = self.headers.get('Authorization')
        if not auth_header or auth_header != f'Bearer {MockServerHandler.api_key}':
            self.send_response(401)
            self.send_header('Content-Type', 'application/json')
            self.end_headers()
            self.wfile.write(b'{"error": "Invalid API key"}')
            return
        
        # Simulate failures for retry testing
        if MockServerHandler.fail_count > 0:
            MockServerHandler.fail_count -= 1
            self.send_response(500)
            self.send_header('Content-Type', 'application/json')
            self.end_headers()
            self.wfile.write(b'{"error": "Server error"}')
            return
        
        # Read request body
        content_length = int(self.headers.get('Content-Length', 0))
        body = self.rfile.read(content_length)
        
        # Get headers
        chunk_index = self.headers.get('X-Chunk-Index', '0')
        file_name = self.headers.get('X-File-Name', 'unknown')
        
        # Send success response
        self.send_response(200)
        self.send_header('Content-Type', 'application/json')
        self.end_headers()
        
        response = {
            'message': 'Chunk received',
            'actualFilename': Path(file_name).name,
            'chunkIndex': int(chunk_index),
            'clientFilename': file_name
        }
        
        self.wfile.write(json.dumps(response).encode('utf-8'))


@pytest.fixture
def mock_server():
    """Create a mock HTTP server for testing"""
    MockServerHandler.fail_count = 0
    MockServerHandler.total_requests = 0
    
    server = HTTPServer(('localhost', 0), MockServerHandler)
    port = server.server_address[1]
    
    # Run server in background thread
    thread = threading.Thread(target=server.serve_forever)
    thread.daemon = True
    thread.start()
    
    yield f"http://localhost:{port}"
    
    server.shutdown()


@pytest.fixture
async def client(mock_server):
    """Create a temporary client instance"""
    with tempfile.NamedTemporaryFile(delete=False, suffix='.db') as tmp:
        db_path = tmp.name
    
    client = IndexedCPClient(
        server_url=mock_server,
        api_key="test-api-key",
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
    """Create a temporary test file"""
    with tempfile.NamedTemporaryFile(mode='w', delete=False, suffix='.txt') as f:
        f.write("Test content for upload. " * 100)
        temp_path = f.name
    
    yield temp_path
    
    try:
        os.unlink(temp_path)
    except Exception:
        pass


class TestClientUpload:
    """Test suite for client upload functionality"""
    
    @pytest.mark.asyncio
    async def test_upload_buffered_files_basic(self, client, test_file, mock_server):
        """Test basic file upload"""
        # Add file to buffer
        chunk_count = await client.add_file(test_file)
        assert chunk_count > 0
        
        # Upload buffered files
        result = await client.upload_buffered_files()
        
        assert isinstance(result, dict)
        assert test_file in result
        assert result[test_file] == Path(test_file).name
        
        # Verify chunks were deleted from storage
        remaining_chunks = await client.storage.load_all()
        assert len(remaining_chunks) == 0
    
    @pytest.mark.asyncio
    async def test_upload_without_server_url(self, test_file):
        """Test upload without server URL raises error"""
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
            try:
                os.unlink(db_path)
            except Exception:
                pass
    
    @pytest.mark.asyncio
    async def test_upload_without_api_key(self, test_file, mock_server):
        """Test upload without API key raises error"""
        with tempfile.NamedTemporaryFile(delete=False, suffix='.db') as tmp:
            db_path = tmp.name
        
        try:
            client = IndexedCPClient(
                server_url=mock_server,
                storage_path=db_path
            )
            await client.initialize()
            
            await client.add_file(test_file)
            
            with pytest.raises(ValueError, match="api_key required"):
                await client.upload_buffered_files()
            
            await client.close()
        finally:
            try:
                os.unlink(db_path)
            except Exception:
                pass
    
    @pytest.mark.asyncio
    async def test_upload_empty_buffer(self, client, mock_server):
        """Test upload with empty buffer returns empty dict"""
        result = await client.upload_buffered_files()
        
        assert isinstance(result, dict)
        assert len(result) == 0
    
    @pytest.mark.asyncio
    async def test_retry_metadata_initialization(self, client, test_file):
        """Test that retry metadata is initialized correctly"""
        chunk_count = await client.add_file(test_file)
        
        # Get chunks from storage
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
    async def test_upload_with_retry_on_failure(self, client, test_file, mock_server):
        """Test upload retry logic with simulated failures"""
        # Configure mock server to fail first attempt
        MockServerHandler.fail_count = 1
        
        # Add file
        await client.add_file(test_file)
        
        # First upload attempt should fail for one chunk
        with pytest.raises(RuntimeError, match="chunk\\(s\\) failed"):
            await client.upload_buffered_files()
        
        # Verify chunks still in storage with updated retry metadata
        chunks = await client.storage.load_all()
        assert len(chunks) > 0
        
        for chunk in chunks:
            metadata = chunk['retryMetadata']
            assert metadata['retryCount'] == 1
            assert metadata['lastAttempt'] is not None
            assert len(metadata['errors']) == 1
        
        # Reset fail count and retry
        MockServerHandler.fail_count = 0
        
        # Manually reset nextRetry to allow immediate retry
        for chunk in chunks:
            chunk['retryMetadata']['nextRetry'] = 0
            await client.storage.save(chunk['id'], chunk)
        
        # Second attempt should succeed
        result = await client.upload_buffered_files()
        assert len(result) == 1
        
        # Verify chunks were deleted
        remaining_chunks = await client.storage.load_all()
        assert len(remaining_chunks) == 0
    
    @pytest.mark.asyncio
    async def test_progress_callback(self, client, test_file, mock_server):
        """Test progress callback is called during upload"""
        progress_events = []
        
        def on_progress(event):
            progress_events.append(event)
        
        client.on_upload_progress = on_progress
        
        # Add and upload file
        chunk_count = await client.add_file(test_file)
        await client.upload_buffered_files()
        
        # Verify progress events
        assert len(progress_events) == chunk_count
        
        for event in progress_events:
            assert 'fileName' in event
            assert 'chunkIndex' in event
            assert event['status'] == 'success'
            assert 'retryCount' in event
    
    @pytest.mark.asyncio
    async def test_completion_callback(self, client, test_file, mock_server):
        """Test completion callback is not called in direct upload"""
        # Note: Completion callback is only called in background upload mode
        completion_events = []
        
        def on_complete(event):
            completion_events.append(event)
        
        client.on_upload_complete = on_complete
        
        # Add and upload file
        await client.add_file(test_file)
        await client.upload_buffered_files()
        
        # Direct upload doesn't call completion callback
        assert len(completion_events) == 0
    
    @pytest.mark.asyncio
    async def test_max_retries_limit(self, client, test_file):
        """Test that max retries limit is respected"""
        # Set max retries to 2
        client.max_retries = 2
        
        # Configure server to always fail
        MockServerHandler.fail_count = 999
        
        # Add file
        await client.add_file(test_file)
        
        # First upload attempt
        with pytest.raises(RuntimeError, match="chunk\\(s\\) failed"):
            await client.upload_buffered_files()
        
        chunks = await client.storage.load_all()
        for chunk in chunks:
            chunk['retryMetadata']['nextRetry'] = 0
            await client.storage.save(chunk['id'], chunk)
        
        # Second upload attempt
        with pytest.raises(RuntimeError, match="chunk\\(s\\) failed"):
            await client.upload_buffered_files()
        
        # Third attempt should be skipped due to max retries
        chunks = await client.storage.load_all()
        for chunk in chunks:
            assert chunk['retryMetadata']['retryCount'] == 2
    
    @pytest.mark.asyncio
    async def test_background_upload(self, client, test_file, mock_server):
        """Test background upload process"""
        # Add file
        await client.add_file(test_file)
        
        # Start background upload with short interval
        await client.start_upload_background(check_interval=0.1)
        
        # Wait for background upload to process
        await asyncio.sleep(0.5)
        
        # Stop background upload
        await client.stop_upload_background()
        
        # Verify chunks were uploaded
        chunks = await client.storage.load_all()
        assert len(chunks) == 0
    
    @pytest.mark.asyncio
    async def test_background_upload_already_running(self, client, mock_server):
        """Test that starting background upload twice doesn't create duplicate tasks"""
        await client.start_upload_background(check_interval=1.0)
        
        # Try to start again
        await client.start_upload_background(check_interval=1.0)
        
        # Should still have only one task
        assert client.background_upload_task is not None
        
        await client.stop_upload_background()
    
    @pytest.mark.asyncio
    async def test_exponential_backoff(self, client, test_file):
        """Test exponential backoff retry delays"""
        client.initial_retry_delay = 1.0
        client.retry_multiplier = 2.0
        client.max_retry_delay = 60.0
        
        # Configure server to fail
        MockServerHandler.fail_count = 999
        
        await client.add_file(test_file)
        
        # Attempt upload (will fail)
        try:
            await client.upload_buffered_files()
        except RuntimeError:
            pass
        
        chunks = await client.storage.load_all()
        assert len(chunks) > 0
        
        # Verify exponential backoff calculation
        for chunk in chunks:
            metadata = chunk['retryMetadata']
            
            # After first failure, next retry should be in ~1000ms
            # (initial_retry_delay * multiplier^0)
            assert metadata['retryCount'] == 1
            
            # Check that nextRetry was set
            assert metadata['nextRetry'] > metadata['lastAttempt']
    
    @pytest.mark.asyncio
    async def test_multiple_files_upload(self, client, mock_server):
        """Test uploading multiple files"""
        # Create multiple test files
        files = []
        for i in range(3):
            with tempfile.NamedTemporaryFile(mode='w', delete=False, suffix='.txt') as f:
                f.write(f"Test file {i} content. " * 50)
                files.append(f.name)
        
        try:
            # Add all files
            for file_path in files:
                await client.add_file(file_path)
            
            # Upload all files
            result = await client.upload_buffered_files()
            
            # Verify all files were uploaded
            assert len(result) == 3
            
            for file_path in files:
                assert file_path in result
            
            # Verify no chunks remain
            chunks = await client.storage.load_all()
            assert len(chunks) == 0
        
        finally:
            for file_path in files:
                try:
                    os.unlink(file_path)
                except Exception:
                    pass
    
    @pytest.mark.asyncio
    async def test_chunk_ordering(self, client, test_file, mock_server):
        """Test that chunks are uploaded in correct order"""
        # Track upload order
        upload_order = []
        
        original_upload_chunk = client._upload_chunk
        
        async def track_upload_chunk(server_url, chunk, index, file_name):
            upload_order.append(index)
            return await original_upload_chunk(server_url, chunk, index, file_name)
        
        client._upload_chunk = track_upload_chunk
        
        # Add and upload file
        await client.add_file(test_file)
        await client.upload_buffered_files()
        
        # Verify chunks were uploaded in order
        assert upload_order == sorted(upload_order)
    
    @pytest.mark.asyncio
    async def test_session_tracking(self, client, test_file, mock_server):
        """Test that file upload sessions are tracked correctly"""
        # Add file
        chunk_count = await client.add_file(test_file)
        
        # Get all chunks
        chunks = await client.storage.load_all()
        
        # Verify all chunks belong to same file
        file_names = set(chunk['fileName'] for chunk in chunks)
        assert len(file_names) == 1
        assert test_file in file_names
        
        # Verify chunk indices are sequential
        indices = sorted(chunk['chunkIndex'] for chunk in chunks)
        assert indices == list(range(chunk_count))
    
    @pytest.mark.asyncio
    async def test_error_history_limit(self, client, test_file):
        """Test that error history is limited to 5 entries"""
        client.max_retries = 10
        
        # Configure server to always fail
        MockServerHandler.fail_count = 999
        
        await client.add_file(test_file)
        
        # Attempt multiple uploads to generate errors
        for i in range(7):
            try:
                await client.upload_buffered_files()
            except RuntimeError:
                pass
            
            # Reset nextRetry to allow immediate retry
            chunks = await client.storage.load_all()
            for chunk in chunks:
                chunk['retryMetadata']['nextRetry'] = 0
                await client.storage.save(chunk['id'], chunk)
        
        # Verify error history is limited to 5
        chunks = await client.storage.load_all()
        for chunk in chunks:
            errors = chunk['retryMetadata']['errors']
            assert len(errors) <= 5
