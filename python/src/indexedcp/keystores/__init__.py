"""
KeyStore Factory and Exports

Provides easy access to all keystore implementations.
"""

from typing import Dict, Any, Optional

from .base_keystore import BaseKeyStore
from .filesystem_keystore import FileSystemKeyStore


def create_keystore(keystore_type: str, options: Optional[Dict[str, Any]] = None) -> BaseKeyStore:
    """
    Create a keystore instance based on type.
    
    Args:
        keystore_type: Type of keystore ('filesystem', 'file', 'fs')
        options: Configuration options for the keystore
    
    Returns:
        Keystore instance
    
    Raises:
        ValueError: If keystore type is unknown
    
    Examples:
        >>> keystore = create_keystore('filesystem', {'key_store_path': './keys'})
        >>> await keystore.initialize()
    """
    options = options or {}
    keystore_type_lower = keystore_type.lower()
    
    if keystore_type_lower in ('filesystem', 'file', 'fs'):
        return FileSystemKeyStore(options)
    else:
        valid_types = ['filesystem', 'file', 'fs']
        raise ValueError(
            f"Unknown keystore type: {keystore_type}. "
            f"Valid types: {', '.join(valid_types)}"
        )


__all__ = [
    'BaseKeyStore',
    'FileSystemKeyStore',
    'create_keystore'
]
