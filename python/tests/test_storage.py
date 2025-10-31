"""
Unit tests for storage backends
"""

import pytest
import asyncio
import tempfile
import os
from pathlib import Path

from indexedcp.storage import BaseStorage, SQLiteStorage, create_storage


class TestSQLiteStorage:
    """Test suite for SQLiteStorage implementation"""
    
    @pytest.fixture
    async def storage(self):
        """Create a temporary SQLite storage instance"""
        with tempfile.NamedTemporaryFile(delete=False, suffix='.db') as tmp:
            db_path = tmp.name
        
        storage = SQLiteStorage(db_path=db_path)
        await storage.initialize()
        
        yield storage
        
        await storage.close()
        
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
    
    @pytest.mark.asyncio
    async def test_initialize(self, storage):
        """Test storage initialization"""
        assert storage.connection is not None
        
        # Verify table was created (using asyncio.to_thread for sync connection)
        def _check_table():
            cursor = storage.connection.execute(
                "SELECT name FROM sqlite_master WHERE type='table' AND name=?",
                (storage.table_name,)
            )
            return cursor.fetchone()
        
        result = await asyncio.to_thread(_check_table)
        assert result is not None
    
    @pytest.mark.asyncio
    async def test_save_and_load(self, storage):
        """Test saving and loading data"""
        test_data = {
            'id': 'test-123',
            'value': 'hello world',
            'count': 42
        }
        
        await storage.save('test-key', test_data)
        loaded_data = await storage.load('test-key')
        
        assert loaded_data is not None
        assert loaded_data['id'] == test_data['id']
        assert loaded_data['value'] == test_data['value']
        assert loaded_data['count'] == test_data['count']
    
    @pytest.mark.asyncio
    async def test_load_nonexistent(self, storage):
        """Test loading non-existent key returns None"""
        result = await storage.load('nonexistent-key')
        assert result is None
    
    @pytest.mark.asyncio
    async def test_update_existing(self, storage):
        """Test updating existing data"""
        await storage.save('update-key', {'version': 1})
        await storage.save('update-key', {'version': 2})
        
        loaded = await storage.load('update-key')
        assert loaded['version'] == 2
    
    @pytest.mark.asyncio
    async def test_delete(self, storage):
        """Test deleting data"""
        await storage.save('delete-key', {'data': 'test'})
        
        # Verify it exists
        assert await storage.exists('delete-key')
        
        # Delete it
        deleted = await storage.delete('delete-key')
        assert deleted is True
        
        # Verify it's gone
        assert not await storage.exists('delete-key')
        assert await storage.load('delete-key') is None
    
    @pytest.mark.asyncio
    async def test_delete_nonexistent(self, storage):
        """Test deleting non-existent key returns False"""
        deleted = await storage.delete('nonexistent-key')
        assert deleted is False
    
    @pytest.mark.asyncio
    async def test_exists(self, storage):
        """Test checking key existence"""
        assert not await storage.exists('test-key')
        
        await storage.save('test-key', {'data': 'test'})
        assert await storage.exists('test-key')
    
    @pytest.mark.asyncio
    async def test_list(self, storage):
        """Test listing all keys"""
        # Initially empty
        keys = await storage.list()
        assert len(keys) == 0
        
        # Add some keys
        await storage.save('key1', {'data': '1'})
        await storage.save('key2', {'data': '2'})
        await storage.save('key3', {'data': '3'})
        
        keys = await storage.list()
        assert len(keys) == 3
        assert 'key1' in keys
        assert 'key2' in keys
        assert 'key3' in keys
    
    @pytest.mark.asyncio
    async def test_load_all(self, storage):
        """Test loading all data"""
        # Add some test data
        await storage.save('item1', {'name': 'first', 'value': 1})
        await storage.save('item2', {'name': 'second', 'value': 2})
        await storage.save('item3', {'name': 'third', 'value': 3})
        
        all_data = await storage.load_all()
        assert len(all_data) == 3
        
        # Check that all items are present
        names = [item['name'] for item in all_data]
        assert 'first' in names
        assert 'second' in names
        assert 'third' in names
    
    @pytest.mark.asyncio
    async def test_context_manager(self):
        """Test using storage as async context manager"""
        with tempfile.NamedTemporaryFile(delete=False, suffix='.db') as tmp:
            db_path = tmp.name
        
        try:
            async with SQLiteStorage(db_path=db_path) as storage:
                await storage.save('test', {'data': 'value'})
                loaded = await storage.load('test')
                assert loaded['data'] == 'value'
            
            # Storage should be closed after context
            # Connection should be None
            assert storage.connection is None
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
    async def test_count(self, storage):
        """Test counting stored items"""
        assert await storage.count() == 0
        
        await storage.save('item1', {'data': '1'})
        assert await storage.count() == 1
        
        await storage.save('item2', {'data': '2'})
        assert await storage.count() == 2
        
        await storage.delete('item1')
        assert await storage.count() == 1
    
    @pytest.mark.asyncio
    async def test_cleanup_old(self, storage):
        """Test cleaning up old entries"""
        import time
        
        # Add some data
        await storage.save('old1', {'data': 'old'})
        await storage.save('old2', {'data': 'old'})
        
        # Wait a bit
        await asyncio.sleep(0.1)
        
        # Add new data
        await storage.save('new', {'data': 'new'})
        
        # Cleanup entries older than 0.05 seconds
        deleted = await storage.cleanup_old(0.05)
        assert deleted == 2
        
        # Only 'new' should remain
        keys = await storage.list()
        assert len(keys) == 1
        assert 'new' in keys
    
    @pytest.mark.asyncio
    async def test_multiple_tables(self):
        """Test using different table names"""
        with tempfile.NamedTemporaryFile(delete=False, suffix='.db') as tmp:
            db_path = tmp.name
        
        try:
            storage1 = SQLiteStorage(db_path=db_path, table_name='table1')
            storage2 = SQLiteStorage(db_path=db_path, table_name='table2')
            
            await storage1.initialize()
            await storage2.initialize()
            
            # Save to different tables
            await storage1.save('key', {'table': '1'})
            await storage2.save('key', {'table': '2'})
            
            # Load from different tables
            data1 = await storage1.load('key')
            data2 = await storage2.load('key')
            
            assert data1['table'] == '1'
            assert data2['table'] == '2'
            
            await storage1.close()
            await storage2.close()
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
    async def test_complex_data_types(self, storage):
        """Test storing complex nested data structures"""
        complex_data = {
            'nested': {
                'level1': {
                    'level2': {
                        'value': 'deep'
                    }
                }
            },
            'list': [1, 2, 3, 4, 5],
            'mixed': [
                {'id': 1, 'name': 'first'},
                {'id': 2, 'name': 'second'}
            ],
            'boolean': True,
            'null': None
        }
        
        await storage.save('complex', complex_data)
        loaded = await storage.load('complex')
        
        assert loaded['nested']['level1']['level2']['value'] == 'deep'
        assert loaded['list'] == [1, 2, 3, 4, 5]
        assert len(loaded['mixed']) == 2
        assert loaded['boolean'] is True
        assert loaded['null'] is None


