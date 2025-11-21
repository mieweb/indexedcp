"""
Comprehensive tests for keystore implementations
"""

import os
import json
import stat
import pytest
import tempfile
import shutil
from pathlib import Path

from indexedcp.keystores import (
    BaseKeyStore,
    FileSystemKeyStore,
    create_keystore
)
from indexedcp import CryptoUtils


class TestBaseKeyStore:
    """Test BaseKeyStore abstract class"""
    
    def test_cannot_instantiate_directly(self):
        """Test that BaseKeyStore cannot be instantiated directly"""
        with pytest.raises(TypeError):
            BaseKeyStore()
    
    def test_abstract_methods_must_be_implemented(self):
        """Test that subclasses must implement abstract methods"""
        
        class IncompleteKeyStore(BaseKeyStore):
            pass
        
        with pytest.raises(TypeError):
            IncompleteKeyStore()


class TestFileSystemKeyStore:
    """Test FileSystemKeyStore implementation"""
    
    @pytest.fixture
    async def temp_keystore_dir(self):
        """Create temporary directory for keystore tests"""
        temp_dir = tempfile.mkdtemp(prefix='test_keystore_')
        yield temp_dir
        # Cleanup
        shutil.rmtree(temp_dir, ignore_errors=True)
    
    @pytest.fixture
    async def keystore(self, temp_keystore_dir):
        """Create filesystem keystore instance"""
        ks = FileSystemKeyStore({'key_store_path': temp_keystore_dir})
        await ks.initialize()
        yield ks
        await ks.close()
    
    @pytest.fixture
    def sample_key_data(self):
        """Generate sample key data for testing"""
        crypto = CryptoUtils()
        key_pair = crypto.generate_server_key_pair()
        return {
            'kid': key_pair['kid'],
            'publicKey': key_pair['publicKey'],
            'privateKey': key_pair['privateKey'],
            'createdAt': 1699999999999,
            'active': True
        }
    
    @pytest.mark.asyncio
    async def test_initialize_creates_directory(self, temp_keystore_dir):
        """Test that initialize creates the keystore directory"""
        keystore = FileSystemKeyStore({'key_store_path': temp_keystore_dir})
        await keystore.initialize()
        
        assert Path(temp_keystore_dir).exists()
        assert Path(temp_keystore_dir).is_dir()
        
        # Check directory permissions (0700)
        dir_stat = os.stat(temp_keystore_dir)
        dir_mode = stat.S_IMODE(dir_stat.st_mode)
        assert dir_mode == stat.S_IRWXU  # 0700
    
    @pytest.mark.asyncio
    async def test_save_and_load(self, keystore, sample_key_data):
        """Test saving and loading a key"""
        # Save key
        await keystore.save(sample_key_data['kid'], sample_key_data)
        
        # Load key
        loaded = await keystore.load(sample_key_data['kid'])
        
        assert loaded is not None
        assert loaded['kid'] == sample_key_data['kid']
        assert loaded['publicKey'] == sample_key_data['publicKey']
        assert loaded['privateKey'] == sample_key_data['privateKey']
        assert loaded['createdAt'] == sample_key_data['createdAt']
        assert loaded['active'] == sample_key_data['active']
    
    @pytest.mark.asyncio
    async def test_save_sets_file_permissions(self, keystore, sample_key_data, temp_keystore_dir):
        """Test that saved key files have correct permissions (0600)"""
        await keystore.save(sample_key_data['kid'], sample_key_data)
        
        key_file = Path(temp_keystore_dir) / f"{sample_key_data['kid']}.json"
        file_stat = os.stat(key_file)
        file_mode = stat.S_IMODE(file_stat.st_mode)
        
        # Check file permissions (0600 - owner read/write only)
        assert file_mode == (stat.S_IRUSR | stat.S_IWUSR)  # 0600
    
    @pytest.mark.asyncio
    async def test_load_nonexistent_returns_none(self, keystore):
        """Test that loading non-existent key returns None"""
        loaded = await keystore.load('non-existent-kid')
        assert loaded is None
    
    @pytest.mark.asyncio
    async def test_exists(self, keystore, sample_key_data):
        """Test key existence check"""
        # Key doesn't exist yet
        assert await keystore.exists(sample_key_data['kid']) is False
        
        # Save key
        await keystore.save(sample_key_data['kid'], sample_key_data)
        
        # Key now exists
        assert await keystore.exists(sample_key_data['kid']) is True
    
    @pytest.mark.asyncio
    async def test_delete(self, keystore, sample_key_data):
        """Test deleting a key"""
        # Save key
        await keystore.save(sample_key_data['kid'], sample_key_data)
        assert await keystore.exists(sample_key_data['kid']) is True
        
        # Delete key
        result = await keystore.delete(sample_key_data['kid'])
        assert result is True
        
        # Key no longer exists
        assert await keystore.exists(sample_key_data['kid']) is False
    
    @pytest.mark.asyncio
    async def test_delete_nonexistent_returns_false(self, keystore):
        """Test that deleting non-existent key returns False"""
        result = await keystore.delete('non-existent-kid')
        assert result is False
    
    @pytest.mark.asyncio
    async def test_list(self, keystore):
        """Test listing key IDs"""
        # Create multiple keys
        crypto = CryptoUtils()
        keys = []
        for _ in range(3):
            kp = crypto.generate_server_key_pair()
            key_data = {
                'kid': kp['kid'],
                'publicKey': kp['publicKey'],
                'privateKey': kp['privateKey'],
                'createdAt': 1699999999999,
                'active': False
            }
            keys.append(key_data)
            await keystore.save(key_data['kid'], key_data)
        
        # List keys
        key_list = await keystore.list()
        
        assert len(key_list) == 3
        for key_data in keys:
            assert key_data['kid'] in key_list
    
    @pytest.mark.asyncio
    async def test_load_all(self, keystore):
        """Test loading all keys"""
        # Create multiple keys
        crypto = CryptoUtils()
        keys = []
        for _ in range(3):
            kp = crypto.generate_server_key_pair()
            key_data = {
                'kid': kp['kid'],
                'publicKey': kp['publicKey'],
                'privateKey': kp['privateKey'],
                'createdAt': 1699999999999,
                'active': False
            }
            keys.append(key_data)
            await keystore.save(key_data['kid'], key_data)
        
        # Load all keys
        all_keys = await keystore.load_all()
        
        assert len(all_keys) == 3
        loaded_kids = {k['kid'] for k in all_keys}
        expected_kids = {k['kid'] for k in keys}
        assert loaded_kids == expected_kids
    
    @pytest.mark.asyncio
    async def test_load_all_empty_directory(self, keystore):
        """Test loading all keys from empty directory"""
        all_keys = await keystore.load_all()
        assert all_keys == []
    
    @pytest.mark.asyncio
    async def test_json_format(self, keystore, sample_key_data, temp_keystore_dir):
        """Test that keys are stored in proper JSON format"""
        await keystore.save(sample_key_data['kid'], sample_key_data)
        
        # Read file directly
        key_file = Path(temp_keystore_dir) / f"{sample_key_data['kid']}.json"
        with open(key_file, 'r') as f:
            data = json.load(f)
        
        assert data == sample_key_data
    
    @pytest.mark.asyncio
    async def test_file_locking_concurrent_writes(self, keystore, sample_key_data):
        """Test that file locking works for concurrent operations"""
        import asyncio
        
        # Attempt concurrent saves (file locking should handle this)
        async def save_operation(kid_suffix):
            key_data = sample_key_data.copy()
            key_data['kid'] = f"{sample_key_data['kid']}_{kid_suffix}"
            await keystore.save(key_data['kid'], key_data)
        
        # Run concurrent saves
        await asyncio.gather(
            save_operation('1'),
            save_operation('2'),
            save_operation('3')
        )
        
        # Verify all keys were saved
        all_keys = await keystore.load_all()
        assert len(all_keys) == 3
    
    @pytest.mark.asyncio
    async def test_persistence_across_instances(self, temp_keystore_dir, sample_key_data):
        """Test that keys persist across keystore instances"""
        # Create first instance and save key
        keystore1 = FileSystemKeyStore({'key_store_path': temp_keystore_dir})
        await keystore1.initialize()
        await keystore1.save(sample_key_data['kid'], sample_key_data)
        await keystore1.close()
        
        # Create second instance and load key
        keystore2 = FileSystemKeyStore({'key_store_path': temp_keystore_dir})
        await keystore2.initialize()
        loaded = await keystore2.load(sample_key_data['kid'])
        await keystore2.close()
        
        assert loaded is not None
        assert loaded['kid'] == sample_key_data['kid']


