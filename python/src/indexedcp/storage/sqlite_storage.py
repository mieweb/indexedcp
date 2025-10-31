"""
SQLite storage implementation for IndexedCP

Thread-safe SQLite-backed storage using Python's built-in sqlite3 module.
"""

import sqlite3
import json
import os
import asyncio
from pathlib import Path
from typing import Any, Dict, List, Optional

from .base_storage import BaseStorage
from ..logger import create_logger


class SQLiteStorage(BaseStorage):
    """
    SQLite-based storage implementation.
    
    Provides persistent, ACID-compliant storage using Python's built-in sqlite3.
    Thread-safe with proper connection management using asyncio.to_thread().
    """
    
    def __init__(self, db_path: str = './indexedcp.db', table_name: str = 'storage', **options):
        """
        Initialize SQLite storage.
        
        Args:
            db_path: Path to SQLite database file
            table_name: Name of the table to use for storage
            **options: Additional options (e.g., log_level)
        """
        super().__init__(**options)
        self.db_path = db_path
        self.table_name = table_name
        self.connection: Optional[sqlite3.Connection] = None
        
        # Logger configuration
        log_level = options.get('log_level', os.environ.get('INDEXEDCP_LOG_LEVEL', 'INFO'))
        self.logger = create_logger(f'IndexedCP.SQLiteStorage', level=log_level)
    
    async def initialize(self) -> None:
        """
        Initialize SQLite database and create table if needed.
        
        Creates the database file and table structure.
        Sets up proper indexes for efficient queries.
        """
        def _init():
            # Create directory if it doesn't exist
            db_dir = Path(self.db_path).parent
            if db_dir != Path('.'):
                db_dir.mkdir(parents=True, exist_ok=True)
            
            # Connect to database
            conn = sqlite3.connect(self.db_path, check_same_thread=False)
            
            # Enable WAL mode for better concurrency
            conn.execute('PRAGMA journal_mode=WAL')
            
            # Create table with proper schema
            conn.execute(f'''
                CREATE TABLE IF NOT EXISTS {self.table_name} (
                    key TEXT PRIMARY KEY,
                    data TEXT NOT NULL,
                    created_at REAL NOT NULL,
                    updated_at REAL NOT NULL
                )
            ''')
            
            # Create index on created_at for efficient time-based queries
            conn.execute(f'''
                CREATE INDEX IF NOT EXISTS idx_{self.table_name}_created_at
                ON {self.table_name}(created_at)
            ''')
            
            conn.commit()
            return conn
        
        try:
            self.connection = await asyncio.to_thread(_init)
            self.logger.info(f"✓ SQLite storage initialized: {self.db_path}")
        except Exception as error:
            self.logger.error(f"Failed to initialize SQLite storage: {error}")
            raise
    
    async def save(self, key: str, data: Dict[str, Any]) -> None:
        """
        Save data to SQLite database.
        
        Uses REPLACE to handle both insert and update operations.
        
        Args:
            key: Unique identifier for the data
            data: Dictionary containing data to store
        """
        if not self.connection:
            raise RuntimeError("Storage not initialized. Call initialize() first.")
        
        def _save():
            import time
            current_time = time.time()
            
            # Serialize data to JSON
            json_data = json.dumps(data)
            
            # Check if key exists to determine created_at
            cursor = self.connection.execute(
                f'SELECT created_at FROM {self.table_name} WHERE key = ?',
                (key,)
            )
            row = cursor.fetchone()
            created_at = row[0] if row else current_time
            
            # REPLACE operation (insert or update)
            self.connection.execute(
                f'''
                REPLACE INTO {self.table_name} (key, data, created_at, updated_at)
                VALUES (?, ?, ?, ?)
                ''',
                (key, json_data, created_at, current_time)
            )
            
            self.connection.commit()
        
        try:
            await asyncio.to_thread(_save)
            self.logger.debug(f"🔑 Saved to SQLite: {key}")
        except Exception as error:
            self.logger.error(f"Failed to save key {key}: {error}")
            raise
    
    async def load(self, key: str) -> Optional[Dict[str, Any]]:
        """
        Load data from SQLite database by key.
        
        Args:
            key: Unique identifier for the data
        
        Returns:
            Dict containing the stored data, or None if not found
        """
        if not self.connection:
            raise RuntimeError("Storage not initialized. Call initialize() first.")
        
        def _load():
            cursor = self.connection.execute(
                f'SELECT data FROM {self.table_name} WHERE key = ?',
                (key,)
            )
            row = cursor.fetchone()
            
            if row:
                return json.loads(row[0])
            return None
        
        try:
            return await asyncio.to_thread(_load)
        except Exception as error:
            if 'no such table' in str(error):
                return None
            self.logger.error(f"Failed to load key {key}: {error}")
            raise
    
    async def load_all(self) -> List[Dict[str, Any]]:
        """
        Load all data from SQLite database.
        
        Returns:
            List of all stored data dictionaries
        """
        if not self.connection:
            raise RuntimeError("Storage not initialized. Call initialize() first.")
        
        def _load_all():
            cursor = self.connection.execute(
                f'SELECT data FROM {self.table_name} ORDER BY created_at ASC'
            )
            rows = cursor.fetchall()
            
            return [json.loads(row[0]) for row in rows]
        
        try:
            return await asyncio.to_thread(_load_all)
        except Exception as error:
            if 'no such table' in str(error):
                return []
            self.logger.error(f"Failed to load all data: {error}")
            raise
    
    async def delete(self, key: str) -> bool:
        """
        Delete data from SQLite database by key.
        
        Args:
            key: Unique identifier for the data
        
        Returns:
            True if data was deleted, False if key didn't exist
        """
        if not self.connection:
            raise RuntimeError("Storage not initialized. Call initialize() first.")
        
        def _delete():
            cursor = self.connection.execute(
                f'DELETE FROM {self.table_name} WHERE key = ?',
                (key,)
            )
            self.connection.commit()
            
            deleted = cursor.rowcount > 0
            return deleted
        
        try:
            deleted = await asyncio.to_thread(_delete)
            if deleted:
                self.logger.debug(f"🗑️  Deleted from SQLite: {key}")
            return deleted
        except Exception as error:
            self.logger.error(f"Failed to delete key {key}: {error}")
            raise
    
    async def exists(self, key: str) -> bool:
        """
        Check if a key exists in SQLite database.
        
        Args:
            key: Unique identifier to check
        
        Returns:
            True if key exists, False otherwise
        """
        if not self.connection:
            raise RuntimeError("Storage not initialized. Call initialize() first.")
        
        def _exists():
            cursor = self.connection.execute(
                f'SELECT 1 FROM {self.table_name} WHERE key = ? LIMIT 1',
                (key,)
            )
            row = cursor.fetchone()
            return row is not None
        
        try:
            return await asyncio.to_thread(_exists)
        except Exception as error:
            if 'no such table' in str(error):
                return False
            self.logger.error(f"Failed to check existence of key {key}: {error}")
            raise
    
    async def list(self) -> List[str]:
        """
        List all keys in SQLite database.
        
        Returns:
            List of all keys ordered by creation time
        """
        if not self.connection:
            raise RuntimeError("Storage not initialized. Call initialize() first.")
        
        def _list():
            cursor = self.connection.execute(
                f'SELECT key FROM {self.table_name} ORDER BY created_at ASC'
            )
            rows = cursor.fetchall()
            
            return [row[0] for row in rows]
        
        try:
            return await asyncio.to_thread(_list)
        except Exception as error:
            if 'no such table' in str(error):
                return []
            self.logger.error(f"Failed to list keys: {error}")
            raise
    
    async def close(self) -> None:
        """
        Close SQLite database connection.
        
        Ensures proper resource cleanup and commits any pending changes.
        """
        if self.connection:
            def _close():
                self.connection.close()
            
            try:
                await asyncio.to_thread(_close)
                self.logger.info("✓ SQLite storage closed")
            except Exception as error:
                self.logger.error(f"Error closing SQLite connection: {error}")
            finally:
                self.connection = None
    
    async def cleanup_old(self, max_age_seconds: float) -> int:
        """
        Delete entries older than the specified age.
        
        Helper method for maintaining storage by removing old entries.
        
        Args:
            max_age_seconds: Maximum age in seconds
        
        Returns:
            Number of entries deleted
        """
        if not self.connection:
            raise RuntimeError("Storage not initialized. Call initialize() first.")
        
        def _cleanup():
            import time
            cutoff_time = time.time() - max_age_seconds
            
            cursor = self.connection.execute(
                f'DELETE FROM {self.table_name} WHERE created_at < ?',
                (cutoff_time,)
            )
            self.connection.commit()
            
            return cursor.rowcount
        
        try:
            deleted_count = await asyncio.to_thread(_cleanup)
            if deleted_count > 0:
                self.logger.info(f"✓ Cleaned up {deleted_count} old entries")
            
            return deleted_count
        except Exception as error:
            self.logger.error(f"Failed to cleanup old entries: {error}")
            raise
    
    async def count(self) -> int:
        """
        Get total count of stored items.
        
        Returns:
            Number of items in storage
        """
        if not self.connection:
            raise RuntimeError("Storage not initialized. Call initialize() first.")
        
        def _count():
            cursor = self.connection.execute(
                f'SELECT COUNT(*) FROM {self.table_name}'
            )
            row = cursor.fetchone()
            return row[0] if row else 0
        
        try:
            return await asyncio.to_thread(_count)
        except Exception as error:
            if 'no such table' in str(error):
                return 0
            self.logger.error(f"Failed to count items: {error}")
            raise
