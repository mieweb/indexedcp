"""
Comprehensive tests for crypto_utils module
"""

import os
import pytest
import json
from cryptography.exceptions import InvalidTag

from indexedcp.crypto_utils import CryptoUtils


class TestCryptoUtils:
    """Test suite for CryptoUtils class"""
    
    @pytest.fixture
    def crypto(self):
        """Create CryptoUtils instance for testing"""
        return CryptoUtils()
    
    @pytest.fixture
    def key_pair(self, crypto):
        """Generate RSA key pair for testing"""
        return crypto.generate_server_key_pair()
    
    @pytest.fixture
    def session_key(self, crypto):
        """Generate AES session key for testing"""
        return crypto.generate_session_key()
    
    def test_generate_server_key_pair(self, crypto):
        """Test RSA-4096 key pair generation"""
        key_pair = crypto.generate_server_key_pair()
        
        # Check structure
        assert 'publicKey' in key_pair
        assert 'privateKey' in key_pair
        assert 'kid' in key_pair
        
        # Check PEM format
        assert key_pair['publicKey'].startswith('-----BEGIN PUBLIC KEY-----')
        assert key_pair['privateKey'].startswith('-----BEGIN PRIVATE KEY-----')
        
        # Check key ID format (16 hex characters)
        assert len(key_pair['kid']) == 16
        assert all(c in '0123456789abcdef' for c in key_pair['kid'])
    
    def test_generate_server_key_pair_custom_size(self, crypto):
        """Test RSA key pair generation with custom modulus length"""
        key_pair = crypto.generate_server_key_pair(modulus_length=2048)
        
        assert 'publicKey' in key_pair
        assert 'privateKey' in key_pair
        assert 'kid' in key_pair
    
    def test_generate_session_key(self, crypto):
        """Test AES-256 session key generation"""
        session_key = crypto.generate_session_key()
        
        # Check length (256 bits = 32 bytes)
        assert len(session_key) == 32
        assert isinstance(session_key, bytes)
    
    def test_session_keys_are_unique(self, crypto):
        """Test that generated session keys are unique"""
        key1 = crypto.generate_session_key()
        key2 = crypto.generate_session_key()
        
        assert key1 != key2
    
    def test_wrap_and_unwrap_session_key(self, crypto, key_pair, session_key):
        """Test RSA-OAEP key wrapping and unwrapping"""
        # Wrap session key with public key
        wrapped_key = crypto.wrap_session_key(
            session_key, 
            key_pair['publicKey']
        )
        
        # Check wrapped key is bytes
        assert isinstance(wrapped_key, bytes)
        assert len(wrapped_key) > 0
        
        # Unwrap session key with private key
        unwrapped_key = crypto.unwrap_session_key(
            wrapped_key,
            key_pair['privateKey']
        )
        
        # Check unwrapped key matches original
        assert unwrapped_key == session_key
    
    def test_wrapped_keys_are_different(self, crypto, key_pair):
        """Test that wrapping the same key produces different results (due to OAEP padding)"""
        session_key = crypto.generate_session_key()
        
        wrapped1 = crypto.wrap_session_key(session_key, key_pair['publicKey'])
        wrapped2 = crypto.wrap_session_key(session_key, key_pair['publicKey'])
        
        # OAEP padding includes randomness, so ciphertexts differ
        assert wrapped1 != wrapped2
    
    def test_encrypt_and_decrypt_packet(self, crypto, session_key):
        """Test AES-256-GCM packet encryption and decryption"""
        # Test data
        plaintext = b"Hello, this is a test message!"
        metadata = {
            'sessionId': 'test-session-123',
            'seq': 1,
            'codec': 'raw',
            'timestamp': 1699999999999
        }
        
        # Encrypt packet
        encrypted = crypto.encrypt_packet(plaintext, session_key, metadata)
        
        # Check structure
        assert 'ciphertext' in encrypted
        assert 'iv' in encrypted
        assert 'authTag' in encrypted
        assert 'aad' in encrypted
        
        # Check types
        assert isinstance(encrypted['ciphertext'], bytes)
        assert isinstance(encrypted['iv'], bytes)
        assert isinstance(encrypted['authTag'], bytes)
        assert isinstance(encrypted['aad'], bytes)
        
        # Check lengths
        assert len(encrypted['iv']) == 12  # 96 bits
        assert len(encrypted['authTag']) == 16  # 128 bits
        
        # Decrypt packet
        decrypted = crypto.decrypt_packet(
            encrypted['ciphertext'],
            session_key,
            encrypted['iv'],
            encrypted['authTag'],
            encrypted['aad']
        )
        
        # Check decrypted matches original
        assert decrypted == plaintext
    
    def test_encrypt_produces_unique_ivs(self, crypto, session_key):
        """Test that each encryption uses a unique IV"""
        plaintext = b"Test data"
        metadata = {'sessionId': 'test', 'seq': 1}
        
        encrypted1 = crypto.encrypt_packet(plaintext, session_key, metadata)
        encrypted2 = crypto.encrypt_packet(plaintext, session_key, metadata)
        
        # IVs should be different
        assert encrypted1['iv'] != encrypted2['iv']
        
        # Ciphertexts should be different (due to different IVs)
        assert encrypted1['ciphertext'] != encrypted2['ciphertext']
    
    def test_decrypt_with_wrong_key_fails(self, crypto):
        """Test that decryption fails with wrong session key"""
        plaintext = b"Secret data"
        metadata = {'sessionId': 'test', 'seq': 1}
        
        # Encrypt with one key
        session_key1 = crypto.generate_session_key()
        encrypted = crypto.encrypt_packet(plaintext, session_key1, metadata)
        
        # Try to decrypt with different key
        session_key2 = crypto.generate_session_key()
        
        with pytest.raises(InvalidTag):
            crypto.decrypt_packet(
                encrypted['ciphertext'],
                session_key2,
                encrypted['iv'],
                encrypted['authTag'],
                encrypted['aad']
            )
    
    def test_decrypt_with_tampered_ciphertext_fails(self, crypto, session_key):
        """Test that decryption fails if ciphertext is tampered"""
        plaintext = b"Important data"
        metadata = {'sessionId': 'test', 'seq': 1}
        
        encrypted = crypto.encrypt_packet(plaintext, session_key, metadata)
        
        # Tamper with ciphertext
        tampered_ciphertext = bytearray(encrypted['ciphertext'])
        tampered_ciphertext[0] ^= 0xFF  # Flip bits in first byte
        
        with pytest.raises(InvalidTag):
            crypto.decrypt_packet(
                bytes(tampered_ciphertext),
                session_key,
                encrypted['iv'],
                encrypted['authTag'],
                encrypted['aad']
            )
    
    def test_decrypt_with_tampered_aad_fails(self, crypto, session_key):
        """Test that decryption fails if AAD is tampered"""
        plaintext = b"Critical data"
        metadata = {'sessionId': 'test', 'seq': 1}
        
        encrypted = crypto.encrypt_packet(plaintext, session_key, metadata)
        
        # Tamper with AAD
        tampered_aad = b'{"sessionId":"test","seq":999,"codec":"raw","timestamp":1699999999999}'
        
        with pytest.raises(InvalidTag):
            crypto.decrypt_packet(
                encrypted['ciphertext'],
                session_key,
                encrypted['iv'],
                encrypted['authTag'],
                tampered_aad
            )
    
    def test_serialize_and_deserialize_packet(self, crypto, session_key):
        """Test packet serialization for storage"""
        plaintext = b"Test data for serialization"
        metadata = {'sessionId': 'test', 'seq': 1}
        
        # Encrypt packet
        encrypted = crypto.encrypt_packet(plaintext, session_key, metadata)
        
        # Serialize
        serialized = crypto.serialize_packet(encrypted)
        
        # Check serialized types (all strings)
        assert isinstance(serialized['ciphertext'], str)
        assert isinstance(serialized['iv'], str)
        assert isinstance(serialized['authTag'], str)
        assert isinstance(serialized['aad'], str)
        
        # Deserialize
        deserialized = crypto.deserialize_packet(serialized)
        
        # Check deserialized matches original
        assert deserialized['ciphertext'] == encrypted['ciphertext']
        assert deserialized['iv'] == encrypted['iv']
        assert deserialized['authTag'] == encrypted['authTag']
        assert deserialized['aad'] == encrypted['aad']
        
        # Decrypt deserialized packet
        decrypted = crypto.decrypt_packet(
            deserialized['ciphertext'],
            session_key,
            deserialized['iv'],
            deserialized['authTag'],
            deserialized['aad']
        )
        
        assert decrypted == plaintext
    
    def test_parse_aad(self, crypto):
        """Test AAD parsing"""
        metadata = {
            'sessionId': 'test-session',
            'seq': 42,
            'codec': 'gzip',
            'timestamp': 1699999999999
        }
        
        aad = json.dumps(metadata, separators=(',', ':')).encode()
        parsed = crypto.parse_aad(aad)
        
        assert parsed['sessionId'] == 'test-session'
        assert parsed['seq'] == 42
        assert parsed['codec'] == 'gzip'
        assert parsed['timestamp'] == 1699999999999
    
    def test_is_valid_key_id(self, crypto):
        """Test key ID validation"""
        # Valid key IDs (16 hex characters)
        assert crypto.is_valid_key_id('0123456789abcdef')
        assert crypto.is_valid_key_id('fedcba9876543210')
        assert crypto.is_valid_key_id('a1b2c3d4e5f60718')
        
        # Invalid key IDs
        assert not crypto.is_valid_key_id('0123456789ABCDEF')  # Uppercase
        assert not crypto.is_valid_key_id('0123456789abcde')   # Too short
        assert not crypto.is_valid_key_id('0123456789abcdef0') # Too long
        assert not crypto.is_valid_key_id('xyz123456789abcd')  # Invalid chars
        assert not crypto.is_valid_key_id('')                   # Empty
    
    def test_generate_session_id(self, crypto):
        """Test session ID generation"""
        session_id = crypto.generate_session_id()
        
        # Check format (32 hex characters)
        assert len(session_id) == 32
        assert all(c in '0123456789abcdef' for c in session_id)
        
        # Check uniqueness
        session_id2 = crypto.generate_session_id()
        assert session_id != session_id2
    
    def test_large_data_encryption(self, crypto, session_key):
        """Test encryption of large data (1MB)"""
        # Generate 1MB of random data
        large_data = os.urandom(1024 * 1024)
        metadata = {'sessionId': 'test', 'seq': 1}
        
        # Encrypt
        encrypted = crypto.encrypt_packet(large_data, session_key, metadata)
        
        # Decrypt
        decrypted = crypto.decrypt_packet(
            encrypted['ciphertext'],
            session_key,
            encrypted['iv'],
            encrypted['authTag'],
            encrypted['aad']
        )
        
        assert decrypted == large_data
    
    def test_empty_data_encryption(self, crypto, session_key):
        """Test encryption of empty data"""
        plaintext = b""
        metadata = {'sessionId': 'test', 'seq': 1}
        
        encrypted = crypto.encrypt_packet(plaintext, session_key, metadata)
        decrypted = crypto.decrypt_packet(
            encrypted['ciphertext'],
            session_key,
            encrypted['iv'],
            encrypted['authTag'],
            encrypted['aad']
        )
        
        assert decrypted == plaintext
    
    def test_class_instantiation(self):
        """Test that CryptoUtils can be instantiated multiple times"""
        crypto1 = CryptoUtils()
        crypto2 = CryptoUtils()
        
        # Each instance should work independently
        key_pair = crypto1.generate_server_key_pair()
        assert 'kid' in key_pair
        
        session_key = crypto2.generate_session_key()
        assert len(session_key) == 32


