"""
Comprehensive tests for encryption support in IndexedCPClient
"""

import os
import pytest
import tempfile
import shutil
import asyncio
from pathlib import Path

from indexedcp import IndexedCPClient, CryptoUtils


class TestEncryptedClient:
    """Test encryption support in IndexedCPClient"""
    
    @pytest.fixture
    async def temp_dir(self):
        """Create temporary directory for test files"""
        temp_dir = tempfile.mkdtemp(prefix='test_enc_client_')
        yield temp_dir
        # Cleanup
        shutil.rmtree(temp_dir, ignore_errors=True)
    
    @pytest.fixture
    async def temp_storage(self, temp_dir):
        """Create temporary storage path"""
        storage_path = os.path.join(temp_dir, 'client_encrypted.db')
        return storage_path
    
    @pytest.fixture
    async def encrypted_client(self, temp_storage):
        """Create encrypted client instance"""
        client = IndexedCPClient(
            server_url="http://localhost:3000/upload",
            api_key="test-key",
            storage_path=temp_storage,
            encryption=True,
            chunk_size=1024,  # 1KB for testing
            log_level="DEBUG"
        )
        await client.initialize()
        yield client
        await client.close()
    
    @pytest.fixture
    def sample_file(self, temp_dir):
        """Create sample file for testing"""
        file_path = os.path.join(temp_dir, 'test_file.txt')
        with open(file_path, 'w') as f:
            f.write("This is test data for encryption.\n" * 100)
        return file_path
    
    @pytest.fixture
    def key_pair(self):
        """Generate RSA key pair for testing"""
        crypto = CryptoUtils()
        return crypto.generate_server_key_pair()
    
    @pytest.mark.asyncio
    async def test_encryption_enabled(self, encrypted_client):
        """Test that encryption is properly enabled"""
        assert encrypted_client.encryption is True
        assert hasattr(encrypted_client, 'crypto_utils')
        assert hasattr(encrypted_client, 'session_keys')
        assert hasattr(encrypted_client, 'session_seq_counters')
    
    @pytest.mark.asyncio
    async def test_encryption_storage_initialized(self, encrypted_client):
        """Test that encrypted storage is initialized"""
        from indexedcp.storage import EncryptedStorage
        assert isinstance(encrypted_client.storage, EncryptedStorage)
    
    @pytest.mark.asyncio
    async def test_fetch_public_key_requires_server_url(self, temp_storage):
        """Test that fetch_public_key requires serverUrl"""
        client = IndexedCPClient(
            server_url=None,  # No server URL
            api_key="test-key",
            storage_path=temp_storage,
            encryption=True
        )
        await client.initialize()
        
        with pytest.raises(RuntimeError, match="serverUrl required"):
            await client.fetch_public_key()
        
        await client.close()
    
    @pytest.mark.asyncio
    async def test_start_stream_generates_session(
        self,
        encrypted_client,
        key_pair
    ):
        """Test that start_stream generates a valid session"""
        # Mock cached public key
        from indexedcp.storage import EncryptedStorage
        if isinstance(encrypted_client.storage, EncryptedStorage):
            await encrypted_client.storage.save_public_key({
                'kid': key_pair['kid'],
                'publicKey': key_pair['publicKey'],
                'fetchedAt': 1699999999999,
                'expiresAt': 9999999999999  # Far future
            })
        
        # Start stream
        session_id = await encrypted_client.start_stream('test_file.txt')
        
        # Verify session created
        assert session_id is not None
        assert len(session_id) == 32  # 16 bytes hex = 32 chars
        assert session_id in encrypted_client.session_keys
        assert session_id in encrypted_client.session_seq_counters
        
        # Verify session in storage
        session = await encrypted_client.storage.get_session(session_id)
        assert session is not None
        assert session['fileName'] == 'test_file.txt'
        assert session['kid'] == key_pair['kid']
        assert 'wrappedKey' in session
    
    @pytest.mark.asyncio
    async def test_add_packet_encrypts_data(
        self,
        encrypted_client,
        key_pair
    ):
        """Test that add_packet properly encrypts data"""
        # Setup: cache public key and start stream
        from indexedcp.storage import EncryptedStorage
        if isinstance(encrypted_client.storage, EncryptedStorage):
            await encrypted_client.storage.save_public_key({
                'kid': key_pair['kid'],
                'publicKey': key_pair['publicKey'],
                'fetchedAt': 1699999999999,
                'expiresAt': 9999999999999
            })
        
        session_id = await encrypted_client.start_stream('test_file.txt')
        
        # Add packet
        test_data = b"This is secret test data"
        await encrypted_client.add_packet(session_id, test_data, seq=0)
        
        # Verify packet stored
        packets = await encrypted_client.storage.get_packets_by_session(session_id)
        assert len(packets) == 1
        
        packet = packets[0]
        assert packet['sessionId'] == session_id
        assert packet['seq'] == 0
        assert 'ciphertext' in packet
        assert 'iv' in packet
        assert 'authTag' in packet
        assert 'aad' in packet
        assert packet['status'] == 'pending'
        
        # Verify data is encrypted (not plaintext)
        import base64
        ciphertext = base64.b64decode(packet['ciphertext'])
        assert ciphertext != test_data
    
    @pytest.mark.asyncio
    async def test_add_packet_auto_increments_seq(
        self,
        encrypted_client,
        key_pair
    ):
        """Test that add_packet auto-increments sequence numbers"""
        # Setup
        from indexedcp.storage import EncryptedStorage
        if isinstance(encrypted_client.storage, EncryptedStorage):
            await encrypted_client.storage.save_public_key({
                'kid': key_pair['kid'],
                'publicKey': key_pair['publicKey'],
                'fetchedAt': 1699999999999,
                'expiresAt': 9999999999999
            })
        
        session_id = await encrypted_client.start_stream('test_file.txt')
        
        # Add multiple packets without specifying seq
        await encrypted_client.add_packet(session_id, b"Packet 1")
        await encrypted_client.add_packet(session_id, b"Packet 2")
        await encrypted_client.add_packet(session_id, b"Packet 3")
        
        # Verify sequence numbers
        packets = await encrypted_client.storage.get_packets_by_session(session_id)
        assert len(packets) == 3
        assert packets[0]['seq'] == 0
        assert packets[1]['seq'] == 1
        assert packets[2]['seq'] == 2
    
    @pytest.mark.asyncio
    async def test_add_file_encrypted(
        self,
        encrypted_client,
        sample_file,
        key_pair
    ):
        """Test that add_file encrypts entire file"""
        # Setup: cache public key
        from indexedcp.storage import EncryptedStorage
        if isinstance(encrypted_client.storage, EncryptedStorage):
            await encrypted_client.storage.save_public_key({
                'kid': key_pair['kid'],
                'publicKey': key_pair['publicKey'],
                'fetchedAt': 1699999999999,
                'expiresAt': 9999999999999
            })
        
        # Add file (should return session_id)
        session_id = await encrypted_client.add_file(sample_file)
        
        # Verify session_id returned
        assert isinstance(session_id, str)
        assert len(session_id) == 32
        
        # Verify packets created
        packets = await encrypted_client.storage.get_packets_by_session(session_id)
        assert len(packets) > 0
        
        # Verify all packets have sequential sequence numbers
        for i, packet in enumerate(packets):
            assert packet['seq'] == i
            assert packet['status'] == 'pending'
        
        # Verify session key cleared from memory
        assert session_id not in encrypted_client.session_keys
    
    @pytest.mark.asyncio
    async def test_get_encryption_status(
        self,
        encrypted_client,
        sample_file,
        key_pair
    ):
        """Test encryption status reporting"""
        # Setup and add file
        from indexedcp.storage import EncryptedStorage
        if isinstance(encrypted_client.storage, EncryptedStorage):
            await encrypted_client.storage.save_public_key({
                'kid': key_pair['kid'],
                'publicKey': key_pair['publicKey'],
                'fetchedAt': 1699999999999,
                'expiresAt': 9999999999999
            })
        
        await encrypted_client.add_file(sample_file)
        
        # Get status
        status = await encrypted_client.get_encryption_status()
        
        assert status['encryption'] is True
        assert status['isEncrypted'] is True
        assert status['activeSessions'] == 1
        assert status['pendingPackets'] > 0
        assert status['cachedKey'] == key_pair['kid']
        assert status['currentKeyId'] == key_pair['kid']
    
    @pytest.mark.asyncio
    async def test_encryption_preserves_packet_order(
        self,
        encrypted_client,
        key_pair
    ):
        """Test that packets maintain correct order"""
        # Setup
        from indexedcp.storage import EncryptedStorage
        if isinstance(encrypted_client.storage, EncryptedStorage):
            await encrypted_client.storage.save_public_key({
                'kid': key_pair['kid'],
                'publicKey': key_pair['publicKey'],
                'fetchedAt': 1699999999999,
                'expiresAt': 9999999999999
            })
        
        session_id = await encrypted_client.start_stream('ordered_test.txt')
        
        # Add packets in specific order
        for i in range(10):
            await encrypted_client.add_packet(session_id, f"Packet {i}".encode())
        
        # Retrieve packets
        packets = await encrypted_client.storage.get_packets_by_session(session_id)
        
        # Verify order preserved
        assert len(packets) == 10
        for i, packet in enumerate(packets):
            assert packet['seq'] == i
    
    @pytest.mark.asyncio
    async def test_multiple_sessions_isolated(
        self,
        encrypted_client,
        key_pair
    ):
        """Test that multiple sessions are properly isolated"""
        # Setup
        from indexedcp.storage import EncryptedStorage
        if isinstance(encrypted_client.storage, EncryptedStorage):
            await encrypted_client.storage.save_public_key({
                'kid': key_pair['kid'],
                'publicKey': key_pair['publicKey'],
                'fetchedAt': 1699999999999,
                'expiresAt': 9999999999999
            })
        
        # Create multiple sessions
        session1 = await encrypted_client.start_stream('file1.txt')
        session2 = await encrypted_client.start_stream('file2.txt')
        
        # Add packets to different sessions
        await encrypted_client.add_packet(session1, b"Data for file 1")
        await encrypted_client.add_packet(session2, b"Data for file 2")
        await encrypted_client.add_packet(session1, b"More data for file 1")
        
        # Verify isolation
        packets1 = await encrypted_client.storage.get_packets_by_session(session1)
        packets2 = await encrypted_client.storage.get_packets_by_session(session2)
        
        assert len(packets1) == 2
        assert len(packets2) == 1
        assert packets1[0]['sessionId'] == session1
        assert packets2[0]['sessionId'] == session2


