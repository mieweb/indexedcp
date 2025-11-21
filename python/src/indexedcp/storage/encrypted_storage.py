"""
Encrypted storage implementation for IndexedCP

Enhanced IndexedDB-compatible storage with encryption support

Schema:
- sessions: { sessionId, kid, wrappedKey, createdAt }
- packets: { id, sessionId, seq, iv, aad, ciphertext, authTag, status }
- keyCache: { kid, publicKey, fetchedAt, expiresAt }
"""

import json
import os
import asyncio
from pathlib import Path
from typing import Any, Dict, List, Optional

from .base_storage import BaseStorage
from ..logger import create_logger


class EncryptedStorage(BaseStorage):
    """
    JSON file-based encrypted storage matching JavaScript implementation.
    
    Stores:
    - sessions.json: Session metadata and wrapped keys
    - packets.json: Encrypted data packets
    - key-cache.json: Cached server public keys
    """
    
    def __init__(self, db_name: str = 'indexedcp-encrypted', version: int = 1, **options):
        """
        Initialize encrypted storage.
        
        Args:
            db_name: Database name (not used, for compatibility)
            version: Database version (not used, for compatibility)
            **options: Additional options:
                - db_path: Custom storage directory path (for testing)
                - log_level: Logging level
        """
        super().__init__(**options)
        self.db_name = db_name
        self.version = version
        
        # Storage paths - match JavaScript exactly (default to home directory)
        # Allow override via options for testing
        custom_path = options.get('db_path')
        if custom_path:
            self.db_path = Path(custom_path)
        else:
            self.db_path = Path.home() / '.indexcp' / 'encrypted-db'
        
        self.sessions_path = self.db_path / 'sessions.json'
        self.packets_path = self.db_path / 'packets.json'
        self.key_cache_path = self.db_path / 'key-cache.json'
        
        # Logger configuration
        log_level = options.get('log_level', os.environ.get('INDEXEDCP_LOG_LEVEL', 'INFO'))
        self.logger = create_logger('IndexedCP.EncryptedDB', level=log_level)
    
    def _ensure_db_dir(self):
        """Create storage directory if it doesn't exist."""
        self.db_path.mkdir(parents=True, exist_ok=True)
    
    def _load_store(self, store_name: str) -> List[Dict[str, Any]]:
        """
        Load records from JSON file.
        
        Args:
            store_name: Store name ('sessions', 'packets', or 'keyCache')
        
        Returns:
            List of records
        """
        store_path = self._get_store_path(store_name)
        
        try:
            if store_path.exists():
                with open(store_path, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    return data if isinstance(data, list) else []
        except Exception as error:
            self.logger.warning(f"Failed to load store {store_name}: {error}")
        
        return []
    
    def _save_store(self, store_name: str, records: List[Dict[str, Any]]):
        """
        Save records to JSON file.
        
        Args:
            store_name: Store name ('sessions', 'packets', or 'keyCache')
            records: List of records to save
        """
        store_path = self._get_store_path(store_name)
        
        try:
            if len(records) == 0:
                # Delete the file if there are no records
                if store_path.exists():
                    store_path.unlink()
            else:
                with open(store_path, 'w', encoding='utf-8') as f:
                    json.dump(records, f, indent=2)
        except Exception as error:
            self.logger.error(f"Failed to save store {store_name}: {error}")
            raise
    
    def _get_store_path(self, store_name: str) -> Path:
        """Get file path for store."""
        if store_name == 'sessions':
            return self.sessions_path
        elif store_name == 'packets':
            return self.packets_path
        elif store_name == 'keyCache':
            return self.key_cache_path
        else:
            raise ValueError(f"Unknown store: {store_name}")
    
    def _get_key_path(self, store_name: str) -> str:
        """Get primary key field name for store."""
        if store_name == 'sessions':
            return 'sessionId'
        elif store_name == 'packets':
            return 'id'
        elif store_name == 'keyCache':
            return 'kid'
        else:
            return 'id'
    
    async def initialize(self) -> None:
        """Initialize encrypted storage (create directory)."""
        def _init():
            self._ensure_db_dir()
        
        try:
            await asyncio.to_thread(_init)
            self.logger.info(f"[OK] Encrypted storage initialized: {self.db_path}")
        except Exception as error:
            self.logger.error(f"Failed to initialize encrypted storage: {error}")
            raise
    
    # ============================================================================
    # Core CRUD Operations (matching JavaScript API)
    # ============================================================================
    
    async def add(self, store_name: str, record: Dict[str, Any]) -> Dict[str, Any]:
        """
        Add record to store.
        
        Args:
            store_name: Store name
            record: Record to add
        
        Returns:
            Added record
        """
        def _add():
            records = self._load_store(store_name)
            
            # Auto-generate ID if not present
            if 'id' not in record and store_name == 'packets':
                record['id'] = f"{record['sessionId']}-{record['seq']}"
            
            records.append(record)
            self._save_store(store_name, records)
            return record
        
        try:
            result = await asyncio.to_thread(_add)
            self.logger.debug(f"[OK] Added to {store_name}: {record.get('id', record.get('sessionId', 'N/A'))}")
            return result
        except Exception as error:
            self.logger.error(f"Failed to add to {store_name}: {error}")
            raise
    
    async def put(self, store_name: str, record: Dict[str, Any]) -> Dict[str, Any]:
        """
        Put (insert or update) record in store.
        
        Args:
            store_name: Store name
            record: Record to put
        
        Returns:
            Saved record
        """
        def _put():
            records = self._load_store(store_name)
            key_path = self._get_key_path(store_name)
            key_value = record.get(key_path)
            
            # Find and replace existing record or add new
            index = next((i for i, r in enumerate(records) if r.get(key_path) == key_value), -1)
            
            if index >= 0:
                records[index] = record
            else:
                records.append(record)
            
            self._save_store(store_name, records)
            return record
        
        try:
            result = await asyncio.to_thread(_put)
            self.logger.debug(f"[OK] Put to {store_name}: {record.get(self._get_key_path(store_name))}")
            return result
        except Exception as error:
            self.logger.error(f"Failed to put to {store_name}: {error}")
            raise
    
    async def get(self, store_name: str, key: Any) -> Optional[Dict[str, Any]]:
        """
        Get record by key.
        
        Args:
            store_name: Store name
            key: Primary key value
        
        Returns:
            Record or None if not found
        """
        def _get():
            records = self._load_store(store_name)
            key_path = self._get_key_path(store_name)
            return next((r for r in records if r.get(key_path) == key), None)
        
        try:
            return await asyncio.to_thread(_get)
        except Exception as error:
            self.logger.error(f"Failed to get from {store_name}: {error}")
            raise
    
    async def delete(self, store_name: str, key: Any) -> bool:
        """
        Delete record by key.
        
        Args:
            store_name: Store name
            key: Primary key value
        
        Returns:
            True if deleted
        """
        def _delete():
            records = self._load_store(store_name)
            key_path = self._get_key_path(store_name)
            filtered_records = [r for r in records if r.get(key_path) != key]
            self._save_store(store_name, filtered_records)
            return True
        
        try:
            result = await asyncio.to_thread(_delete)
            self.logger.debug(f"[OK] Deleted from {store_name}: {key}")
            return result
        except Exception as error:
            self.logger.error(f"Failed to delete from {store_name}: {error}")
            raise
    
    async def get_all(self, store_name: str) -> List[Dict[str, Any]]:
        """
        Get all records from store.
        
        Args:
            store_name: Store name
        
        Returns:
            List of all records
        """
        def _get_all():
            return self._load_store(store_name)
        
        try:
            return await asyncio.to_thread(_get_all)
        except Exception as error:
            self.logger.error(f"Failed to get all from {store_name}: {error}")
            raise
    
    async def get_all_from_index(
        self, 
        store_name: str, 
        index_name: str, 
        value: Any
    ) -> List[Dict[str, Any]]:
        """
        Get all records matching index value.
        
        Args:
            store_name: Store name
            index_name: Index field name
            value: Value to match
        
        Returns:
            List of matching records
        """
        def _get_filtered():
            records = self._load_store(store_name)
            return [r for r in records if r.get(index_name) == value]
        
        try:
            return await asyncio.to_thread(_get_filtered)
        except Exception as error:
            self.logger.error(f"Failed to get from index {index_name}: {error}")
            raise
    
    # ============================================================================
    # Session Methods
    # ============================================================================
    
    async def save_session(self, session_data: Dict[str, Any]) -> None:
        """
        Save session metadata.
        
        Args:
            session_data: Session data with sessionId, kid, wrappedKey, fileName, createdAt
        """
        await self.put('sessions', session_data)
        self.logger.debug(f"🔐 Saved session: {session_data['sessionId']}")
    
    async def get_session(self, session_id: str) -> Optional[Dict[str, Any]]:
        """
        Get session by ID.
        
        Args:
            session_id: Session identifier
        
        Returns:
            Session data or None if not found
        """
        return await self.get('sessions', session_id)
    
    async def get_all_sessions(self) -> List[Dict[str, Any]]:
        """Get all sessions."""
        return await self.get_all('sessions')
    
    # ============================================================================
    # Packet Methods
    # ============================================================================
    
    async def save_packet(self, packet_data: Dict[str, Any]) -> None:
        """
        Save encrypted packet.
        
        Args:
            packet_data: Packet data with id, sessionId, seq, ciphertext, iv, authTag, aad, status, createdAt
        """
        await self.add('packets', packet_data)
        self.logger.debug(f"🔐 Saved packet: {packet_data['id']}")
    
    async def get_packets_by_session(
        self, 
        session_id: str, 
        status: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """
        Get all packets for a session.
        
        Args:
            session_id: Session identifier
            status: Filter by status (optional)
        
        Returns:
            List of packet data dictionaries ordered by sequence
        """
        packets = await self.get_all_from_index('packets', 'sessionId', session_id)
        
        if status:
            packets = [p for p in packets if p.get('status') == status]
        
        # Sort by sequence number
        packets.sort(key=lambda p: p.get('seq', 0))
        return packets
    
    async def get_all_pending_packets(self) -> List[Dict[str, Any]]:
        """Get all pending packets."""
        return await self.get_pending_packets()
    
    async def get_pending_packets(self) -> List[Dict[str, Any]]:
        """
        Get pending packets for upload.
        
        Returns:
            List of packets with status='pending'
        """
        def _get_pending():
            packets = self._load_store('packets')
            return [p for p in packets if p.get('status') == 'pending']
        
        try:
            return await asyncio.to_thread(_get_pending)
        except Exception as error:
            self.logger.error(f"Failed to get pending packets: {error}")
            raise
    
    async def update_packet_status(self, packet_id: str, status: str) -> None:
        """
        Update packet status.
        
        Args:
            packet_id: Packet identifier
            status: New status (e.g., 'uploaded', 'failed')
        """
        def _update():
            packets = self._load_store('packets')
            packet = next((p for p in packets if p.get('id') == packet_id), None)
            if packet:
                packet['status'] = status
                self._save_store('packets', packets)
        
        try:
            await asyncio.to_thread(_update)
            self.logger.debug(f"Updated packet {packet_id} status: {status}")
        except Exception as error:
            self.logger.error(f"Failed to update packet status: {error}")
            raise
    
    # ============================================================================
    # Key Cache Methods
    # ============================================================================
    
    async def save_public_key(self, key_data: Dict[str, Any]) -> None:
        """
        Save public key to cache.
        
        Args:
            key_data: Key data with kid, publicKey, fetchedAt, expiresAt
        """
        await self.put('keyCache', key_data)
        self.logger.debug(f"🔑 Cached public key: {key_data['kid']}")
    
    async def get_cached_public_key(self) -> Optional[Dict[str, Any]]:
        """
        Get most recent non-expired public key.
        
        Returns:
            Key data or None if no valid key found
        """
        def _get():
            import time
            now = time.time() * 1000  # Milliseconds
            
            keys = self._load_store('keyCache')
            # Filter non-expired keys
            valid_keys = [k for k in keys if k.get('expiresAt', 0) > now]
            
            if not valid_keys:
                return None
            
            # Sort by fetchedAt descending and return most recent
            valid_keys.sort(key=lambda k: k.get('fetchedAt', 0), reverse=True)
            return valid_keys[0]
        
        try:
            return await asyncio.to_thread(_get)
        except Exception as error:
            self.logger.error(f"Failed to get cached public key: {error}")
            raise
    
    # ============================================================================
    # Cleanup Methods
    # ============================================================================
    
    async def cleanup_session(self, session_id: str) -> None:
        """
        Cleanup old packets by session ID.
        
        Args:
            session_id: Session identifier to cleanup
        """
        def _cleanup():
            # Remove packets
            packets = self._load_store('packets')
            filtered_packets = [p for p in packets if p.get('sessionId') != session_id]
            self._save_store('packets', filtered_packets)
            
            # Remove session
            sessions = self._load_store('sessions')
            filtered_sessions = [s for s in sessions if s.get('sessionId') != session_id]
            self._save_store('sessions', filtered_sessions)
        
        try:
            await asyncio.to_thread(_cleanup)
            self.logger.debug(f"🗑️  Cleaned up session: {session_id}")
        except Exception as error:
            self.logger.error(f"Failed to cleanup session: {error}")
            raise
    
    # ============================================================================
    # BaseStorage Interface (for backward compatibility)
    # ============================================================================
    
    async def save(self, key: str, data: Dict[str, Any]) -> None:
        """Save data (delegates to appropriate store based on key prefix)."""
        if key.startswith('session-'):
            await self.save_session(data)
        elif key.startswith('packet-'):
            await self.save_packet(data)
        elif key.startswith('key-'):
            await self.save_public_key(data)
        else:
            raise ValueError(f"Unknown key prefix for encrypted storage: {key}")
    
    async def load(self, key: str) -> Optional[Dict[str, Any]]:
        """Load data (delegates to appropriate store based on key prefix)."""
        if key.startswith('session-'):
            session_id = key.replace('session-', '')
            return await self.get_session(session_id)
        elif key.startswith('key-'):
            return await self.get_cached_public_key()
        else:
            raise ValueError(f"Unknown key prefix for encrypted storage: {key}")
    
    async def load_all(self) -> List[Dict[str, Any]]:
        """Load all pending packets (for upload processing)."""
        return await self.get_all_pending_packets()
    
    async def exists(self, key: str) -> bool:
        """Check if data exists."""
        data = await self.load(key)
        return data is not None
    
    async def list(self) -> List[str]:
        """List all packet IDs (for compatibility)."""
        def _list():
            packets = self._load_store('packets')
            return [p['id'] for p in packets if p.get('status') == 'pending']
        
        try:
            return await asyncio.to_thread(_list)
        except Exception as error:
            self.logger.error(f"Failed to list packets: {error}")
            raise
    
    async def count(self) -> int:
        """Count all records (pending packets)."""
        packets = await self.get_all_pending_packets()
        return len(packets)
    
    async def clear(self) -> None:
        """Clear all data."""
        def _clear():
            self._save_store('packets', [])
            self._save_store('sessions', [])
            self._save_store('keyCache', [])
        
        try:
            await asyncio.to_thread(_clear)
            self.logger.info("🗑️  Cleared all encrypted storage")
        except Exception as error:
            self.logger.error(f"Failed to clear storage: {error}")
            raise
    
    async def close(self) -> None:
        """Close storage connection (no-op for JSON files)."""
        self.logger.info("[OK] Encrypted storage closed")


def open_encrypted_db(db_name: str, version: int, options: Optional[Dict[str, Any]] = None) -> EncryptedStorage:
    """
    Factory function to create EncryptedStorage instance (matches JavaScript API).
    
    Args:
        db_name: Database name
        version: Database version
        options: Optional configuration
    
    Returns:
        EncryptedStorage instance
    """
    storage = EncryptedStorage(db_name, version, **(options or {}))
    return storage
