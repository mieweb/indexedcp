"""
IndexedDB-like interface for Python

This module provides an IndexedDB-compatible API using SQLite as the backend,
making the Python implementation even closer to the JavaScript version.
"""

import os
import json
import sqlite3
import asyncio
from pathlib import Path
from typing import Optional, Dict, Any, List, Callable
from dataclasses import dataclass


@dataclass
class ObjectStore:
    """Represents an IndexedDB object store."""
    name: str
    connection: sqlite3.Connection
    key_path: Optional[str] = None
    auto_increment: bool = False

    def add(self, value: Dict[str, Any]) -> Any:
        """Add a record to the object store."""
        if self.key_path and self.key_path in value:
            key = value[self.key_path]
        elif self.auto_increment:
            # Generate auto-increment key
            cursor = self.connection.execute(
                f"SELECT MAX(rowid) FROM {self.name}"
            )
            max_id = cursor.fetchone()[0]
            key = (max_id or 0) + 1
            if self.key_path:
                value[self.key_path] = key
        else:
            raise ValueError("No key provided and auto_increment is False")

        # Serialize the data
        data_json = json.dumps(value, default=self._serialize_binary)
        
        # Insert into database
        self.connection.execute(
            f"INSERT OR REPLACE INTO {self.name} (key, data) VALUES (?, ?)",
            (str(key), data_json)
        )
        self.connection.commit()
        return value

    def get(self, key: Any) -> Optional[Dict[str, Any]]:
        """Get a record by key."""
        cursor = self.connection.execute(
            f"SELECT data FROM {self.name} WHERE key = ?",
            (str(key),)
        )
        row = cursor.fetchone()
        if row:
            data = json.loads(row[0], object_hook=self._deserialize_binary)
            return data
        return None

    def get_all(self) -> List[Dict[str, Any]]:
        """Get all records from the object store."""
        cursor = self.connection.execute(f"SELECT data FROM {self.name}")
        rows = cursor.fetchall()
        return [json.loads(row[0], object_hook=self._deserialize_binary) for row in rows]

    def delete(self, key: Any) -> bool:
        """Delete a record by key."""
        cursor = self.connection.execute(
            f"DELETE FROM {self.name} WHERE key = ?",
            (str(key),)
        )
        self.connection.commit()
        return cursor.rowcount > 0

    def clear(self) -> None:
        """Clear all records from the object store."""
        self.connection.execute(f"DELETE FROM {self.name}")
        self.connection.commit()

    def _serialize_binary(self, obj):
        """Serialize binary data to base64 for JSON storage."""
        if isinstance(obj, bytes):
            return {
                '__type__': 'bytes',
                '__data__': obj.hex()  # Using hex instead of base64 for efficiency
            }
        raise TypeError(f"Object of type {type(obj)} is not JSON serializable")

    def _deserialize_binary(self, obj):
        """Deserialize binary data from JSON storage."""
        if isinstance(obj, dict) and obj.get('__type__') == 'bytes':
            return bytes.fromhex(obj['__data__'])
        return obj


@dataclass
class Transaction:
    """Represents an IndexedDB transaction."""
    connection: sqlite3.Connection
    store_names: List[str]
    mode: str = 'readonly'

    def object_store(self, name: str) -> ObjectStore:
        """Get an object store from this transaction."""
        if name not in self.store_names:
            raise ValueError(f"Object store '{name}' not in transaction")
        return ObjectStore(name, self.connection)


class IDBDatabase:
    """IndexedDB-like database interface."""
    
    def __init__(self, name: str, version: int, db_path: Path):
        self.name = name
        self.version = version
        self.db_path = db_path
        self.connection: Optional[sqlite3.Connection] = None
        self.object_store_names: List[str] = []

    def _connect(self) -> sqlite3.Connection:
        """Get or create database connection."""
        if not self.connection:
            self.db_path.parent.mkdir(parents=True, exist_ok=True)
            self.connection = sqlite3.connect(str(self.db_path))
            # Enable foreign keys
            self.connection.execute("PRAGMA foreign_keys = ON")
        return self.connection

    def create_object_store(self, name: str, options: Optional[Dict[str, Any]] = None) -> ObjectStore:
        """Create an object store (similar to IndexedDB)."""
        options = options or {}
        key_path = options.get('keyPath')
        auto_increment = options.get('autoIncrement', False)
        
        conn = self._connect()
        
        # Create table for the object store
        conn.execute(f"""
            CREATE TABLE IF NOT EXISTS {name} (
                key TEXT PRIMARY KEY,
                data TEXT NOT NULL
            )
        """)
        conn.commit()
        
        if name not in self.object_store_names:
            self.object_store_names.append(name)
        
        return ObjectStore(name, conn, key_path, auto_increment)

    def transaction(self, store_names: List[str], mode: str = 'readonly') -> Transaction:
        """Create a transaction."""
        if isinstance(store_names, str):
            store_names = [store_names]
        
        conn = self._connect()
        return Transaction(conn, store_names, mode)

    def add(self, store_name: str, value: Dict[str, Any]) -> Any:
        """Convenience method to add to a store."""
        store = ObjectStore(store_name, self._connect())
        return store.add(value)

    def get(self, store_name: str, key: Any) -> Optional[Dict[str, Any]]:
        """Convenience method to get from a store."""
        store = ObjectStore(store_name, self._connect())
        return store.get(key)

    def get_all(self, store_name: str) -> List[Dict[str, Any]]:
        """Convenience method to get all from a store."""
        store = ObjectStore(store_name, self._connect())
        return store.get_all()

    def delete(self, store_name: str, key: Any) -> bool:
        """Convenience method to delete from a store."""
        store = ObjectStore(store_name, self._connect())
        return store.delete(key)

    def close(self):
        """Close the database connection."""
        if self.connection:
            self.connection.close()
            self.connection = None


# Factory function that mimics IndexedDB's openDB
async def open_db(name: str, version: int = 1, upgrade_callback: Optional[Callable] = None) -> IDBDatabase:
    """
    Open an IndexedDB-like database.
    
    Args:
        name: Database name
        version: Database version
        upgrade_callback: Optional upgrade function called with db instance
    
    Returns:
        IDBDatabase instance
    """
    # Simulate async operation (IndexedDB is async)
    await asyncio.sleep(0)
    
    # Create database path
    home_dir = Path.home()
    db_dir = home_dir / ".indexcp"
    db_path = db_dir / f"{name}.db"
    
    # Create database instance
    db = IDBDatabase(name, version, db_path)
    
    # Run upgrade callback if provided
    if upgrade_callback:
        upgrade_callback(db)
    
    return db


# Synchronous version for easier migration
def open_db_sync(name: str, version: int = 1, upgrade_callback: Optional[Callable] = None) -> IDBDatabase:
    """
    Synchronous version of open_db for easier migration from SQLite.
    
    Args:
        name: Database name
        version: Database version
        upgrade_callback: Optional upgrade function called with db instance
    
    Returns:
        IDBDatabase instance
    """
    # Create database path
    home_dir = Path.home()
    db_dir = home_dir / ".indexcp"
    db_path = db_dir / f"{name}.db"
    
    # Create database instance
    db = IDBDatabase(name, version, db_path)
    
    # Run upgrade callback if provided
    if upgrade_callback:
        upgrade_callback(db)
    
    return db


# Export the same interface as the JavaScript idb library
openDB = open_db_sync  # Default to synchronous for easier usage