class TestCreateStorage:
    """Test suite for storage factory function"""
    
    @pytest.mark.asyncio
    async def test_create_sqlite_storage(self):
        """Test creating SQLite storage via factory"""
        with tempfile.NamedTemporaryFile(delete=False, suffix='.db') as tmp:
            db_path = tmp.name
        
        try:
            storage = create_storage('sqlite', db_path=db_path)
            assert isinstance(storage, SQLiteStorage)
            
            await storage.initialize()
            await storage.save('test', {'data': 'value'})
            loaded = await storage.load('test')
            assert loaded['data'] == 'value'
            
            await storage.close()
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
    
    def test_create_invalid_storage(self):
        """Test creating storage with invalid type raises error"""
        with pytest.raises(ValueError) as exc_info:
            create_storage('invalid-type')
        
        assert 'Unknown storage type' in str(exc_info.value)


class TestBaseStorageInterface:
    """Test that BaseStorage defines correct abstract interface"""
    
    def test_base_storage_is_abstract(self):
        """Test that BaseStorage cannot be instantiated directly"""
        with pytest.raises(TypeError):
            BaseStorage()
    
    def test_required_methods_exist(self):
        """Test that BaseStorage defines all required abstract methods"""
        required_methods = [
            'initialize',
            'save',
            'load',
            'load_all',
            'delete',
            'exists',
            'list',
            'close'
        ]
        
        for method_name in required_methods:
            assert hasattr(BaseStorage, method_name)
            method = getattr(BaseStorage, method_name)
            assert getattr(method, '__isabstractmethod__', False)
