"""
Base KeyStore interface

All keystore implementations must extend this class and implement:
- save(kid, key_data)
- load(kid)
- load_all()
- delete(kid)
- exists(kid)
"""

from abc import ABC, abstractmethod
from typing import Optional, Dict, Any, List

from ..logger import create_logger


class BaseKeyStore(ABC):
    """Abstract base class for keystore implementations."""
    
    def __init__(self, options: Optional[Dict[str, Any]] = None):
        """
        Initialize base keystore.
        
        Args:
            options: Configuration options including log_level
        """
        options = options or {}
        self.logger = create_logger(
            name=self.__class__.__name__,
            level=options.get('log_level', 'INFO')
        )
    
    @abstractmethod
    async def save(self, kid: str, key_data: Dict[str, Any]) -> None:
        """
        Save a key pair to storage.
        
        Args:
            kid: Key ID
            key_data: Key data to store
                - kid: Key ID
                - privateKey: Private key (PEM format)
                - publicKey: Public key (PEM format)
                - createdAt: Timestamp (milliseconds)
                - active: Whether this is the active key
        
        Raises:
            Exception: If save operation fails
        """
        pass
    
    @abstractmethod
    async def load(self, kid: str) -> Optional[Dict[str, Any]]:
        """
        Load a specific key by ID.
        
        Args:
            kid: Key ID
        
        Returns:
            Key data dictionary or None if not found
        
        Raises:
            Exception: If load operation fails
        """
        pass
    
    @abstractmethod
    async def load_all(self) -> List[Dict[str, Any]]:
        """
        Load all keys from storage.
        
        Returns:
            List of key data dictionaries
        
        Raises:
            Exception: If load operation fails
        """
        pass
    
    @abstractmethod
    async def delete(self, kid: str) -> bool:
        """
        Delete a key from storage.
        
        Args:
            kid: Key ID
        
        Returns:
            True if deleted, False if not found
        
        Raises:
            Exception: If delete operation fails
        """
        pass
    
    @abstractmethod
    async def exists(self, kid: str) -> bool:
        """
        Check if a key exists.
        
        Args:
            kid: Key ID
        
        Returns:
            True if key exists, False otherwise
        """
        pass
    
    async def list(self) -> List[str]:
        """
        List all key IDs.
        
        Returns:
            List of key IDs
        """
        keys = await self.load_all()
        return [k['kid'] for k in keys]
    
    async def close(self) -> None:
        """
        Clean up resources (optional).
        
        Override in subclass if cleanup is needed.
        """
        pass
    
    async def initialize(self) -> None:
        """
        Initialize the keystore (optional).
        
        Override in subclass if initialization is needed.
        """
        pass
