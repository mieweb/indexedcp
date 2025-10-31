"""
Storage abstraction layer for IndexedCP

Provides pluggable storage backends for key-value persistence.
"""

from .base_storage import BaseStorage
from .sqlite_storage import SQLiteStorage


def create_storage(storage_type: str = 'sqlite', **options) -> BaseStorage:
    """
    Create a storage instance based on type.
    
    Args:
        storage_type: Type of storage ('sqlite', 'memory')
        **options: Storage-specific configuration options
    
    Returns:
        BaseStorage: Storage instance
    
    Raises:
        ValueError: If storage_type is unknown
    
    Example:
        >>> storage = create_storage('sqlite', db_path='./data.db')
        >>> await storage.initialize()
    """
    storage_type = storage_type.lower()
    
    if storage_type in ('sqlite', 'sql', 'db'):
        return SQLiteStorage(**options)
    else:
        raise ValueError(
            f"Unknown storage type: {storage_type}. "
            f"Valid types: sqlite"
        )


__all__ = [
    'BaseStorage',
    'SQLiteStorage',
    'create_storage'
]
