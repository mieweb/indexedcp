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
        max_retries: int = float('inf'),
        initial_retry_delay: float = 1.0,
        max_retry_delay: float = 60.0,
        retry_multiplier: float = 2.0,
        on_upload_progress: Optional[Callable] = None,
        on_upload_error: Optional[Callable] = None,
        on_upload_complete: Optional[Callable] = None,
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
            max_retries: Maximum retry attempts (default: infinite)
            initial_retry_delay: Initial retry delay in seconds (default: 1.0)
            max_retry_delay: Maximum retry delay in seconds (default: 60.0)
            retry_multiplier: Exponential backoff multiplier (default: 2.0)
            on_upload_progress: Callback for upload progress
            on_upload_error: Callback for upload errors
            on_upload_complete: Callback for upload completion
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
        
        # Retry settings
        self.max_retries = max_retries
        self.initial_retry_delay = initial_retry_delay
        self.max_retry_delay = max_retry_delay
        self.retry_multiplier = retry_multiplier
        
        # Callbacks
        self.on_upload_progress = on_upload_progress
        self.on_upload_error = on_upload_error
        self.on_upload_complete = on_upload_complete
        
        # Background upload state
        self.background_upload_task: Optional[asyncio.Task] = None
        self.background_upload_running = False
        
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
                    'data': chunk_data.hex(),  # Store as hex string (JSON serializable)
                    'retryMetadata': {
                        'retryCount': 0,
                        'lastAttempt': None,
                        'nextRetry': time.time() * 1000,  # Current time in ms
                        'errors': []
                    }
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
        Upload a single file's chunks in order with retry support.
        
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
        errors = []
        success_count = 0
        now = time.time() * 1000  # Current time in ms
        
        # Upload chunks sequentially to preserve order
        for chunk in chunks:
            chunk_index = chunk.get('chunkIndex', 0)
            
            # Initialize retry metadata if not present
            if 'retryMetadata' not in chunk:
                chunk['retryMetadata'] = {
                    'retryCount': 0,
                    'lastAttempt': None,
                    'nextRetry': now,
                    'errors': []
                }
            
            retry_metadata = chunk['retryMetadata']
            
            # Check if ready for retry
            if retry_metadata['nextRetry'] > now:
                self.logger.debug(f"Chunk {chunk_index} not ready for retry yet")
                continue
            
            # Check max retries
            if retry_metadata['retryCount'] >= self.max_retries:
                self.logger.warning(
                    f"⚠ Max retries ({self.max_retries}) reached for chunk {chunk_index}"
                )
                continue
            
            try:
                # Update retry metadata
                retry_metadata['lastAttempt'] = now
                retry_metadata['retryCount'] += 1
                
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
                success_count += 1
                
                # Call progress callback
                if self.on_upload_progress:
                    self.on_upload_progress({
                        'fileName': file_name,
                        'chunkIndex': chunk_index,
                        'status': 'success',
                        'retryCount': retry_metadata['retryCount'] - 1
                    })
                
            except Exception as error:
                # Failure - update retry metadata with exponential backoff
                delay = min(
                    self.initial_retry_delay * (self.retry_multiplier ** (retry_metadata['retryCount'] - 1)),
                    self.max_retry_delay
                ) * 1000  # Convert to ms
                
                retry_metadata['nextRetry'] = now + delay
                retry_metadata['errors'].append({
                    'timestamp': now,
                    'message': str(error)
                })
                
                # Keep only last 5 errors
                if len(retry_metadata['errors']) > 5:
                    retry_metadata['errors'] = retry_metadata['errors'][-5:]
                
                # Update chunk in storage with new retry metadata
                chunk['retryMetadata'] = retry_metadata
                await self.storage.save(chunk['id'], chunk)
                
                errors.append(error)
                
                retry_display = f"{retry_metadata['retryCount']}/{self.max_retries if self.max_retries != float('inf') else '∞'}"
                self.logger.warning(
                    f"⚠ Upload failed for {file_name} chunk {chunk_index} "
                    f"(retry {retry_display}). Next retry in {delay/1000:.0f}s"
                )
                
                # Call progress callback
                if self.on_upload_progress:
                    self.on_upload_progress({
                        'fileName': file_name,
                        'chunkIndex': chunk_index,
                        'status': 'failed',
                        'retryCount': retry_metadata['retryCount'],
                        'nextRetryIn': delay,
                        'error': str(error)
                    })
        
        if errors:
            raise RuntimeError(f"{len(errors)} chunk(s) failed for {file_name}")
        
        # Store the mapping of client filename to server filename
        server_filename = server_filename or Path(file_name).name
        
        if server_filename != Path(file_name).name:
            self.logger.info(f"Upload complete for {file_name} -> Server saved as: {server_filename}")
        else:
            self.logger.info(f"✓ Successfully uploaded {file_name} ({success_count} chunks)")
        
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
    
    async def start_upload_background(
        self,
        server_url: Optional[str] = None,
        check_interval: float = 5.0
    ) -> None:
        """
        Start background upload process with automatic retry.
        
        Continuously monitors pending uploads and retries failures with exponential backoff.
        
        Args:
            server_url: Server URL for uploads (uses constructor value if not provided)
            check_interval: How often to check for pending uploads in seconds (default: 5.0)
        """
        if self.background_upload_task and not self.background_upload_task.done():
            self.logger.info("Background upload already running")
            return
        
        self.logger.info(f" Starting background upload (checking every {check_interval}s)")
        
        # Start background task
        self.background_upload_task = asyncio.create_task(
            self._background_upload_loop(server_url, check_interval)
        )
    
    async def stop_upload_background(self) -> None:
        """Stop background upload process."""
        if self.background_upload_task and not self.background_upload_task.done():
            self.background_upload_task.cancel()
            try:
                await self.background_upload_task
            except asyncio.CancelledError:
                pass
            self.background_upload_task = None
            self.logger.info("⏹ Stopped background upload")
    
    async def _background_upload_loop(
        self,
        server_url: Optional[str],
        check_interval: float
    ) -> None:
        """
        Background upload loop with automatic retry.
        
        Args:
            server_url: Server URL for uploads
            check_interval: Check interval in seconds
        """
        while True:
            try:
                if not self.background_upload_running:
                    await self._process_background_upload(server_url)
                
                await asyncio.sleep(check_interval)
                
            except asyncio.CancelledError:
                break
            except Exception as error:
                self.logger.error(f"Background upload error: {error}")
                if self.on_upload_error:
                    self.on_upload_error(error)
    
    async def _process_background_upload(self, server_url: Optional[str]) -> None:
        """
        Process pending uploads with retry logic.
        
        Args:
            server_url: Server URL for uploads
        """
        if self.background_upload_running:
            return
        
        self.background_upload_running = True
        
        try:
            target_url = server_url or self.server_url
            if not target_url:
                raise ValueError("server_url required for background upload")
            
            if not self.storage:
                raise RuntimeError("Client not initialized")
            
            # Get all records from storage
            all_records = await self.storage.load_all()
            now = time.time() * 1000  # Current time in ms
            
            if not all_records:
                return
            
            # Filter for records ready for retry
            retryable_records = []
            for record in all_records:
                # Initialize retry metadata if not present
                if 'retryMetadata' not in record:
                    record['retryMetadata'] = {
                        'retryCount': 0,
                        'lastAttempt': None,
                        'nextRetry': now,
                        'errors': []
                    }
                
                retry_metadata = record['retryMetadata']
                
                # Check if ready for retry
                if retry_metadata['nextRetry'] > now:
                    continue
                
                # Check max retries
                if retry_metadata['retryCount'] >= self.max_retries:
                    continue
                
                retryable_records.append(record)
            
            if not retryable_records:
                return
            
            # Group by fileName
            file_groups = {}
            for record in retryable_records:
                file_name = record.get('fileName')
                if file_name not in file_groups:
                    file_groups[file_name] = []
                file_groups[file_name].append(record)
            
            file_count = len(file_groups)
            if file_count == 0:
                return
            
            self.logger.info(f" Background upload: {file_count} file(s) with pending chunks")
            
            # Upload files sequentially
            succeeded = 0
            failed = 0
            
            for file_name, chunks in file_groups.items():
                try:
                    await self._upload_file_chunks(target_url, file_name, chunks)
                    succeeded += 1
                except Exception as error:
                    failed += 1
                    self.logger.error(f"Failed to upload {file_name}: {error}")
            
            # Report results
            if succeeded > 0 and self.on_upload_complete:
                self.on_upload_complete({
                    'succeeded': succeeded,
                    'failed': failed,
                    'total': succeeded + failed
                })
        
        finally:
            self.background_upload_running = False
    
    async def close(self) -> None:
        """
        Close client storage connection.
        
        Should be called when done using the client to properly
        release database resources.
        """
        # Stop background upload if running
        await self.stop_upload_background()
        
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