class TestEncryptedClientBackwardCompatibility:
    """Test backward compatibility with non-encrypted mode"""
    
    @pytest.fixture
    async def temp_dir(self):
        """Create temporary directory"""
        temp_dir = tempfile.mkdtemp(prefix='test_compat_')
        yield temp_dir
        shutil.rmtree(temp_dir, ignore_errors=True)
    
    @pytest.fixture
    async def normal_client(self, temp_dir):
        """Create normal (non-encrypted) client"""
        storage_path = os.path.join(temp_dir, 'client_normal.db')
        client = IndexedCPClient(
            server_url="http://localhost:3000/upload",
            api_key="test-key",
            storage_path=storage_path,
            encryption=False,  # Explicitly disabled
            chunk_size=1024,
            log_level="INFO"
        )
        await client.initialize()
        yield client
        await client.close()
    
    @pytest.mark.asyncio
    async def test_normal_mode_no_encryption(self, normal_client):
        """Test that normal mode doesn't have encryption features"""
        assert normal_client.encryption is False
        assert not hasattr(normal_client, 'crypto_utils')
        assert not hasattr(normal_client, 'session_keys')
    
    @pytest.mark.asyncio
    async def test_normal_mode_uses_sqlite_storage(self, normal_client):
        """Test that normal mode uses SQLiteStorage"""
        from indexedcp.storage import SQLiteStorage
        assert isinstance(normal_client.storage, SQLiteStorage)
    
    @pytest.mark.asyncio
    async def test_encryption_methods_raise_error_in_normal_mode(
        self,
        normal_client
    ):
        """Test that encryption methods raise errors in normal mode"""
        with pytest.raises(RuntimeError, match="Encryption not enabled"):
            await normal_client.fetch_public_key()
        
        with pytest.raises(RuntimeError, match="Encryption not enabled"):
            await normal_client.get_cached_public_key()
        
        with pytest.raises(RuntimeError, match="Encryption not enabled"):
            await normal_client.start_stream('test.txt')
    
    @pytest.mark.asyncio
    async def test_normal_mode_add_file_returns_chunk_count(
        self,
        normal_client,
        temp_dir
    ):
        """Test that normal mode add_file returns chunk count"""
        # Create test file
        file_path = os.path.join(temp_dir, 'test.txt')
        with open(file_path, 'w') as f:
            f.write("Test data\n" * 100)
        
        # Add file
        result = await normal_client.add_file(file_path)
        
        # Should return integer (chunk count)
        assert isinstance(result, int)
        assert result > 0


