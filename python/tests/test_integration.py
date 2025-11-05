"""
Integration tests for IndexedCP client and server.

Tests real client-server interactions with an actual running server.
"""

import pytest
import asyncio
import tempfile
import os
import shutil
import time
from pathlib import Path
from threading import Thread
import uvicorn

from indexedcp.server import IndexedCPServer
from indexedcp.client import IndexedCPClient


# Global server instance for background thread
_server_instance = None
_server_thread = None


def run_server_in_thread(server, port):
    """Run FastAPI server in a background thread."""
    app = server.create_app()
    config = uvicorn.Config(
        app,
        host="127.0.0.1",
        port=port,
        log_level="error",  # Reduce noise in tests
        access_log=False
    )
    server_instance = uvicorn.Server(config)
    server_instance.run()


@pytest.fixture(scope="module")
def test_server():
    """
    Create and run a test server for the entire test module.
    Server runs in a background thread.
    """
    global _server_instance, _server_thread
    
    # Create temporary upload directory
    temp_dir = tempfile.mkdtemp(prefix="indexedcp_test_")
    test_api_key = "test-integration-key-12345"
    test_port = 9999
    
    # Create server instance
    server = IndexedCPServer(
        upload_dir=temp_dir,
        port=test_port,
        api_keys=[test_api_key],
        path_mode="ignore",
        log_level="ERROR"
    )
    
    # Start server in background thread
    _server_thread = Thread(
        target=run_server_in_thread,
        args=(server, test_port),
        daemon=True
    )
    _server_thread.start()
    
    # Wait for server to start
    time.sleep(2)
    
    yield {
        'server': server,
        'url': f"http://127.0.0.1:{test_port}/upload",
        'api_key': test_api_key,
        'upload_dir': temp_dir
    }
    
    # Cleanup
    try:
        shutil.rmtree(temp_dir)
    except Exception:
        pass


@pytest.fixture
def clean_upload_dir(test_server):
    """Clean upload directory before each test."""
    # Clear upload directory before test
    upload_dir = Path(test_server['upload_dir'])
    if upload_dir.exists():
        for file in upload_dir.iterdir():
            if file.is_file():
                try:
                    file.unlink()
                except Exception:
                    pass
    
    # Clear server sessions
    test_server['server'].clear_sessions()
    
    yield
    
    # Optionally clean after test too (for extra safety)
    for file in upload_dir.iterdir():
        if file.is_file():
            try:
                file.unlink()
            except Exception:
                pass


@pytest.fixture
async def test_client(test_server, clean_upload_dir):
    """Create a test client instance."""
    with tempfile.NamedTemporaryFile(delete=False, suffix='.db') as tmp:
        db_path = tmp.name
    
    client = IndexedCPClient(
        server_url=test_server['url'],
        api_key=test_server['api_key'],
        storage_path=db_path,
        chunk_size=1024,  # Small chunks for testing
        log_level="ERROR"
    )
    
    await client.initialize()
    
    yield client
    
    await client.close()
    
    # Cleanup database files
    try:
        os.unlink(db_path)
        for ext in ['-wal', '-shm']:
            wal_file = db_path + ext
            if os.path.exists(wal_file):
                os.unlink(wal_file)
    except Exception:
        pass


@pytest.fixture
def test_file_small():
    """Create a small test file (< 1KB)."""
    with tempfile.NamedTemporaryFile(mode='w', delete=False, suffix='.txt') as f:
        f.write("Hello, IndexedCP! This is a small test file.\n")
        temp_path = f.name
    
    yield temp_path
    
    try:
        os.unlink(temp_path)
    except Exception:
        pass


@pytest.fixture
def test_file_multipart():
    """Create a file that requires multiple chunks (> 3KB for 1KB chunks)."""
    with tempfile.NamedTemporaryFile(mode='w', delete=False, suffix='.txt') as f:
        # Write ~4KB of data (will create 4 chunks with 1KB chunk size)
        for i in range(100):
            f.write(f"Line {i}: This is test data for multipart upload testing.\n")
        temp_path = f.name
    
    yield temp_path
    
    try:
        os.unlink(temp_path)
    except Exception:
        pass


@pytest.fixture
def test_file_large():
    """Create a large file for stress testing (> 10KB)."""
    with tempfile.NamedTemporaryFile(mode='wb', delete=False, suffix='.bin') as f:
        # Write 15KB of data
        f.write(b'X' * (15 * 1024))
        temp_path = f.name
    
    yield temp_path
    
    try:
        os.unlink(temp_path)
    except Exception:
        pass


