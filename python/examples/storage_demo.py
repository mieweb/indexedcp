"""
Storage Demo - Demonstrates the storage abstraction layer

Shows how to use the SQLite storage backend for persistent key-value storage.
"""

import asyncio
import sys
import os

# Add parent directory to path for imports
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

from indexedcp import create_storage, create_logger


async def basic_usage_demo():
    """Demonstrate basic storage operations"""
    logger = create_logger("StorageDemo.Basic", level="INFO")
    logger.info("=== Basic Storage Usage Demo ===\n")
    
    # Create storage instance
    storage = create_storage('sqlite', db_path='./demo.db')
    await storage.initialize()
    
    try:
        # Save data
        logger.info("1. Saving user data...")
        await storage.save('user:alice', {
            'name': 'Alice Johnson',
            'email': 'alice@example.com',
            'age': 28,
            'role': 'developer'
        })
        
        await storage.save('user:bob', {
            'name': 'Bob Smith',
            'email': 'bob@example.com',
            'age': 35,
            'role': 'manager'
        })
        
        await storage.save('config:app', {
            'theme': 'dark',
            'language': 'en',
            'notifications': True
        })
        
        logger.info("✓ Saved 3 items\n")
        
        # Load data
        logger.info("2. Loading user data...")
        alice = await storage.load('user:alice')
        logger.info(f"   Alice: {alice['name']}, {alice['role']}")
        
        bob = await storage.load('user:bob')
        logger.info(f"   Bob: {bob['name']}, {bob['role']}\n")
        
        # Check existence
        logger.info("3. Checking existence...")
        exists = await storage.exists('user:alice')
        logger.info(f"   user:alice exists: {exists}")
        
        exists = await storage.exists('user:charlie')
        logger.info(f"   user:charlie exists: {exists}\n")
        
        # List all keys
        logger.info("4. Listing all keys...")
        keys = await storage.list()
        logger.info(f"   Found {len(keys)} keys: {keys}\n")
        
        # Load all data
        logger.info("5. Loading all data...")
        all_data = await storage.load_all()
        logger.info(f"   Total items: {len(all_data)}")
        for item in all_data:
            if 'name' in item:
                logger.info(f"   - {item['name']}")
            elif 'theme' in item:
                logger.info(f"   - Config: theme={item['theme']}")
        
        logger.info("")
        
        # Update data
        logger.info("6. Updating data...")
        alice['age'] = 29
        alice['role'] = 'senior developer'
        await storage.save('user:alice', alice)
        
        updated = await storage.load('user:alice')
        logger.info(f"   Updated Alice: age={updated['age']}, role={updated['role']}\n")
        
        # Delete data
        logger.info("7. Deleting data...")
        deleted = await storage.delete('config:app')
        logger.info(f"   Deleted config:app: {deleted}")
        
        remaining = await storage.list()
        logger.info(f"   Remaining keys: {remaining}\n")
        
    finally:
        await storage.close()
        logger.info("✓ Storage closed")


async def context_manager_demo():
    """Demonstrate using storage as context manager"""
    logger = create_logger("StorageDemo.Context", level="INFO")
    logger.info("\n=== Context Manager Demo ===\n")
    
    logger.info("Using async context manager for automatic cleanup...")
    
    async with create_storage('sqlite', db_path='./demo_context.db') as storage:
        await storage.save('temp:data', {'value': 'temporary'})
        data = await storage.load('temp:data')
        logger.info(f"Loaded data: {data}")
    
    logger.info("✓ Storage automatically closed after context\n")


