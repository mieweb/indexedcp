import os
import asyncio
import time
import json
import urllib.request
import urllib.error
import base64
from pathlib import Path
from typing import Any, Dict, List, Optional, Callable

from .logger import create_logger
from .storage import SQLiteStorage, EncryptedStorage
from .crypto_utils import CryptoUtils


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
        
        # Storage instance (SQLiteStorage for basic, EncryptedStorage for encryption)
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
        
        # Encryption support (optional)
        if self.encryption:
            # Load encryption modules
            self.crypto_utils = CryptoUtils()
            self.session_keys: Dict[str, bytes] = {}  # sessionId -> AES key (in memory)
            self.session_seq_counters: Dict[str, int] = {}  # sessionId -> next seq number
    
    async def initialize(self) -> None:
        """
        Initialize client storage.
        
        Creates the storage instance and initializes the database.
        Must be called before using add_file() or other operations.
        """
        # Create storage instance based on encryption mode
        if self.encryption:
            # For encrypted storage, use custom path based on storage_path
            # This allows each client to have its own encrypted storage directory
            encrypted_storage_dir = Path(self.storage_path).parent / 'encrypted-db'
            self.storage = EncryptedStorage(
                db_name='indexedcp-encrypted',
                version=1,
                db_path=str(encrypted_storage_dir),
                log_level=self.log_level
            )
        else:
            self.storage = SQLiteStorage(
                db_path=self.storage_path,
                table_name=self.store_name,
                log_level=self.log_level
            )
        
        await self.storage.initialize()
        self.logger.info(f"[OK] Client initialized with storage: {self.storage_path}")
    
    # ============================================================================
    # Encryption Methods (only used when encryption=True)
    # ============================================================================
    
    async def fetch_public_key(self) -> Dict[str, str]:
        """
        Fetch public key from server.
        
        Returns:
            Dict with 'publicKey', 'kid', and 'expiresAt'
        
        Raises:
            RuntimeError: If encryption not enabled or serverUrl not provided
        """
        if not self.encryption:
            raise RuntimeError('Encryption not enabled. Set encryption=True in constructor.')
        
        if not self.server_url:
            raise RuntimeError('serverUrl required for fetch_public_key()')
        
        # Construct public key endpoint URL
        base_url = self.server_url.replace('/upload', '')
        public_key_url = f"{base_url}/public-key"
        
        try:
            req = urllib.request.Request(public_key_url, method='GET')
            
            with urllib.request.urlopen(req) as response:
                if response.status != 200:
                    raise RuntimeError(f"Failed to fetch public key: {response.status}")
                
                response_data = response.read().decode('utf-8')
                public_key_info = json.loads(response_data)
            
            # Cache the public key
            if isinstance(self.storage, EncryptedStorage):
                await self.storage.save_public_key({
                    'kid': public_key_info['kid'],
                    'publicKey': public_key_info['publicKey'],
                    'fetchedAt': time.time() * 1000,
                    'expiresAt': public_key_info.get('expiresAt', (time.time() + 86400) * 1000)
                })
            
            self.logger.info(f"[OK] Fetched and cached server public key (kid: {public_key_info['kid']})")
            return public_key_info
        
        except urllib.error.URLError as e:
            raise RuntimeError(f"Failed to fetch public key: {e.reason}")
    
    async def get_cached_public_key(self) -> Optional[Dict[str, str]]:
        """
        Get cached public key for offline use.
        
        Returns:
            Dict with 'publicKey', 'kid', 'fetchedAt', 'expiresAt' or None if not found
        
        Raises:
            RuntimeError: If encryption not enabled
        """
        if not self.encryption:
            raise RuntimeError('Encryption not enabled. Set encryption=True in constructor.')
        
        if not isinstance(self.storage, EncryptedStorage):
            return None
        
        return await self.storage.get_cached_public_key()
    
    async def start_stream(self, file_name: str) -> str:
        """
        Start encrypted stream for a file.
        
        Args:
            file_name: Name of the file to encrypt
        
        Returns:
            Session ID for the encrypted stream
        
        Raises:
            RuntimeError: If encryption not enabled or no public key available
        """
        if not self.encryption:
            raise RuntimeError('Encryption not enabled. Set encryption=True in constructor.')
        
        if not isinstance(self.storage, EncryptedStorage):
            raise RuntimeError('Encrypted storage not initialized')
        
        # Get public key (cached or fetch)
        public_key_info = await self.get_cached_public_key()
        if not public_key_info and self.server_url:
            public_key_info = await self.fetch_public_key()
        
        if not public_key_info:
            raise RuntimeError(
                'No public key available. Call fetch_public_key() first or provide serverUrl.'
            )
        
        # Generate session key and ID
        session_key = self.crypto_utils.generate_session_key()
        session_id = self.crypto_utils.generate_session_id()
        
        # Wrap session key with server's public key
        wrapped_key = self.crypto_utils.wrap_session_key(
            session_key,
            public_key_info['publicKey']
        )
        
        # Store session in database
        await self.storage.save_session({
            'sessionId': session_id,
            'kid': public_key_info['kid'],
            'wrappedKey': base64.b64encode(wrapped_key).decode('utf-8'),
            'fileName': file_name,
            'createdAt': time.time() * 1000
        })
        
        # Keep session key in memory for packet encryption
        self.session_keys[session_id] = session_key
        
        # Initialize sequence counter for this session
        self.session_seq_counters[session_id] = 0
        
        self.logger.info(f"[OK] Started encrypted stream: {session_id} for {file_name}")
        return session_id
    
    async def add_packet(
        self,
        session_id: str,
        data: bytes,
        seq: Optional[int] = None
    ) -> None:
        """
        Add encrypted packet to buffer.
        
        Args:
            session_id: Session identifier
            data: Packet data as bytes
            seq: Packet sequence number (auto-increments if not provided)
        
        Raises:
            RuntimeError: If encryption not enabled or session not found
        """
        if not self.encryption:
            raise RuntimeError('Encryption not enabled. Set encryption=True in constructor.')
        
        if not isinstance(self.storage, EncryptedStorage):
            raise RuntimeError('Encrypted storage not initialized')
        
        # Get session key from memory
        session_key = self.session_keys.get(session_id)
        if not session_key:
            raise RuntimeError(
                f"No session key for {session_id}. Call start_stream() first."
            )
        
        # Auto-increment sequence number if not provided
        if seq is None:
            seq = self.session_seq_counters.get(session_id, 0)
            self.session_seq_counters[session_id] = seq + 1
        
        # Encrypt packet
        encrypted = self.crypto_utils.encrypt_packet(data, session_key, {
            'sessionId': session_id,
            'seq': seq,
            'codec': 'raw',
            'timestamp': int(time.time() * 1000)
        })
        
        # Store encrypted packet
        await self.storage.save_packet({
            'id': f"{session_id}-{seq}",
            'sessionId': session_id,
            'seq': seq,
            'ciphertext': base64.b64encode(encrypted['ciphertext']).decode('utf-8'),
            'iv': base64.b64encode(encrypted['iv']).decode('utf-8'),
            'authTag': base64.b64encode(encrypted['authTag']).decode('utf-8'),
            'aad': base64.b64encode(encrypted['aad']).decode('utf-8'),
            'status': 'pending',
            'createdAt': time.time() * 1000
        })
    
    async def get_encryption_status(self) -> Dict[str, Any]:
        """
        Get encryption status.
        
        Returns:
            Dict with encryption information
        """
        if not self.encryption:
            return {'encryption': False}
        
        if not isinstance(self.storage, EncryptedStorage):
            return {'encryption': True, 'initialized': False}
        
        sessions = await self.storage.get_all_sessions()
        pending_packets = await self.storage.get_all_pending_packets()
        cached_key = await self.storage.get_cached_public_key()
        
        return {
            'encryption': True,
            'isEncrypted': True,
            'activeSessions': len(sessions),
            'pendingPackets': len(pending_packets),
            'cachedKey': cached_key['kid'] if cached_key else None,
            'currentKeyId': cached_key['kid'] if cached_key else None
        }
    
    # ============================================================================
    # End Encryption Methods
    # ============================================================================
    
    async def add_file(self, filepath: str) -> int:
        """
        Add a file to the upload queue with chunking.
        
        Reads the file, splits it into chunks, and stores each chunk
        in storage for later upload. Supports offline operation.
        
        For encryption mode: returns sessionId (str)
        For normal mode: returns chunk count (int)
        
        Args:
            filepath: Path to the file to upload
        
        Returns:
            Session ID (encryption mode) or number of chunks created (normal mode)
        
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
        
        # Handle encryption mode
        if self.encryption:
            return await self._add_file_encrypted(filepath)
        
        # Original unencrypted logic
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
    
    async def _add_file_encrypted(self, filepath: str) -> str:
        """
        Add file with encryption enabled.
        
        Args:
            filepath: Path to the file to upload
        
        Returns:
            Session ID for the encrypted upload
        
        Raises:
            RuntimeError: If encryption setup fails
        """
        file_name = str(filepath)
        session_id = None
        
        try:
            # Start encrypted stream
            session_id = await self.start_stream(file_name)
            
            # Read and encrypt file in chunks
            seq = 0
            with open(filepath, 'rb') as f:
                while True:
                    chunk_data = f.read(self.chunk_size)
                    if not chunk_data:
                        break
                    
                    await self.add_packet(session_id, chunk_data, seq)
                    seq += 1
            
            # Clear session key from memory (keys only during capture)
            if session_id in self.session_keys:
                del self.session_keys[session_id]
            
            self.logger.info(f"[OK] File {Path(filepath).name} encrypted and buffered ({seq} packets)")
            return session_id
            
        except Exception as error:
            # Clean up session key on error
            if session_id and session_id in self.session_keys:
                del self.session_keys[session_id]
            raise
    
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
        
        # Handle encryption mode
        if self.encryption:
            return await self._upload_encrypted_files(target_url)
        
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
    
    async def _upload_encrypted_files(self, server_url: str) -> Dict[str, str]:
        """
        Upload encrypted files (encryption mode).
        
        Args:
            server_url: Server URL
        
        Returns:
            Dictionary mapping file names to server filenames
        """
        if not isinstance(self.storage, EncryptedStorage):
            raise RuntimeError('Encrypted storage not initialized')
        
        # Get all pending packets grouped by session
        pending_packets = await self.storage.get_all_pending_packets()
        
        self.logger.info(f"Found {len(pending_packets)} encrypted packets to upload")
        
        if len(pending_packets) == 0:
            self.logger.info("No buffered files to upload")
            return {}
        
        # Group by sessionId
        session_groups: Dict[str, List[Dict[str, Any]]] = {}
        for packet in pending_packets:
            session_id = packet['sessionId']
            if session_id not in session_groups:
                session_groups[session_id] = []
            session_groups[session_id].append(packet)
        
        # Upload all sessions
        upload_results = {}
        for session_id, session_packets in session_groups.items():
            result = await self._upload_session(server_url, session_id, session_packets)
            if result:
                upload_results[result['fileName']] = result['serverFilename']
        
        return upload_results
    
    async def _upload_session(
        self,
        server_url: str,
        session_id: str,
        session_packets: List[Dict[str, Any]]
    ) -> Optional[Dict[str, str]]:
        """
        Upload a single session's packets.
        
        Args:
            server_url: Server URL
            session_id: Session identifier
            session_packets: List of packet records
        
        Returns:
            Dict with fileName and serverFilename or None if session not found
        """
        if not isinstance(self.storage, EncryptedStorage):
            raise RuntimeError('Encrypted storage not initialized')
        
        # Get session metadata
        session = await self.storage.get_session(session_id)
        if not session:
            self.logger.warning(f"⚠ Session {session_id} not found, skipping")
            return None
        
        self.logger.info(
            f"Uploading {session['fileName']} ({len(session_packets)} encrypted packets)..."
        )
        
        # Sort packets by sequence number
        session_packets.sort(key=lambda p: p['seq'])
        
        server_filename = None
        
        # Upload packets sequentially (to preserve order)
        for packet in session_packets:
            try:
                result = await self._upload_encrypted_packet(
                    server_url,
                    session,
                    packet
                )
                
                if result and result.get('actualFilename') and not server_filename:
                    server_filename = result['actualFilename']
                
                # Mark packet as uploaded
                await self.storage.update_packet_status(packet['id'], 'uploaded')
                
            except Exception as error:
                self.logger.error(
                    f"Failed to upload packet {packet['id']}: {error}"
                )
                raise
        
        self.logger.info(f"[OK] Upload complete: {session['fileName']}")
        
        # Clean up session keys from memory
        if session_id in self.session_keys:
            del self.session_keys[session_id]
        if session_id in self.session_seq_counters:
            del self.session_seq_counters[session_id]
        
        return {
            'fileName': session['fileName'],
            'serverFilename': server_filename or session['fileName']
        }
    
    async def _upload_encrypted_packet(
        self,
        server_url: str,
        session: Dict[str, Any],
        packet: Dict[str, Any]
    ) -> Optional[Dict[str, Any]]:
        """
        Upload a single encrypted packet to the server.
        
        Args:
            server_url: Server URL
            session: Session metadata
            packet: Packet data
        
        Returns:
            Response data or None
        """
        # Use /upload-encrypted endpoint for encrypted uploads
        encrypted_url = server_url.replace('/upload', '/upload-encrypted')
        
        # Prepare packet data for upload - server expects all fields in body
        packet_data = {
            'sessionId': session['sessionId'],
            'kid': session['kid'],
            'wrappedKey': session['wrappedKey'],
            'ciphertext': packet['ciphertext'],
            'iv': packet['iv'],
            'authTag': packet['authTag'],
            'aad': packet['aad'],
            'seq': packet['seq'],
            'fileName': session.get('fileName', 'uploaded_file.txt')
        }
        
        # Headers for encrypted upload
        headers = {
            'Content-Type': 'application/json',
            'Authorization': f'Bearer {self.api_key}'
        }
        
        try:
            # Send as JSON
            json_data = json.dumps(packet_data).encode('utf-8')
            
            req = urllib.request.Request(
                encrypted_url,  # Use encrypted endpoint
                data=json_data,
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
                
                # Parse response
                try:
                    response_data = response.read().decode('utf-8')
                    return json.loads(response_data)
                except (json.JSONDecodeError, KeyError):
                    return None
        
        except urllib.error.HTTPError as e:
            if e.code == 401:
                raise RuntimeError("Authentication failed: Invalid API key")
            raise RuntimeError(f"Upload failed: {e.code} - {e.reason}")
        except urllib.error.URLError as e:
            raise RuntimeError(f"Upload failed: {e.reason}")
    
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
                    f"(retry {retry_display}). Next retry in {delay/1000:.0f}s. Error: {str(error)}"
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
            self.logger.info(f"[OK] Successfully uploaded {file_name} ({success_count} chunks)")
        
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
        # Send only the basename in X-File-Name header for server compatibility
        # (sanitize mode rejects paths with separators)
        base_name = os.path.basename(file_name)
        
        headers = {
            'Content-Type': 'application/octet-stream',
            'X-Chunk-Index': str(index),
            'X-File-Name': base_name,
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
            self.logger.info("[OK] Client storage closed")
    
    # Context manager support
    async def __aenter__(self):
        """Async context manager entry."""
        await self.initialize()
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit."""
        await self.close()
        return False