class TestBasicUpload:
    """Test basic file upload functionality."""
    
    @pytest.mark.asyncio
    async def test_simple_upload_small_file(self, test_server, test_client, test_file_small):
        """Test uploading a small file (single chunk)."""
        # Add file to client buffer
        chunk_count = await test_client.add_file(test_file_small)
        assert chunk_count == 1
        
        # Upload to server
        results = await test_client.upload_buffered_files()
        assert len(results) == 1
        
        # Verify file exists on server
        server_filename = list(results.values())[0]
        server_file_path = Path(test_server['upload_dir']) / server_filename
        
        assert server_file_path.exists()
        
        # Verify content matches
        with open(test_file_small, 'rb') as original:
            original_content = original.read()
        
        with open(server_file_path, 'rb') as uploaded:
            uploaded_content = uploaded.read()
        
        assert original_content == uploaded_content
    
    @pytest.mark.asyncio
    async def test_multipart_upload(self, test_server, test_client, test_file_multipart):
        """Test uploading a file with multiple chunks."""
        # Add file to client buffer
        chunk_count = await test_client.add_file(test_file_multipart)
        assert chunk_count > 1, "File should be split into multiple chunks"
        
        # Upload to server
        results = await test_client.upload_buffered_files()
        assert len(results) == 1
        
        # Verify file exists on server
        server_filename = list(results.values())[0]
        server_file_path = Path(test_server['upload_dir']) / server_filename
        
        assert server_file_path.exists()
        
        # Verify content matches (chunks reassembled correctly)
        with open(test_file_multipart, 'rb') as original:
            original_content = original.read()
        
        with open(server_file_path, 'rb') as uploaded:
            uploaded_content = uploaded.read()
        
        assert original_content == uploaded_content
        assert len(uploaded_content) > 3 * 1024, "File should be larger than 3KB"
    
    @pytest.mark.asyncio
    async def test_large_file_upload(self, test_server, test_client, test_file_large):
        """Test uploading a large file (15KB, ~15 chunks)."""
        # Add file to client buffer
        chunk_count = await test_client.add_file(test_file_large)
        assert chunk_count >= 15, "15KB file should create ~15 chunks with 1KB size"
        
        # Upload to server
        results = await test_client.upload_buffered_files()
        assert len(results) == 1
        
        # Verify file exists on server
        server_filename = list(results.values())[0]
        server_file_path = Path(test_server['upload_dir']) / server_filename
        
        assert server_file_path.exists()
        
        # Verify file size matches
        original_size = os.path.getsize(test_file_large)
        uploaded_size = os.path.getsize(server_file_path)
        
        assert original_size == uploaded_size
        assert uploaded_size == 15 * 1024


class TestMultipleFiles:
    """Test uploading multiple files in batch."""
    
    @pytest.mark.asyncio
    async def test_upload_multiple_files(self, test_server, test_client):
        """Test uploading multiple files in one batch."""
        # Create multiple test files
        test_files = []
        for i in range(3):
            with tempfile.NamedTemporaryFile(mode='w', delete=False, suffix=f'_{i}.txt') as f:
                f.write(f"Test file {i} content. " * 50)
                test_files.append(f.name)
        
        try:
            # Add all files to buffer
            chunk_counts = []
            for file_path in test_files:
                count = await test_client.add_file(file_path)
                chunk_counts.append(count)
            
            assert len(chunk_counts) == 3
            assert all(count > 0 for count in chunk_counts)
            
            # Upload all files
            results = await test_client.upload_buffered_files()
            assert len(results) == 3
            
            # Verify all files exist on server
            for client_path, server_filename in results.items():
                server_file_path = Path(test_server['upload_dir']) / server_filename
                assert server_file_path.exists()
                
                # Verify content
                with open(client_path, 'rb') as original:
                    original_content = original.read()
                
                with open(server_file_path, 'rb') as uploaded:
                    uploaded_content = uploaded.read()
                
                assert original_content == uploaded_content
        
        finally:
            for file_path in test_files:
                try:
                    os.unlink(file_path)
                except Exception:
                    pass
    
    @pytest.mark.asyncio
    async def test_multiple_files_different_sizes(self, test_server, test_client):
        """Test uploading files of varying sizes."""
        # Create files of different sizes
        test_files = []
        
        # Small file (1 chunk)
        with tempfile.NamedTemporaryFile(mode='w', delete=False, suffix='_small.txt') as f:
            f.write("Small")
            test_files.append(f.name)
        
        # Medium file (3-4 chunks)
        with tempfile.NamedTemporaryFile(mode='w', delete=False, suffix='_medium.txt') as f:
            f.write("M" * 3500)
            test_files.append(f.name)
        
        # Large file (10+ chunks)
        with tempfile.NamedTemporaryFile(mode='wb', delete=False, suffix='_large.bin') as f:
            f.write(b'L' * 12000)
            test_files.append(f.name)
        
        try:
            # Add and upload all files
            for file_path in test_files:
                await test_client.add_file(file_path)
            
            results = await test_client.upload_buffered_files()
            assert len(results) == 3
            
            # Verify all files uploaded correctly
            for client_path, server_filename in results.items():
                server_file_path = Path(test_server['upload_dir']) / server_filename
                assert server_file_path.exists()
                
                original_size = os.path.getsize(client_path)
                uploaded_size = os.path.getsize(server_file_path)
                assert original_size == uploaded_size
        
        finally:
            for file_path in test_files:
                try:
                    os.unlink(file_path)
                except Exception:
                    pass