class TestKeystoreFactory:
    """Test keystore factory function"""
    
    def test_create_filesystem_keystore(self):
        """Test factory creates FileSystemKeyStore"""
        keystore = create_keystore('filesystem', {'key_store_path': './test-keys'})
        assert isinstance(keystore, FileSystemKeyStore)
    
    def test_create_filesystem_keystore_aliases(self):
        """Test factory recognizes filesystem aliases"""
        # Test all aliases
        for alias in ['filesystem', 'file', 'fs']:
            keystore = create_keystore(alias, {'key_store_path': './test-keys'})
            assert isinstance(keystore, FileSystemKeyStore)
    
    def test_create_filesystem_keystore_case_insensitive(self):
        """Test factory is case-insensitive"""
        keystore = create_keystore('FileSystem', {'key_store_path': './test-keys'})
        assert isinstance(keystore, FileSystemKeyStore)
    
    def test_factory_invalid_type_raises_error(self):
        """Test factory raises error for invalid type"""
        with pytest.raises(ValueError) as exc_info:
            create_keystore('invalid-type')
        
        assert 'Unknown keystore type' in str(exc_info.value)
        assert 'invalid-type' in str(exc_info.value)
    
    def test_factory_with_options(self):
        """Test factory passes options to keystore"""
        keystore = create_keystore('filesystem', {
            'key_store_path': './custom-path',
            'log_level': 'DEBUG'
        })
        assert isinstance(keystore, FileSystemKeyStore)
        assert keystore.key_store_path == Path('./custom-path')


