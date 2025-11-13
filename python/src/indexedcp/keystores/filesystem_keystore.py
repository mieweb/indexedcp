"""
Filesystem-based KeyStore implementation

Stores keys as JSON files in a directory.
Default implementation - no external dependencies.
"""

import os
import json
import stat
from pathlib import Path
from typing import Optional, Dict, Any, List
import fcntl  # For file locking

from .base_keystore import BaseKeyStore


class FileSystemKeyStore(BaseKeyStore):
    """Filesystem-based keystore that stores keys as JSON files."""
    
    def __init__(self, options: Optional[Dict[str, Any]] = None):
        """
        Initialize filesystem keystore.
        
        Args:
            options: Configuration options
                - key_store_path: Directory for key storage (default: './server-keys')
                - log_level: Logging level
        """
        super().__init__(options)
        options = options or {}
        self.key_store_path = Path(options.get('key_store_path', './server-keys'))
        self.file_extension = '.json'
    
    async def initialize(self) -> None:
        """Initialize the keystore by creating the directory."""
        try:
            self.key_store_path.mkdir(parents=True, exist_ok=True)
            # Set directory permissions to 0700 (owner read/write/execute only)
            os.chmod(self.key_store_path, stat.S_IRWXU)
            self.logger.info(f'✓ Filesystem keystore initialized: {self.key_store_path}')
        except Exception as error:
            self.logger.error(f'Failed to initialize filesystem keystore: {error}')
            raise
    
    async def save(self, kid: str, key_data: Dict[str, Any]) -> None:
        """
        Save a key pair to filesystem.
        
        Args:
            kid: Key ID
            key_data: Key data to store
        
        Raises:
            Exception: If save operation fails
        """
        try:
            key_file = self.key_store_path / f'{kid}{self.file_extension}'
            
            # Write with file locking for thread safety
            with open(key_file, 'w', encoding='utf-8') as f:
                # Acquire exclusive lock
                fcntl.flock(f.fileno(), fcntl.LOCK_EX)
                try:
                    json.dump(key_data, f, indent=2)
                finally:
                    # Release lock
                    fcntl.flock(f.fileno(), fcntl.LOCK_UN)
            
            # Set file permissions to 0600 (owner read/write only)
            os.chmod(key_file, stat.S_IRUSR | stat.S_IWUSR)
            
            self.logger.info(f'🔑 Persisted key to filesystem: {kid}')
        except Exception as error:
            self.logger.error(f'Failed to save key {kid}: {error}')
            raise
    
    async def load(self, kid: str) -> Optional[Dict[str, Any]]:
        """
        Load a specific key by ID.
        
        Args:
            kid: Key ID
        
        Returns:
            Key data or None if not found
        """
        try:
            key_file = self.key_store_path / f'{kid}{self.file_extension}'
            
            if not key_file.exists():
                return None
            
            # Read with file locking
            with open(key_file, 'r', encoding='utf-8') as f:
                # Acquire shared lock
                fcntl.flock(f.fileno(), fcntl.LOCK_SH)
                try:
                    data = json.load(f)
                finally:
                    # Release lock
                    fcntl.flock(f.fileno(), fcntl.LOCK_UN)
            
            return data
        except FileNotFoundError:
            return None
        except Exception as error:
            self.logger.error(f'Failed to load key {kid}: {error}')
            raise
    
    async def load_all(self) -> List[Dict[str, Any]]:
        """
        Load all keys from filesystem.
        
        Returns:
            List of key data dictionaries
        """
        try:
            # Ensure directory exists
            self.key_store_path.mkdir(parents=True, exist_ok=True)
            
            keys = []
            for file_path in self.key_store_path.glob(f'*{self.file_extension}'):
                try:
                    with open(file_path, 'r', encoding='utf-8') as f:
                        # Acquire shared lock
                        fcntl.flock(f.fileno(), fcntl.LOCK_SH)
                        try:
                            data = json.load(f)
                            keys.append(data)
                        finally:
                            # Release lock
                            fcntl.flock(f.fileno(), fcntl.LOCK_UN)
                except Exception as error:
                    self.logger.warning(f'Failed to load key file {file_path.name}: {error}')
                    # Continue loading other keys
            
            return keys
        except Exception as error:
            self.logger.error(f'Failed to load all keys: {error}')
            return []
    
    async def delete(self, kid: str) -> bool:
        """
        Delete a key from filesystem.
        
        Args:
            kid: Key ID
        
        Returns:
            True if deleted, False if not found
        """
        try:
            key_file = self.key_store_path / f'{kid}{self.file_extension}'
            
            if not key_file.exists():
                return False
            
            key_file.unlink()
            self.logger.info(f'🗑️  Deleted key from filesystem: {kid}')
            return True
        except FileNotFoundError:
            return False
        except Exception as error:
            self.logger.error(f'Failed to delete key {kid}: {error}')
            raise
    
    async def exists(self, kid: str) -> bool:
        """
        Check if a key exists in filesystem.
        
        Args:
            kid: Key ID
        
        Returns:
            True if key exists, False otherwise
        """
        try:
            key_file = self.key_store_path / f'{kid}{self.file_extension}'
            return key_file.exists()
        except Exception:
            return False
    
    async def list(self) -> List[str]:
        """
        List all key IDs in filesystem.
        
        Returns:
            List of key IDs
        """
        try:
            return [
                f.stem  # Get filename without extension
                for f in self.key_store_path.glob(f'*{self.file_extension}')
            ]
        except Exception:
            return []
    
    async def close(self) -> None:
        """Clean up resources (no-op for filesystem)."""
        pass