class TestBackgroundUpload:
    """Test background upload functionality."""
    
    @pytest.mark.asyncio
    async def test_background_upload_single_file(self, test_server, test_client, test_file_small):
        """Test background upload of a single file."""
        # Add file to buffer
        chunk_count = await test_client.add_file(test_file_small)
        assert chunk_count > 0
        
        # Start background upload
        await test_client.start_upload_background(check_interval=0.5)
        
        # Wait for upload to complete
        await asyncio.sleep(2)
        
        # Stop background upload
        await test_client.stop_upload_background()
        
        # Verify file was uploaded
        all_chunks = await test_client.storage.load_all()
        assert len(all_chunks) == 0, "All chunks should be deleted after successful upload"
        
        # Verify file exists on server
        uploaded_files = list(Path(test_server['upload_dir']).glob('*'))
        assert len(uploaded_files) > 0
    
    @pytest.mark.asyncio
    async def test_background_upload_multiple_files(self, test_server, test_client):
        """Test background upload with multiple files."""
        # Create multiple files
        test_files = []
        for i in range(3):
            with tempfile.NamedTemporaryFile(mode='w', delete=False, suffix=f'_bg_{i}.txt') as f:
                f.write(f"Background upload test {i}. " * 30)
                test_files.append(f.name)
        
        try:
            # Add files to buffer
            for file_path in test_files:
                await test_client.add_file(file_path)
            
            # Verify chunks are buffered
            all_chunks = await test_client.storage.load_all()
            initial_chunk_count = len(all_chunks)
            assert initial_chunk_count > 0
            
            # Start background upload
            await test_client.start_upload_background(check_interval=0.5)
            
            # Wait for uploads to complete
            await asyncio.sleep(3)
            
            # Stop background upload
            await test_client.stop_upload_background()
            
            # Verify all chunks were uploaded and deleted
            remaining_chunks = await test_client.storage.load_all()
            assert len(remaining_chunks) == 0
            
            # Verify files exist on server
            uploaded_files = list(Path(test_server['upload_dir']).glob('*'))
            assert len(uploaded_files) >= 3
        
        finally:
            for file_path in test_files:
                try:
                    os.unlink(file_path)
                except Exception:
                    pass


