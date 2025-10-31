"""
Base Storage interface for IndexedCP

Abstract base class defining the storage interface for all implementations.
"""

from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional


class BaseStorage(ABC):
    """
    Abstract base class for storage implementations.
    
    All storage backends must implement these methods to provide
    consistent key-value persistence across different storage engines.
    """
    
    def __init__(self, **options):
        """
        Initialize storage with options.
        
        Args:
            **options: Storage-specific configuration options
        """
        self.options = options
    
    @abstractmethod
    async def initialize(self) -> None:
        """
        Initialize the storage backend.
        
        This method should set up connections, create tables/collections,
        and perform any necessary setup before the storage can be used.
        
        Raises:
            Exception: If initialization fails
        """
        pass
    
    @abstractmethod
    async def save(self, key: str, data: Dict[str, Any]) -> None:
        """
        Save data to storage.
        
        Args:
            key: Unique identifier for the data
            data: Dictionary containing data to store
        
        Raises:
            Exception: If save operation fails
        """
        pass
    
    @abstractmethod
    async def load(self, key: str) -> Optional[Dict[str, Any]]:
        """
        Load data from storage by key.
        
        Args:
            key: Unique identifier for the data
        
        Returns:
            Dict containing the stored data, or None if not found
        
        Raises:
            Exception: If load operation fails
        """
        pass
    
    @abstractmethod
    async def load_all(self) -> List[Dict[str, Any]]:
        """
        Load all data from storage.
        
        Returns:
            List of all stored data dictionaries
        
        Raises:
            Exception: If load operation fails
        """
        pass
    
    @abstractmethod
    async def delete(self, key: str) -> bool:
        """
        Delete data from storage by key.
        
        Args:
            key: Unique identifier for the data
        
        Returns:
            True if data was deleted, False if key didn't exist
        
        Raises:
            Exception: If delete operation fails
        """
        pass
    
    @abstractmethod
    async def exists(self, key: str) -> bool:
        """
        Check if a key exists in storage.
        
        Args:
            key: Unique identifier to check
        
        Returns:
            True if key exists, False otherwise
        
        Raises:
            Exception: If check operation fails
        """
        pass
    
    @abstractmethod
    async def list(self) -> List[str]:
        """
        List all keys in storage.
        
        Returns:
            List of all keys
        
        Raises:
            Exception: If list operation fails
        """
        pass
    
    @abstractmethod
    async def close(self) -> None:
        """
        Close storage connections and cleanup resources.
        
        This method should be called when the storage is no longer needed
        to ensure proper resource cleanup.
        """
        pass
    
    async def __aenter__(self):
        """Context manager entry - initialize storage."""
        await self.initialize()
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit - close storage."""
        await self.close()
        return False
