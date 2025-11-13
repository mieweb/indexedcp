import pytest
import tempfile
import shutil
from pathlib import Path
from fastapi.testclient import TestClient

from indexedcp.server import IndexedCPServer


@pytest.fixture
def temp_upload_dir():
    """Create a temporary upload directory."""
    temp_dir = tempfile.mkdtemp()
    yield temp_dir
    shutil.rmtree(temp_dir)


@pytest.fixture
def test_api_key():
    """Test API key."""
    return "test-api-key-12345"


@pytest.fixture
def server_sanitize(temp_upload_dir, test_api_key):
    """Create server with sanitize mode."""
    return IndexedCPServer(
        upload_dir=temp_upload_dir,
        api_keys=[test_api_key],
        path_mode="sanitize",
        log_level="INFO"
    )


@pytest.fixture
def server_ignore(temp_upload_dir, test_api_key):
    """Create server with ignore mode."""
    return IndexedCPServer(
        upload_dir=temp_upload_dir,
        api_keys=[test_api_key],
        path_mode="ignore",
        log_level="INFO"
    )


@pytest.fixture
def server_allow_paths(temp_upload_dir, test_api_key):
    """Create server with allow-paths mode."""
    return IndexedCPServer(
        upload_dir=temp_upload_dir,
        api_keys=[test_api_key],
        path_mode="allow-paths",
        log_level="INFO"
    )


class TestServerInitialization:
    """Test server initialization and configuration."""
    
    def test_init_with_defaults(self, temp_upload_dir):
        """Test server initialization with default settings."""
        server = IndexedCPServer(upload_dir=temp_upload_dir)
        
        assert server.upload_dir == Path(temp_upload_dir)
        assert server.port == 3000
        assert len(server.api_keys) == 1  # Auto-generated
        assert server.path_mode == "ignore"
        assert server.encryption is False
    
    def test_init_with_custom_settings(self, temp_upload_dir, test_api_key):
        """Test server initialization with custom settings."""
        server = IndexedCPServer(
            upload_dir=temp_upload_dir,
            port=8080,
            api_keys=[test_api_key],
            path_mode="sanitize"
        )
        
        assert server.port == 8080
        assert test_api_key in server.api_keys
        assert server.path_mode == "sanitize"
    
    def test_init_creates_upload_directory(self, temp_upload_dir):
        """Test that server creates upload directory if it doesn't exist."""
        upload_path = Path(temp_upload_dir) / "new_uploads"
        server = IndexedCPServer(upload_dir=str(upload_path))
        
        assert upload_path.exists()
        assert upload_path.is_dir()
    
    def test_init_invalid_path_mode(self, temp_upload_dir):
        """Test initialization with invalid path mode."""
        with pytest.raises(ValueError, match="Invalid path_mode"):
            IndexedCPServer(
                upload_dir=temp_upload_dir,
                path_mode="invalid-mode"
            )
    
    def test_encryption_not_supported(self, temp_upload_dir):
        """Test that encryption flag raises NotImplementedError."""
        with pytest.raises(NotImplementedError, match="Encryption not supported"):
            IndexedCPServer(
                upload_dir=temp_upload_dir,
                encryption=True
            )
    
    def test_get_server_info(self, server_sanitize):
        """Test get_server_info method."""
        info = server_sanitize.get_server_info()
        
        assert "port" in info
        assert "upload_dir" in info
        assert "path_mode" in info
        assert "api_keys_count" in info
        assert "encryption" in info
        assert "active_sessions" in info
        assert info["path_mode"] == "sanitize"
        assert info["encryption"] is False