class TestChunkReassembly:
    """Test that chunks are correctly reassembled on server."""
    
    @pytest.mark.asyncio
    async def test_chunk_order_preservation(self, test_server, test_client):
        """Test that chunks are reassembled in correct order."""
        # Create file with identifiable chunks (make sure it's large enough for 5+ chunks)
        # With 1KB chunk size, need at least 5KB of data
        with tempfile.NamedTemporaryFile(mode='w', delete=False, suffix='_ordered.txt') as f:
            for i in range(5):
                # Each chunk will have identifiable content (>1KB per chunk)
                f.write(f"CHUNK_{i}_" + "X" * 1000 + "\n")
            temp_path = f.name
        
        try:
            # Add and upload file
            chunk_count = await test_client.add_file(temp_path)
            assert chunk_count >= 5
            
            results = await test_client.upload_buffered_files()
            
            # Read uploaded file
            server_filename = list(results.values())[0]
            server_file_path = Path(test_server['upload_dir']) / server_filename
            
            with open(server_file_path, 'r') as f:
                content = f.read()
            
            # Verify chunks are in order
            assert "CHUNK_0_" in content
            assert "CHUNK_1_" in content
            assert "CHUNK_2_" in content
            assert "CHUNK_3_" in content
            assert "CHUNK_4_" in content
            
            # Verify order is preserved
            pos_0 = content.index("CHUNK_0_")
            pos_1 = content.index("CHUNK_1_")
            pos_2 = content.index("CHUNK_2_")
            pos_3 = content.index("CHUNK_3_")
            pos_4 = content.index("CHUNK_4_")
            
            assert pos_0 < pos_1 < pos_2 < pos_3 < pos_4
        
        finally:
            try:
                os.unlink(temp_path)
            except Exception:
                pass
    
    @pytest.mark.asyncio
    async def test_binary_data_integrity(self, test_server, test_client):
        """Test that binary data is preserved during chunking and reassembly."""
        # Create binary file with specific pattern
        with tempfile.NamedTemporaryFile(mode='wb', delete=False, suffix='.bin') as f:
            # Create pattern: 0-255 repeated
            pattern = bytes(range(256)) * 50  # 12.8KB
            f.write(pattern)
            temp_path = f.name
        
        try:
            # Add and upload file
            chunk_count = await test_client.add_file(temp_path)
            assert chunk_count > 1
            
            results = await test_client.upload_buffered_files()
            
            # Verify binary content is identical
            server_filename = list(results.values())[0]
            server_file_path = Path(test_server['upload_dir']) / server_filename
            
            with open(temp_path, 'rb') as original:
                original_data = original.read()
            
            with open(server_file_path, 'rb') as uploaded:
                uploaded_data = uploaded.read()
            
            assert original_data == uploaded_data
            assert len(uploaded_data) == 256 * 50
        
        finally:
            try:
                os.unlink(temp_path)
            except Exception:
                pass


class TestServerPathModes:
    """Test different server path handling modes."""
    
    @pytest.mark.asyncio
    async def test_ignore_mode_unique_filenames(self, test_server, test_client):
        """Test that ignore mode generates unique filenames."""
        # Upload same file twice
        with tempfile.NamedTemporaryFile(mode='w', delete=False, suffix='_duplicate.txt') as f:
            f.write("Duplicate test content")
            temp_path = f.name
        
        try:
            # First upload
            await test_client.add_file(temp_path)
            results1 = await test_client.upload_buffered_files()
            server_file1 = list(results1.values())[0]
            
            # Clear server sessions to allow new upload
            test_server['server'].clear_sessions()
            
            # Second upload
            await test_client.add_file(temp_path)
            results2 = await test_client.upload_buffered_files()
            server_file2 = list(results2.values())[0]
            
            # Filenames should be different (ignore mode generates unique names)
            assert server_file1 != server_file2
            
            # Both files should exist
            assert (Path(test_server['upload_dir']) / server_file1).exists()
            assert (Path(test_server['upload_dir']) / server_file2).exists()
        
        finally:
            try:
                os.unlink(temp_path)
            except Exception:
                pass
    
    @pytest.mark.asyncio
    async def test_session_tracking(self, test_server, test_client, test_file_multipart):
        """Test that server tracks sessions across chunks."""
        # Clear any existing sessions
        test_server['server'].clear_sessions()
        
        # Add multipart file
        chunk_count = await test_client.add_file(test_file_multipart)
        assert chunk_count > 1
        
        # Upload file
        results = await test_client.upload_buffered_files()
        
        # Verify single file was created (not one per chunk)
        server_filename = list(results.values())[0]
        uploaded_files = list(Path(test_server['upload_dir']).glob(f"*{Path(server_filename).suffix}"))
        
        # Should have exactly one file for this upload
        matching_files = [f for f in uploaded_files if server_filename in str(f)]
        assert len(matching_files) == 1