async def advanced_features_demo():
    """Demonstrate advanced storage features"""
    logger = create_logger("StorageDemo.Advanced", level="INFO")
    logger.info("=== Advanced Features Demo ===\n")
    
    from indexedcp.storage import SQLiteStorage
    
    storage = SQLiteStorage(db_path='./demo_advanced.db', table_name='advanced_storage')
    await storage.initialize()
    
    try:
        # Add multiple items
        logger.info("1. Adding multiple items...")
        for i in range(10):
            await storage.save(f'item:{i}', {
                'id': i,
                'name': f'Item {i}',
                'timestamp': i * 1000
            })
        
        logger.info(f"✓ Added 10 items\n")
        
        # Count items
        logger.info("2. Counting items...")
        count = await storage.count()
        logger.info(f"   Total items in storage: {count}\n")
        
        # Complex nested data
        logger.info("3. Storing complex nested data...")
        complex_data = {
            'metadata': {
                'version': '1.0',
                'author': {
                    'name': 'Developer',
                    'email': 'dev@example.com'
                }
            },
            'items': [
                {'id': 1, 'value': 'first'},
                {'id': 2, 'value': 'second'}
            ],
            'flags': {
                'enabled': True,
                'debug': False
            }
        }
        
        await storage.save('complex:data', complex_data)
        loaded = await storage.load('complex:data')
        logger.info(f"   Version: {loaded['metadata']['version']}")
        logger.info(f"   Author: {loaded['metadata']['author']['name']}")
        logger.info(f"   Items count: {len(loaded['items'])}\n")
        
        # Cleanup old entries
        logger.info("4. Cleanup demonstration...")
        logger.info("   (Waiting to create age difference...)")
        await asyncio.sleep(0.2)
        
        # Add new item
        await storage.save('item:new', {'id': 999, 'name': 'New Item'})
        
        # Cleanup items older than 0.1 seconds
        deleted = await storage.cleanup_old(0.1)
        logger.info(f"   Cleaned up {deleted} old entries")
        
        remaining = await storage.count()
        logger.info(f"   Remaining items: {remaining}\n")
        
    finally:
        await storage.close()
        logger.info("✓ Storage closed")


async def error_handling_demo():
    """Demonstrate error handling"""
    logger = create_logger("StorageDemo.Errors", level="INFO")
    logger.info("=== Error Handling Demo ===\n")
    
    storage = create_storage('sqlite', db_path='./demo_errors.db')
    await storage.initialize()
    
    try:
        # Loading non-existent key
        logger.info("1. Loading non-existent key...")
        result = await storage.load('nonexistent:key')
        logger.info(f"   Result: {result}")
        logger.info("   (Returns None, not an error)\n")
        
        # Deleting non-existent key
        logger.info("2. Deleting non-existent key...")
        deleted = await storage.delete('nonexistent:key')
        logger.info(f"   Deleted: {deleted}")
        logger.info("   (Returns False, not an error)\n")
        
        # Using storage before initialization (should fail)
        logger.info("3. Testing uninitialized storage...")
        uninitialized = create_storage('sqlite', db_path='./uninitialized.db')
        try:
            await uninitialized.save('key', {'data': 'value'})
        except RuntimeError as e:
            logger.info(f"   ✓ Caught expected error: {e}\n")
        
    finally:
        await storage.close()


async def main():
    """Run all demos"""
    try:
        await basic_usage_demo()
        await context_manager_demo()
        await advanced_features_demo()
        await error_handling_demo()
        
        logger = create_logger("StorageDemo", level="INFO")
        logger.info("\n" + "="*50)
        logger.info(" All demos completed successfully!")
        logger.info("="*50 + "\n")
        
        # Cleanup demo databases
        logger.info("Cleaning up demo databases...")
        for db_file in ['demo.db', 'demo_context.db', 'demo_advanced.db', 'demo_errors.db']:
            if os.path.exists(db_file):
                os.remove(db_file)
                # Also remove WAL and SHM files
                for ext in ['-wal', '-shm']:
                    wal_file = db_file + ext
                    if os.path.exists(wal_file):
                        os.remove(wal_file)
        logger.info("✓ Cleanup complete\n")
        
    except Exception as e:
        logger = create_logger("StorageDemo", level="ERROR")
        logger.error(f"Demo failed: {e}")
        raise


if __name__ == '__main__':
    asyncio.run(main())