class TestAPIAuthentication:
    """Test API key authentication."""
    
    def test_valid_api_key(self, server_sanitize, test_api_key):
        """Test upload with valid API key."""
        app = server_sanitize.create_app()
        client = TestClient(app)
        
        response = client.post(
            "/upload",
            headers={
                "Authorization": f"Bearer {test_api_key}",
                "X-Chunk-Index": "0",
                "X-File-Name": "test.txt"
            },
            content=b"test data"
        )
        
        assert response.status_code == 200
        assert response.json()["message"] == "Chunk received"
    
    def test_missing_api_key(self, server_sanitize):
        """Test upload without API key."""
        app = server_sanitize.create_app()
        client = TestClient(app)
        
        response = client.post(
            "/upload",
            headers={
                "X-Chunk-Index": "0",
                "X-File-Name": "test.txt"
            },
            content=b"test data"
        )
        
        assert response.status_code == 401
        assert "Invalid or missing API key" in response.json()["detail"]
    
    def test_invalid_api_key(self, server_sanitize):
        """Test upload with invalid API key."""
        app = server_sanitize.create_app()
        client = TestClient(app)
        
        response = client.post(
            "/upload",
            headers={
                "Authorization": "Bearer invalid-key",
                "X-Chunk-Index": "0",
                "X-File-Name": "test.txt"
            },
            content=b"test data"
        )
        
        assert response.status_code == 401
    
    def test_health_check_no_auth(self, server_sanitize):
        """Test health check endpoint (no auth required)."""
        app = server_sanitize.create_app()
        client = TestClient(app)
        
        response = client.get("/health")
        
        assert response.status_code == 200
        assert response.json()["status"] == "ok"


class TestSanitizeMode:
    """Test sanitize path mode (strips paths, prevents traversal)."""
    
    def test_simple_filename(self, server_sanitize, test_api_key, temp_upload_dir):
        """Test upload with simple filename."""
        app = server_sanitize.create_app()
        client = TestClient(app)
        
        response = client.post(
            "/upload",
            headers={
                "Authorization": f"Bearer {test_api_key}",
                "X-Chunk-Index": "0",
                "X-File-Name": "test.txt"
            },
            content=b"test content"
        )
        
        assert response.status_code == 200
        data = response.json()
        assert data["actualFilename"] == "test.txt"
        
        # Verify file was created
        uploaded_file = Path(temp_upload_dir) / "test.txt"
        assert uploaded_file.exists()
        assert uploaded_file.read_bytes() == b"test content"
    
    def test_reject_path_separators(self, server_sanitize, test_api_key):
        """Test that path separators are rejected in sanitize mode."""
        app = server_sanitize.create_app()
        client = TestClient(app)
        
        response = client.post(
            "/upload",
            headers={
                "Authorization": f"Bearer {test_api_key}",
                "X-Chunk-Index": "0",
                "X-File-Name": "path/to/file.txt"
            },
            content=b"test data"
        )
        
        assert response.status_code == 400
        assert "Invalid filename" in response.json()["error"]
    
    def test_reject_traversal_attempts(self, server_sanitize, test_api_key):
        """Test that path traversal attempts are rejected."""
        app = server_sanitize.create_app()
        client = TestClient(app)
        
        response = client.post(
            "/upload",
            headers={
                "Authorization": f"Bearer {test_api_key}",
                "X-Chunk-Index": "0",
                "X-File-Name": "../../../etc/passwd"
            },
            content=b"malicious content"
        )
        
        assert response.status_code == 400
    
    def test_session_tracking(self, server_sanitize, test_api_key, temp_upload_dir):
        """Test that multi-chunk uploads use same filename."""
        app = server_sanitize.create_app()
        client = TestClient(app)
        
        # Upload first chunk
        response1 = client.post(
            "/upload",
            headers={
                "Authorization": f"Bearer {test_api_key}",
                "X-Chunk-Index": "0",
                "X-File-Name": "multipart.txt"
            },
            content=b"chunk1 "
        )
        
        assert response1.status_code == 200
        actual_filename = response1.json()["actualFilename"]
        
        # Upload second chunk
        response2 = client.post(
            "/upload",
            headers={
                "Authorization": f"Bearer {test_api_key}",
                "X-Chunk-Index": "1",
                "X-File-Name": "multipart.txt"
            },
            content=b"chunk2"
        )
        
        assert response2.status_code == 200
        assert response2.json()["actualFilename"] == actual_filename
        
        # Verify file has both chunks
        uploaded_file = Path(temp_upload_dir) / actual_filename
        assert uploaded_file.read_bytes() == b"chunk1 chunk2"


