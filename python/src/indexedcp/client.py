import os
import asyncio
import time
import json
import urllib.request
import urllib.error
from pathlib import Path
from typing import Any, Dict, List, Optional, Callable

from .logger import create_logger
from .storage import SQLiteStorage


class IndexedCPClient:
    
    def __init__(
        self,
        server_url: Optional[str] = None,
        api_key: Optional[str] = None,
        storage_path: Optional[str] = None,
        chunk_size: int = 1024 * 1024,  # 1MB default
        encryption: bool = False,
        log_level: Optional[str] = None,
        **options
    ):
        """
        Initialize IndexedCP client.
        
        Args:
            server_url: URL of the IndexedCP server
            api_key: API key for authentication
            storage_path: Path to SQLite database file (default: ~/.indexcp/db/client.db)
            chunk_size: Size of each chunk in bytes (default: 1MB)
            encryption: Enable encryption (not supported in basic version)
            log_level: Logging level (DEBUG, INFO, WARN, ERROR)
            **options: Additional options
        """
        self.server_url = server_url
        self.api_key = api_key or os.environ.get('INDEXEDCP_API_KEY')
        
        # Use home directory for storage (matching JS implementation)
        if storage_path is None:
            home_dir = Path.home()
            storage_dir = home_dir / '.indexcp' / 'db'
            storage_dir.mkdir(parents=True, exist_ok=True)
            storage_path = str(storage_dir / 'client.db')
        
        self.storage_path = storage_path
        self.chunk_size = chunk_size
        self.encryption = encryption
        
        # Storage instance (using existing SQLiteStorage abstraction)
        self.storage: Optional[SQLiteStorage] = None
        self.store_name = 'chunks'
        
        # Logger configuration
        self.log_level = log_level or os.environ.get('INDEXEDCP_LOG_LEVEL', 'INFO')
        self.logger = create_logger('IndexedCP.Client', level=self.log_level)
        
        # Encryption not supported in basic implementation
        if self.encryption:
            raise NotImplementedError(
                "Encryption not supported in basic client implementation. "
                "Set encryption=False or use EncryptedClient (coming soon)."
            )
    
    async def initialize(self) -> None:
        """
        Initialize client storage.
        
        Creates the storage instance and initializes the database.
        Must be called before using add_file() or other operations.
        """
        # Create storage instance with custom table name for chunks
        self.storage = SQLiteStorage(
            db_path=self.storage_path,
            table_name=self.store_name,
            log_level=self.log_level
        )
        
        await self.storage.initialize()
        self.logger.info(f"✓ Client initialized with storage: {self.storage_path}")
    
    async def add_file(self, filepath: str) -> int:
        """
        Add a file to the upload queue with chunking.
        
        Reads the file, splits it into chunks, and stores each chunk
        in storage for later upload. Supports offline operation.
        
        Args:
            filepath: Path to the file to upload
        
        Returns:
            Number of chunks created
        
        Raises:
            FileNotFoundError: If file doesn't exist
            RuntimeError: If storage not initialized
        """
        if not self.storage:
            raise RuntimeError("Client not initialized. Call initialize() first.")
        
        file_path = Path(filepath)
        
        if not file_path.exists():
            raise FileNotFoundError(f"File not found: {filepath}")
        
        if not file_path.is_file():
            raise ValueError(f"Not a file: {filepath}")
        
        self.logger.info(f"Adding file {file_path.name} to buffer")
        
        # Store all chunks (matching JS structure: id, fileName, chunkIndex, data only)
        chunk_index = 0
        with open(file_path, 'rb') as f:
            while True:
                chunk_data = f.read(self.chunk_size)
                if not chunk_data:
                    break
                
                # Create chunk record (matching JS structure - minimal fields)
                chunk_key = f"{filepath}-{chunk_index}"
                chunk_record = {
                    'id': chunk_key,
                    'fileName': str(filepath),
                    'chunkIndex': chunk_index,
                    'data': chunk_data.hex()  # Store as hex string (JSON serializable)
                }
                
                # Save to storage using storage abstraction
                await self.storage.save(chunk_key, chunk_record)
                chunk_index += 1
        
        self.logger.info(f"File {file_path.name} added to buffer with {chunk_index} chunks")
        
        return chunk_index
    
    async def upload_buffered_files(
        self,
        server_url: Optional[str] = None
    ) -> Dict[str, str]:
        """
        Upload all buffered files to the server.
        
        Args:
            server_url: Server URL (uses constructor value if not provided)
        
        Returns:
            Dictionary mapping client file paths to server file names
        
        Raises:
            RuntimeError: If storage not initialized or server_url not provided
        """
        if not self.storage:
            raise RuntimeError("Client not initialized. Call initialize() first.")
        
        target_url = server_url or self.server_url
        if not target_url:
            raise ValueError("server_url required for upload")
        
        if not self.api_key:
            raise ValueError("api_key required for upload")
        
        # Get all records from storage
        all_records = await self.storage.load_all()
        
        self.logger.info(f"Found {len(all_records)} buffered chunks")
        
        if len(all_records) == 0:
            self.logger.info("No buffered files to upload")
            return {}
        
        # Group records by fileName
        file_groups = {}
        for record in all_records:
            file_name = record.get('fileName')
            if file_name not in file_groups:
                file_groups[file_name] = []
            file_groups[file_name].append(record)
        
        self.logger.info(f"Grouped into {len(file_groups)} files: {list(file_groups.keys())}")
        
        # Upload all files sequentially
        upload_results = {}
        for file_name, chunks in file_groups.items():
            result = await self._upload_file_chunks(target_url, file_name, chunks)
            upload_results[result['fileName']] = result['serverFilename']
        
        return upload_results
    
    async def _upload_file_chunks(
        self,
        server_url: str,
        file_name: str,
        chunks: List[Dict[str, Any]]
    ) -> Dict[str, str]:
        """
        Upload a single file's chunks in order.
        
        Args:
            server_url: Server URL
            file_name: File name to upload
            chunks: List of chunk records
        
        Returns:
            Dictionary with fileName and serverFilename
        """
        self.logger.info(f"Uploading {file_name} with {len(chunks)} chunks...")
        
        # Sort chunks by index
        chunks.sort(key=lambda c: c.get('chunkIndex', 0))
        
        server_filename = None
        
        # Upload chunks sequentially to preserve order
        for chunk in chunks:
            chunk_index = chunk.get('chunkIndex', 0)
            self.logger.info(f"Uploading chunk {chunk_index} for {file_name}")
            
            # Convert hex string back to bytes
            chunk_data = bytes.fromhex(chunk.get('data', ''))
            
            response = await self._upload_chunk(
                server_url,
                chunk_data,
                chunk_index,
                file_name
            )
            
            # Capture server-determined filename from first chunk response
            if response and response.get('actualFilename') and not server_filename:
                server_filename = response['actualFilename']
            
            # Delete chunk from storage after successful upload (matching JS)
            await self.storage.delete(chunk['id'])
        
        # Store the mapping of client filename to server filename
        server_filename = server_filename or Path(file_name).name
        
        if server_filename != Path(file_name).name:
            self.logger.info(f"Upload complete for {file_name} -> Server saved as: {server_filename}")
        else:
            self.logger.info(f"Upload complete for {file_name}")
        
        return {'fileName': file_name, 'serverFilename': server_filename}
    
    async def _upload_chunk(
        self,
        server_url: str,
        chunk: bytes,
        index: int,
        file_name: str
    ) -> Optional[Dict[str, Any]]:
        """
        Upload a single chunk to the server.
        
        Args:
            server_url: Server URL
            chunk: Chunk data as bytes
            index: Chunk index
            file_name: File name
        
        Returns:
            Response data dictionary or None
        """
        headers = {
            'Content-Type': 'application/octet-stream',
            'X-Chunk-Index': str(index),
            'X-File-Name': file_name,
            'Authorization': f'Bearer {self.api_key}'
        }
        
        try:
            req = urllib.request.Request(
                server_url,
                data=chunk,
                headers=headers,
                method='POST'
            )
            
            with urllib.request.urlopen(req) as response:
                if response.status == 401:
                    raise RuntimeError("Authentication failed: Invalid API key")
                
                if response.status != 200:
                    raise RuntimeError(
                        f"Upload failed: {response.status} - {response.reason}"
                    )
                
                # Try to parse response as JSON
                try:
                    response_data = response.read().decode('utf-8')
                    result = json.loads(response_data)
                    
                    # Log server-determined filename if different
                    if result.get('actualFilename') and result['actualFilename'] != file_name:
                        if result['actualFilename'] != Path(file_name).name:
                            self.logger.info(
                                f"Server used filename: {result['actualFilename']} "
                                f"(client sent: {file_name})"
                            )
                    
                    return result
                except (json.JSONDecodeError, KeyError):
                    # Backward compatibility: plain text response
                    return None
        
        except urllib.error.HTTPError as e:
            if e.code == 401:
                raise RuntimeError("Authentication failed: Invalid API key")
            raise RuntimeError(f"Upload failed: {e.code} - {e.reason}")
        except urllib.error.URLError as e:
            raise RuntimeError(f"Upload failed: {e.reason}")
    
    async def close(self) -> None:
        """
        Close client storage connection.
        
        Should be called when done using the client to properly
        release database resources.
        """
        if self.storage:
            await self.storage.close()
            self.storage = None
            self.logger.info("✓ Client storage closed")
    
    # Context manager support
    async def __aenter__(self):
        """Async context manager entry."""
        await self.initialize()
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit."""
        await self.close()
        return False