class TestErrorScenarios:
    """Test error handling in integration scenarios."""
    
    @pytest.mark.asyncio
    async def test_invalid_api_key(self, test_server):
        """Test upload with invalid API key fails gracefully."""
        with tempfile.NamedTemporaryFile(delete=False, suffix='.db') as tmp:
            db_path = tmp.name
        
        try:
            # Create client with wrong API key
            client = IndexedCPClient(
                server_url=test_server['url'],
                api_key="wrong-api-key",
                storage_path=db_path,
                chunk_size=1024,
                max_retries=1,  # Limit retries for faster test
                log_level="ERROR"
            )
            
            await client.initialize()
            
            # Create test file
            with tempfile.NamedTemporaryFile(mode='w', delete=False, suffix='.txt') as f:
                f.write("Test content")
                test_file = f.name
            
            try:
                # Add file
                await client.add_file(test_file)
                
                # Attempt upload should fail (either with auth error or general upload error)
                with pytest.raises(RuntimeError):
                    await client.upload_buffered_files()
            
            finally:
                try:
                    os.unlink(test_file)
                except Exception:
                    pass
            
            await client.close()
        
        finally:
            try:
                os.unlink(db_path)
            except Exception:
                pass
    
    @pytest.mark.asyncio
    async def test_upload_preserves_failed_chunks(self, test_server):
        """Test that failed chunks remain in storage for retry."""
        with tempfile.NamedTemporaryFile(delete=False, suffix='.db') as tmp:
            db_path = tmp.name
        
        try:
            # Create client with wrong API key
            client = IndexedCPClient(
                server_url=test_server['url'],
                api_key="invalid-key",
                storage_path=db_path,
                chunk_size=1024,
                max_retries=1,
                log_level="ERROR"
            )
            
            await client.initialize()
            
            # Create test file
            with tempfile.NamedTemporaryFile(mode='w', delete=False, suffix='.txt') as f:
                f.write("Test content for failed upload")
                test_file = f.name
            
            try:
                # Add file
                chunk_count = await client.add_file(test_file)
                
                # Verify chunks in storage
                chunks_before = await client.storage.load_all()
                assert len(chunks_before) == chunk_count
                
                # Attempt upload (will fail)
                try:
                    await client.upload_buffered_files()
                except RuntimeError:
                    pass  # Expected to fail
                
                # Chunks should still be in storage
                chunks_after = await client.storage.load_all()
                assert len(chunks_after) == chunk_count
            
            finally:
                try:
                    os.unlink(test_file)
                except Exception:
                    pass
            
            await client.close()
        
        finally:
            try:
                os.unlink(db_path)
            except Exception:
                pass


class TestEndToEndWorkflow:
    """Test complete end-to-end workflows."""
    
    @pytest.mark.asyncio
    async def test_complete_workflow(self, test_server, test_client):
        """Test complete workflow: add -> upload -> verify."""
        # Create a test file
        with tempfile.NamedTemporaryFile(mode='w', delete=False, suffix='_workflow.txt') as f:
            f.write("Complete workflow test. " * 100)
            test_file = f.name
        
        try:
            # Step 1: Add file to buffer
            chunk_count = await test_client.add_file(test_file)
            assert chunk_count > 0
            
            # Step 2: Verify chunks are in storage
            chunks = await test_client.storage.load_all()
            assert len(chunks) == chunk_count
            
            # Step 3: Upload to server
            results = await test_client.upload_buffered_files()
            assert len(results) == 1
            
            # Step 4: Verify chunks are deleted after upload
            remaining_chunks = await test_client.storage.load_all()
            assert len(remaining_chunks) == 0
            
            # Step 5: Verify file on server
            server_filename = list(results.values())[0]
            server_file_path = Path(test_server['upload_dir']) / server_filename
            assert server_file_path.exists()
            
            # Step 6: Verify content integrity
            with open(test_file, 'rb') as original:
                original_content = original.read()
            
            with open(server_file_path, 'rb') as uploaded:
                uploaded_content = uploaded.read()
            
            assert original_content == uploaded_content
        
        finally:
            try:
                os.unlink(test_file)
            except Exception:
                pass
    
    @pytest.mark.asyncio
    async def test_batch_workflow(self, test_server, test_client):
        """Test batch upload workflow with multiple files."""
        test_files = []
        
        # Create multiple files
        for i in range(5):
            with tempfile.NamedTemporaryFile(mode='w', delete=False, suffix=f'_batch_{i}.txt') as f:
                f.write(f"Batch file {i}. " * 50)
                test_files.append(f.name)
        
        try:
            # Add all files
            total_chunks = 0
            for file_path in test_files:
                chunks = await test_client.add_file(file_path)
                total_chunks += chunks
            
            # Verify all chunks buffered
            buffered_chunks = await test_client.storage.load_all()
            assert len(buffered_chunks) == total_chunks
            
            # Upload all at once
            results = await test_client.upload_buffered_files()
            assert len(results) == 5
            
            # Verify all uploaded
            remaining_chunks = await test_client.storage.load_all()
            assert len(remaining_chunks) == 0
            
            # Verify all files on server
            for client_path, server_filename in results.items():
                server_path = Path(test_server['upload_dir']) / server_filename
                assert server_path.exists()
        
        finally:
            for file_path in test_files:
                try:
                    os.unlink(file_path)
                except Exception:
                    pass


if __name__ == "__main__":
    pytest.main([__file__, "-v", "-s"])