class TestIgnoreMode:
    """Test ignore path mode (unique filename generation with path preservation)."""
    
    def test_unique_filename_generation(self, server_ignore, test_api_key, temp_upload_dir):
        """Test that ignore mode generates unique filenames."""
        app = server_ignore.create_app()
        client = TestClient(app)
        
        response = client.post(
            "/upload",
            headers={
                "Authorization": f"Bearer {test_api_key}",
                "X-Chunk-Index": "0",
                "X-File-Name": "test.txt"
            },
            content=b"test content"
        )
        
        assert response.status_code == 200
        actual_filename = response.json()["actualFilename"]
        
        # Should have format: timestamp_random_test.txt
        assert "_test.txt" in actual_filename
        assert actual_filename != "test.txt"
        
        # Verify file exists
        uploaded_file = Path(temp_upload_dir) / actual_filename
        assert uploaded_file.exists()
    
    def test_path_preservation(self, server_ignore, test_api_key, temp_upload_dir):
        """Test that paths are preserved as underscores in ignore mode."""
        app = server_ignore.create_app()
        client = TestClient(app)
        
        response = client.post(
            "/upload",
            headers={
                "Authorization": f"Bearer {test_api_key}",
                "X-Chunk-Index": "0",
                "X-File-Name": "reports/2024/data.csv"
            },
            content=b"csv,data"
        )
        
        assert response.status_code == 200
        actual_filename = response.json()["actualFilename"]
        
        # Should have underscores instead of slashes
        assert "reports_2024_data.csv" in actual_filename
        assert "/" not in actual_filename
    
    def test_multiple_uploads_unique(self, server_ignore, test_api_key):
        """Test that multiple uploads generate unique filenames."""
        app = server_ignore.create_app()
        client = TestClient(app)
        
        filenames = []
        for i in range(3):
            # Clear sessions between uploads to ensure new unique filenames
            server_ignore.clear_sessions()
            
            response = client.post(
                "/upload",
                headers={
                    "Authorization": f"Bearer {test_api_key}",
                    "X-Chunk-Index": "0",
                    "X-File-Name": "test.txt"
                },
                content=f"content {i}".encode()
            )
            
            assert response.status_code == 200
            filenames.append(response.json()["actualFilename"])
        
        # All filenames should be unique
        assert len(set(filenames)) == 3


class TestAllowPathsMode:
    """Test allow-paths mode (subdirectories allowed)."""
    
    def test_subdirectory_creation(self, server_allow_paths, test_api_key, temp_upload_dir):
        """Test that subdirectories are created in allow-paths mode."""
        app = server_allow_paths.create_app()
        client = TestClient(app)
        
        response = client.post(
            "/upload",
            headers={
                "Authorization": f"Bearer {test_api_key}",
                "X-Chunk-Index": "0",
                "X-File-Name": "reports/2024/data.csv"
            },
            content=b"csv,data"
        )
        
        assert response.status_code == 200
        assert response.json()["actualFilename"] == "reports/2024/data.csv"
        
        # Verify subdirectories and file were created
        uploaded_file = Path(temp_upload_dir) / "reports" / "2024" / "data.csv"
        assert uploaded_file.exists()
        assert uploaded_file.read_bytes() == b"csv,data"
    
    def test_reject_traversal(self, server_allow_paths, test_api_key):
        """Test that traversal attempts are rejected even in allow-paths mode."""
        app = server_allow_paths.create_app()
        client = TestClient(app)
        
        response = client.post(
            "/upload",
            headers={
                "Authorization": f"Bearer {test_api_key}",
                "X-Chunk-Index": "0",
                "X-File-Name": "../../../etc/passwd"
            },
            content=b"malicious"
        )
        
        assert response.status_code == 400
        assert "Invalid filename" in response.json()["error"]
    
    def test_reject_absolute_paths(self, server_allow_paths, test_api_key):
        """Test that absolute paths are rejected."""
        app = server_allow_paths.create_app()
        client = TestClient(app)
        
        response = client.post(
            "/upload",
            headers={
                "Authorization": f"Bearer {test_api_key}",
                "X-Chunk-Index": "0",
                "X-File-Name": "/etc/passwd"
            },
            content=b"malicious"
        )
        
        assert response.status_code == 400
    
    def test_nested_subdirectories(self, server_allow_paths, test_api_key, temp_upload_dir):
        """Test deeply nested subdirectories."""
        app = server_allow_paths.create_app()
        client = TestClient(app)
        
        response = client.post(
            "/upload",
            headers={
                "Authorization": f"Bearer {test_api_key}",
                "X-Chunk-Index": "0",
                "X-File-Name": "a/b/c/d/e/file.txt"
            },
            content=b"deep content"
        )
        
        assert response.status_code == 200
        
        uploaded_file = Path(temp_upload_dir) / "a" / "b" / "c" / "d" / "e" / "file.txt"
        assert uploaded_file.exists()