class TestEncryptedStorageIntegration:
    """Test integration with EncryptedStorage"""
    
    @pytest.fixture
    async def temp_storage(self):
        """Create temporary storage"""
        temp_dir = tempfile.mkdtemp(prefix='test_enc_storage_')
        storage_path = os.path.join(temp_dir, 'test.db')
        yield storage_path
        shutil.rmtree(temp_dir, ignore_errors=True)
    
    @pytest.mark.asyncio
    async def test_encrypted_storage_three_table_schema(self, temp_storage):
        """Test that encrypted storage creates three tables"""
        from indexedcp.storage import EncryptedStorage
        
        storage = EncryptedStorage(db_path=temp_storage)
        await storage.initialize()
        
        # Verify tables exist by attempting operations
        # Sessions
        await storage.save_session({
            'sessionId': 'test-session',
            'kid': 'test-kid',
            'wrappedKey': 'wrapped-key-data',
            'fileName': 'test.txt',
            'createdAt': 1699999999999
        })
        
        session = await storage.get_session('test-session')
        assert session is not None
        
        # Packets
        await storage.save_packet({
            'id': 'test-session-0',
            'sessionId': 'test-session',
            'seq': 0,
            'ciphertext': 'encrypted-data',
            'iv': 'iv-data',
            'authTag': 'tag-data',
            'aad': 'aad-data',
            'status': 'pending',
            'createdAt': 1699999999999
        })
        
        packets = await storage.get_packets_by_session('test-session')
        assert len(packets) == 1
        
        # Key cache
        await storage.save_public_key({
            'kid': 'test-kid',
            'publicKey': 'public-key-data',
            'fetchedAt': 1699999999999,
            'expiresAt': 9999999999999
        })
        
        key = await storage.get_cached_public_key()
        assert key is not None
        
        await storage.close()


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