class TestEndToEndEncryption:
    """End-to-end encryption workflow tests"""
    
    def test_full_encryption_workflow(self):
        """Test complete encryption workflow from key generation to decryption"""
        crypto = CryptoUtils()
        
        # 1. Server generates RSA key pair
        server_keys = crypto.generate_server_key_pair()
        
        # 2. Client generates ephemeral AES session key
        session_key = crypto.generate_session_key()
        
        # 3. Client wraps session key with server's public key
        wrapped_key = crypto.wrap_session_key(
            session_key,
            server_keys['publicKey']
        )
        
        # 4. Client encrypts data
        plaintext = b"Sensitive file data"
        metadata = {
            'sessionId': crypto.generate_session_id(),
            'seq': 1,
            'codec': 'raw'
        }
        encrypted_packet = crypto.encrypt_packet(plaintext, session_key, metadata)
        
        # 5. Serialize for storage/transmission
        serialized = crypto.serialize_packet(encrypted_packet)
        
        # Simulate storage/network transmission
        # In real scenario, client would store serialized packet + wrapped_key
        
        # 6. Server unwraps session key
        unwrapped_key = crypto.unwrap_session_key(
            wrapped_key,
            server_keys['privateKey']
        )
        
        # 7. Server deserializes packet
        deserialized = crypto.deserialize_packet(serialized)
        
        # 8. Server decrypts data
        decrypted = crypto.decrypt_packet(
            deserialized['ciphertext'],
            unwrapped_key,
            deserialized['iv'],
            deserialized['authTag'],
            deserialized['aad']
        )
        
        # 9. Verify plaintext matches original
        assert decrypted == plaintext
    
    def test_multiple_packets_same_session(self):
        """Test encrypting multiple packets with same session key"""
        crypto = CryptoUtils()
        
        session_key = crypto.generate_session_key()
        session_id = crypto.generate_session_id()
        
        packets_plaintext = [
            b"Packet 1 data",
            b"Packet 2 data",
            b"Packet 3 data"
        ]
        
        # Encrypt all packets
        encrypted_packets = []
        for seq, plaintext in enumerate(packets_plaintext):
            metadata = {
                'sessionId': session_id,
                'seq': seq,
                'codec': 'raw'
            }
            encrypted = crypto.encrypt_packet(plaintext, session_key, metadata)
            encrypted_packets.append(encrypted)
        
        # Decrypt all packets
        for seq, encrypted in enumerate(encrypted_packets):
            decrypted = crypto.decrypt_packet(
                encrypted['ciphertext'],
                session_key,
                encrypted['iv'],
                encrypted['authTag'],
                encrypted['aad']
            )
            assert decrypted == packets_plaintext[seq]
    
    def test_key_rotation_scenario(self):
        """Test scenario where server rotates keys but old keys still work"""
        crypto = CryptoUtils()
        
        # Old key pair
        old_keys = crypto.generate_server_key_pair()
        
        # Client encrypts with old public key
        session_key = crypto.generate_session_key()
        wrapped_key = crypto.wrap_session_key(session_key, old_keys['publicKey'])
        
        plaintext = b"Data encrypted with old key"
        metadata = {'sessionId': crypto.generate_session_id(), 'seq': 1}
        encrypted = crypto.encrypt_packet(plaintext, session_key, metadata)
        
        # Server rotates to new key pair (but keeps old private key)
        new_keys = crypto.generate_server_key_pair()
        
        # Server can still decrypt old data with old private key
        unwrapped_key = crypto.unwrap_session_key(wrapped_key, old_keys['privateKey'])
        decrypted = crypto.decrypt_packet(
            encrypted['ciphertext'],
            unwrapped_key,
            encrypted['iv'],
            encrypted['authTag'],
            encrypted['aad']
        )
        
        assert decrypted == plaintext