class TestChunkedUpload:
    """Test chunked file upload functionality."""
    
    def test_single_chunk_upload(self, server_sanitize, test_api_key, temp_upload_dir):
        """Test upload of single chunk file."""
        app = server_sanitize.create_app()
        client = TestClient(app)
        
        response = client.post(
            "/upload",
            headers={
                "Authorization": f"Bearer {test_api_key}",
                "X-Chunk-Index": "0",
                "X-File-Name": "single.txt"
            },
            content=b"complete content"
        )
        
        assert response.status_code == 200
        
        uploaded_file = Path(temp_upload_dir) / "single.txt"
        assert uploaded_file.read_bytes() == b"complete content"
    
    def test_multi_chunk_upload(self, server_sanitize, test_api_key, temp_upload_dir):
        """Test upload of multi-chunk file."""
        app = server_sanitize.create_app()
        client = TestClient(app)
        
        # Upload 3 chunks
        chunks = [b"chunk1", b"chunk2", b"chunk3"]
        
        for i, chunk in enumerate(chunks):
            response = client.post(
                "/upload",
                headers={
                    "Authorization": f"Bearer {test_api_key}",
                    "X-Chunk-Index": str(i),
                    "X-File-Name": "multi.txt"
                },
                content=chunk
            )
            assert response.status_code == 200
        
        # Verify reassembled file
        uploaded_file = Path(temp_upload_dir) / "multi.txt"
        assert uploaded_file.read_bytes() == b"chunk1chunk2chunk3"
    
    def test_large_chunks(self, server_sanitize, test_api_key, temp_upload_dir):
        """Test uploading large chunks."""
        app = server_sanitize.create_app()
        client = TestClient(app)
        
        # Create 1MB chunk
        large_chunk = b"X" * (1024 * 1024)
        
        response = client.post(
            "/upload",
            headers={
                "Authorization": f"Bearer {test_api_key}",
                "X-Chunk-Index": "0",
                "X-File-Name": "large.bin"
            },
            content=large_chunk
        )
        
        assert response.status_code == 200
        
        uploaded_file = Path(temp_upload_dir) / "large.bin"
        assert uploaded_file.stat().st_size == 1024 * 1024


class TestSessionManagement:
    """Test upload session management."""
    
    def test_clear_sessions(self, server_sanitize):
        """Test clearing upload sessions."""
        server_sanitize.upload_sessions["test.txt"] = "test_12345.txt"
        assert len(server_sanitize.upload_sessions) == 1
        
        server_sanitize.clear_sessions()
        assert len(server_sanitize.upload_sessions) == 0
    
    def test_session_persistence_across_chunks(self, server_sanitize, test_api_key):
        """Test that session persists across multiple chunks."""
        app = server_sanitize.create_app()
        client = TestClient(app)
        
        # Upload multiple chunks for same file
        for i in range(5):
            response = client.post(
                "/upload",
                headers={
                    "Authorization": f"Bearer {test_api_key}",
                    "X-Chunk-Index": str(i),
                    "X-File-Name": "session_test.txt"
                },
                content=f"chunk{i}".encode()
            )
            
            assert response.status_code == 200
            
            # All chunks should return same actual filename
            if i == 0:
                first_filename = response.json()["actualFilename"]
            else:
                assert response.json()["actualFilename"] == first_filename


class TestErrorHandling:
    """Test error handling and edge cases."""
    
    def test_missing_headers(self, server_sanitize, test_api_key):
        """Test upload with missing X-File-Name header uses default."""
        app = server_sanitize.create_app()
        client = TestClient(app)
        
        # Missing X-File-Name header - server provides default
        response = client.post(
            "/upload",
            headers={
                "Authorization": f"Bearer {test_api_key}",
                "X-Chunk-Index": "0"
            },
            content=b"test data"
        )
        
        # Server accepts with default filename
        assert response.status_code == 200
        assert "actualFilename" in response.json()
    
    def test_empty_filename(self, server_sanitize, test_api_key):
        """Test upload with empty filename."""
        app = server_sanitize.create_app()
        client = TestClient(app)
        
        response = client.post(
            "/upload",
            headers={
                "Authorization": f"Bearer {test_api_key}",
                "X-Chunk-Index": "0",
                "X-File-Name": ""
            },
            content=b"test data"
        )
        
        assert response.status_code == 400


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