class TestKeystoreIntegration:
    """Integration tests for keystore with crypto operations"""
    
    @pytest.fixture
    async def temp_dir(self):
        """Create temporary directory"""
        temp_dir = tempfile.mkdtemp(prefix='test_integration_')
        yield temp_dir
        shutil.rmtree(temp_dir, ignore_errors=True)
    
    @pytest.mark.asyncio
    async def test_full_key_lifecycle(self, temp_dir):
        """Test complete key lifecycle: generate, save, load, use, delete"""
        # Create keystore
        keystore = create_keystore('filesystem', {'key_store_path': temp_dir})
        await keystore.initialize()
        
        # Generate key pair
        crypto = CryptoUtils()
        key_pair = crypto.generate_server_key_pair()
        
        # Save to keystore
        key_data = {
            'kid': key_pair['kid'],
            'publicKey': key_pair['publicKey'],
            'privateKey': key_pair['privateKey'],
            'createdAt': 1699999999999,
            'active': True
        }
        await keystore.save(key_data['kid'], key_data)
        
        # Load from keystore
        loaded = await keystore.load(key_data['kid'])
        assert loaded is not None
        
        # Use the loaded key for encryption/decryption
        session_key = crypto.generate_session_key()
        wrapped = crypto.wrap_session_key(session_key, loaded['publicKey'])
        unwrapped = crypto.unwrap_session_key(wrapped, loaded['privateKey'])
        assert session_key == unwrapped
        
        # Delete key
        await keystore.delete(key_data['kid'])
        assert await keystore.exists(key_data['kid']) is False
        
        await keystore.close()
    
    @pytest.mark.asyncio
    async def test_key_rotation_scenario(self, temp_dir):
        """Test key rotation: new key active, old key retained for decryption"""
        keystore = create_keystore('filesystem', {'key_store_path': temp_dir})
        await keystore.initialize()
        
        crypto = CryptoUtils()
        
        # Generate and save old key (initially active)
        old_kp = crypto.generate_server_key_pair()
        old_key = {
            'kid': old_kp['kid'],
            'publicKey': old_kp['publicKey'],
            'privateKey': old_kp['privateKey'],
            'createdAt': 1699999999999,
            'active': True
        }
        await keystore.save(old_key['kid'], old_key)
        
        # Generate and save new key (now active)
        new_kp = crypto.generate_server_key_pair()
        new_key = {
            'kid': new_kp['kid'],
            'publicKey': new_kp['publicKey'],
            'privateKey': new_kp['privateKey'],
            'createdAt': 1700000000000,
            'active': True
        }
        
        # Deactivate old key
        old_key['active'] = False
        await keystore.save(old_key['kid'], old_key)
        
        # Save new key
        await keystore.save(new_key['kid'], new_key)
        
        # Verify both keys exist
        assert await keystore.exists(old_key['kid']) is True
        assert await keystore.exists(new_key['kid']) is True
        
        # Load both keys
        loaded_old = await keystore.load(old_key['kid'])
        loaded_new = await keystore.load(new_key['kid'])
        
        assert loaded_old['active'] is False
        assert loaded_new['active'] is True
        
        # Old key can still decrypt old data
        session_key = crypto.generate_session_key()
        wrapped_with_old = crypto.wrap_session_key(session_key, loaded_old['publicKey'])
        unwrapped = crypto.unwrap_session_key(wrapped_with_old, loaded_old['privateKey'])
        assert session_key == unwrapped
        
        await keystore.close()
    
    @pytest.mark.asyncio
    async def test_multiple_active_keys(self, temp_dir):
        """Test scenario with multiple keys for multi-server deployment"""
        keystore = create_keystore('filesystem', {'key_store_path': temp_dir})
        await keystore.initialize()
        
        crypto = CryptoUtils()
        
        # Create 3 keys (simulating 3 servers)
        keys = []
        for i in range(3):
            kp = crypto.generate_server_key_pair()
            key_data = {
                'kid': kp['kid'],
                'publicKey': kp['publicKey'],
                'privateKey': kp['privateKey'],
                'createdAt': 1699999999999 + i,
                'active': True
            }
            keys.append(key_data)
            await keystore.save(key_data['kid'], key_data)
        
        # Verify all keys stored
        all_keys = await keystore.load_all()
        assert len(all_keys) == 3
        
        # Each key should work independently
        session_key = crypto.generate_session_key()
        for key_data in keys:
            loaded = await keystore.load(key_data['kid'])
            wrapped = crypto.wrap_session_key(session_key, loaded['publicKey'])
            unwrapped = crypto.unwrap_session_key(wrapped, loaded['privateKey'])
            assert session_key == unwrapped
        
        await keystore.close()
