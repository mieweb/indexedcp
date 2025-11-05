import os
import secrets
import time
from pathlib import Path
from typing import Optional, List, Dict, Any, Callable

from fastapi import FastAPI, Request, Response, HTTPException, Depends, Header
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware

from .logger import create_logger


class IndexedCPServer:
    """
    Basic IndexedCP server for file uploads without encryption.
    """
    
    def __init__(
        self,
        upload_dir: str = "./uploads",
        port: int = 3000,
        api_keys: Optional[List[str]] = None,
        path_mode: str = "ignore",
        log_level: Optional[str] = None,
        encryption: bool = False,
        **options
    ):
        """
        Initialize IndexedCP server.
        
        Args:
            upload_dir: Directory for uploaded files (default: ./uploads)
            port: server port (default: 3000)
            api_keys: List of valid API keys (generates one if not provided)
            path_mode: Path handling mode - 'ignore' (default), 'sanitize', 'allow-paths'
            log_level: Logging level (DEBUG, INFO, WARN, ERROR)
            encryption: Enable encryption (not supported in basic version)
            **options: Additional server options
        """
        self.upload_dir = Path(upload_dir)
        self.port = port
        
        # API key setup (generate if not provided)
        if api_keys is None or len(api_keys) == 0:
            self.api_keys = [self._generate_api_key()]
        else:
            self.api_keys = api_keys
        
        # Path handling mode
        valid_modes = ['sanitize', 'ignore', 'allow-paths']
        if path_mode not in valid_modes:
            raise ValueError(
                f"Invalid path_mode: {path_mode}. "
                f"Valid modes: {', '.join(valid_modes)}"
            )
        self.path_mode = path_mode
        
        # Logger configuration
        self.log_level = log_level or os.environ.get('INDEXEDCP_LOG_LEVEL', 'INFO')
        self.logger = create_logger('IndexedCP.Server', level=self.log_level)
        
        # Track upload sessions (client filename -> actual filename)
        self.upload_sessions: Dict[str, str] = {}
        
        # Encryption not supported in basic implementation
        self.encryption = encryption
        if self.encryption:
            raise NotImplementedError(
                "Encryption not supported in basic server implementation. "
                "Set encryption=False or use EncryptedServer (coming soon)."
            )
        
        # Ensure upload directory exists
        self.upload_dir.mkdir(parents=True, exist_ok=True)
    
    def _generate_api_key(self) -> str:
        """Generate a secure random API key."""
        return secrets.token_hex(32)
    
    def create_app(self) -> FastAPI:
        """
        Create and configure FastAPI application.
        
        Returns:
            FastAPI: Configured FastAPI application instance
        """
        app = FastAPI(
            title="IndexedCP Server",
            description="File upload server with chunked upload support",
            version="0.1.0"
        )
        
        # Add CORS middleware for browser clients
        app.add_middleware(
            CORSMiddleware,
            allow_origins=["*"],
            allow_credentials=True,
            allow_methods=["GET", "POST", "OPTIONS"],
            allow_headers=["*"],
        )
        
        # Register routes
        @app.post("/upload")
        async def upload_endpoint(
            request: Request,
            api_key: str = Depends(self._verify_api_key)
        ):
            """Handle file upload endpoint."""
            return await self.handle_upload(request)
        
        @app.get("/health")
        async def health_check():
            """Health check endpoint."""
            return {"status": "ok", "service": "IndexedCP Server"}
        
        return app
    
    async def _verify_api_key(
        self,
        authorization: Optional[str] = Header(None)
    ) -> str:
        """
        Verify API key from Authorization header.
        
        Args:
            authorization: Authorization header value
        
        Returns:
            str: Verified API key
        
        Raises:
            HTTPException: If API key is invalid or missing
        """
        if not authorization:
            raise HTTPException(
                status_code=401,
                detail="Invalid or missing API key"
            )
        
        # Extract token from "Bearer <token>" format
        if authorization.startswith("Bearer "):
            provided_key = authorization[7:]
        else:
            provided_key = authorization
        
        if provided_key not in self.api_keys:
            raise HTTPException(
                status_code=401,
                detail="Invalid or missing API key"
            )
        
        return provided_key
    
    async def handle_upload(self, request: Request) -> JSONResponse:
        """
        Handle chunked file upload.
        
        Args:
            request: FastAPI request object
        
        Returns:
            JSONResponse: Upload confirmation with file metadata
        """
        # Extract headers
        chunk_index = request.headers.get('x-chunk-index', '0')
        client_filename = request.headers.get('x-file-name', 'uploaded_file.txt')
        
        try:
            chunk_index = int(chunk_index)
        except ValueError:
            chunk_index = 0
        
        # Determine output file based on path mode
        try:
            output_file, actual_filename = self._determine_output_path(
                client_filename,
                chunk_index
            )
        except ValueError as e:
            return JSONResponse(
                status_code=400,
                content={
                    "error": "Invalid filename",
                    "message": str(e)
                }
            )
        except PermissionError as e:
            return JSONResponse(
                status_code=403,
                content={
                    "error": "Access denied: invalid path",
                    "message": str(e)
                }
            )
        
        # Read chunk data from request body
        try:
            chunk_data = await request.body()
            
            # Write chunk to file (append mode)
            with open(output_file, 'ab') as f:
                f.write(chunk_data)
            
            self.logger.info(
                f"Chunk {chunk_index} received for {client_filename} -> {actual_filename}"
            )
            
            return JSONResponse(
                status_code=200,
                content={
                    "message": "Chunk received",
                    "actualFilename": actual_filename,
                    "chunkIndex": chunk_index,
                    "clientFilename": client_filename
                }
            )
        
        except Exception as error:
            self.logger.error(f"Upload error: {error}")
            return JSONResponse(
                status_code=500,
                content={
                    "error": "Upload error",
                    "message": str(error)
                }
            )
    
    def _determine_output_path(
        self,
        client_filename: str,
        chunk_index: int
    ) -> tuple[Path, str]:
        """
        Determine output file path based on path mode.
        
        Args:
            client_filename: Filename from client
            chunk_index: Chunk index number
        
        Returns:
            tuple: (output_file_path, actual_filename)
        
        Raises:
            ValueError: If filename is invalid
            PermissionError: If path traversal attempt detected
        """
        if self.path_mode == "ignore":
            # Mode: ignore - Generate unique filename with full path preserved
            return self._handle_ignore_mode(client_filename, chunk_index)
        
        elif self.path_mode == "allow-paths":
            # Mode: allow-paths - Allow subdirectories from client
            return self._handle_allow_paths_mode(client_filename)
        
        else:  # sanitize mode (default)
            # Mode: sanitize - Strip paths, prevent overwrites
            return self._handle_sanitize_mode(client_filename, chunk_index)
    
    def _handle_ignore_mode(
        self,
        client_filename: str,
        chunk_index: int
    ) -> tuple[Path, str]:
        """
        Handle filename generation in 'ignore' mode.
        
        Generates unique filename with timestamp and preserves original path.
        Uses session tracking to ensure all chunks use the same filename.
        
        Args:
            client_filename: Original filename from client
            chunk_index: Chunk index number
        
        Returns:
            tuple: (output_file_path, actual_filename)
        """
        # Check if we already have a session for this file
        if client_filename in self.upload_sessions:
            # Use the same filename from the first chunk
            actual_filename = self.upload_sessions[client_filename]
            output_file = self.upload_dir / actual_filename
            return output_file, actual_filename
        
        # First chunk - generate unique filename
        timestamp = int(time.time() * 1000)
        random_hex = secrets.token_hex(4)
        
        # Preserve full path by replacing separators with single underscore
        # Strip leading ./ or .\
        full_path = client_filename
        for prefix in ['./', '.\\']:
            if full_path.startswith(prefix):
                full_path = full_path[len(prefix):]
        
        # Replace path separators with single underscore
        full_path = full_path.replace('/', '_').replace('\\', '_')
        
        # Extract extension
        path_obj = Path(full_path)
        ext = path_obj.suffix
        name_without_ext = path_obj.stem
        
        # Sanitize to be filesystem-safe:
        # Keep letters, numbers, underscores, dots, and dashes
        # Replace all other characters with dash
        safe_name = ''.join(
            c if c.isalnum() or c in '._-' else '-'
            for c in name_without_ext
        )
        
        # Format: <timestamp>_<random>_<full-path-with-underscores>.<ext>
        proposed_name = f"{timestamp}_{random_hex}_{safe_name}{ext}"
        
        # Check filename length (most filesystems support 255 chars)
        MAX_FILENAME_LENGTH = 255
        if len(proposed_name) > MAX_FILENAME_LENGTH:
            # Truncate the safe name part to fit
            prefix_length = len(f"{timestamp}_{random_hex}_")
            max_safe_name_length = MAX_FILENAME_LENGTH - prefix_length - len(ext)
            truncated_name = safe_name[:max_safe_name_length]
            proposed_name = f"{timestamp}_{random_hex}_{truncated_name}{ext}"
        
        actual_filename = proposed_name
        
        # Store the filename for subsequent chunks
        self.upload_sessions[client_filename] = actual_filename
        
        output_file = self.upload_dir / actual_filename
        
        return output_file, actual_filename
    
    def _handle_allow_paths_mode(self, client_filename: str) -> tuple[Path, str]:
        """
        Handle filename in 'allow-paths' mode.
        
        Allows subdirectories but protects against traversal attacks.
        
        Args:
            client_filename: Filename from client
        
        Returns:
            tuple: (output_file_path, actual_filename)
        
        Raises:
            ValueError: If filename contains traversal attempts
            PermissionError: If resolved path is outside upload directory
        """
        # Strip leading ./ or .\
        cleaned_filename = client_filename
        for prefix in ['./', '.\\']:
            if cleaned_filename.startswith(prefix):
                cleaned_filename = cleaned_filename[len(prefix):]
        
        # Reject traversal attempts and absolute paths
        has_traversal = '..' in cleaned_filename
        has_absolute = (
            cleaned_filename.startswith('/') or
            cleaned_filename.startswith('\\\\') or
            (len(cleaned_filename) > 1 and cleaned_filename[1] == ':')  # Windows drive
        )
        
        if has_traversal or has_absolute:
            self.logger.error(
                f"Security: Rejected filename with traversal/absolute path: {client_filename}"
            )
            raise ValueError(
                "Filename must not contain traversal sequences or absolute paths"
            )
        
        # Normalize path separators
        actual_filename = cleaned_filename.replace('\\', '/')
        output_file = self.upload_dir / actual_filename
        
        # Security: Verify the resolved path is inside upload_dir
        try:
            resolved_output = output_file.resolve()
            resolved_upload_dir = self.upload_dir.resolve()
            
            # Check if output file is within upload directory
            if not str(resolved_output).startswith(str(resolved_upload_dir)):
                self.logger.error(
                    f"Security: Path traversal attempt blocked: {client_filename}"
                )
                raise PermissionError("Access denied: invalid path")
        except Exception as e:
            self.logger.error(f"Security: Path validation failed: {e}")
            raise PermissionError("Access denied: invalid path")
        
        # Create subdirectories if needed
        output_file.parent.mkdir(parents=True, exist_ok=True)
        
        return output_file, actual_filename
    
    def _handle_sanitize_mode(
        self,
        client_filename: str,
        chunk_index: int
    ) -> tuple[Path, str]:
        """
        Handle filename in 'sanitize' mode.
        
        Strips paths and prevents overwrites using session tracking.
        Matches JavaScript implementation: validates paths THEN extracts basename.
        
        Args:
            client_filename: Filename from client
            chunk_index: Chunk index number
        
        Returns:
            tuple: (output_file_path, actual_filename)
        
        Raises:
            ValueError: If filename is invalid after sanitization
        """
        # Strip common relative path prefixes for validation
        cleaned_filename = client_filename
        for prefix in ['./', '.\\']:
            if cleaned_filename.startswith(prefix):
                cleaned_filename = cleaned_filename[len(prefix):]
        
        # Validate the original filename - reject paths with separators or traversal
        # This is done BEFORE extracting basename to match JS behavior
        has_path_separators = '/' in cleaned_filename or '\\' in cleaned_filename
        has_traversal = '..' in client_filename
        has_absolute_path = (
            client_filename.startswith('/') or
            client_filename.startswith('\\\\') or
            (len(client_filename) > 1 and client_filename[1] == ':')
        )
        
        if has_path_separators or has_traversal or has_absolute_path:
            self.logger.error(
                f"Security: Rejected filename with path components: {client_filename}"
            )
            raise ValueError(
                "Filename must not contain path separators or traversal sequences"
            )
        
        # Now extract basename for safety (in case of custom generators)
        actual_filename = Path(client_filename).name
        
        # Validate that we have a valid filename after extraction
        if not actual_filename or actual_filename in ['.', '..'] or len(actual_filename) == 0:
            raise ValueError("Invalid filename")
        
        # Check if we have a session for this file
        is_first_chunk = chunk_index == 0
        
        if client_filename in self.upload_sessions:
            # Use the same filename from the first chunk
            actual_filename = self.upload_sessions[client_filename]
        else:
            # First chunk - check for overwrites and create session
            output_file = self.upload_dir / actual_filename
            
            if output_file.exists():
                # Add timestamp to prevent overwrite
                path_obj = Path(actual_filename)
                ext = path_obj.suffix
                base = path_obj.stem
                timestamp = int(time.time() * 1000)
                actual_filename = f"{base}_{timestamp}{ext}"
            
            # Store the filename for subsequent chunks
            self.upload_sessions[client_filename] = actual_filename
        
        output_file = self.upload_dir / actual_filename
        
        # Security: Verify the resolved path is inside upload_dir
        try:
            resolved_output = output_file.resolve()
            resolved_upload_dir = self.upload_dir.resolve()
            
            if not str(resolved_output).startswith(str(resolved_upload_dir)):
                self.logger.error(
                    f"Security: Path traversal attempt blocked: {client_filename}"
                )
                raise PermissionError("Access denied: invalid path")
        except Exception as e:
            self.logger.error(f"Security: Path validation failed: {e}")
            raise PermissionError("Access denied: invalid path")
        
        return output_file, actual_filename
    
    def get_server_info(self) -> Dict[str, Any]:
        """
        Get server configuration information.
        
        Returns:
            dict: Server configuration details
        """
        return {
            "port": self.port,
            "upload_dir": str(self.upload_dir),
            "path_mode": self.path_mode,
            "api_keys_count": len(self.api_keys),
            "encryption": self.encryption,
            "active_sessions": len(self.upload_sessions)
        }
    
    def clear_sessions(self) -> None:
        """Clear upload session tracking."""
        self.upload_sessions.clear()
        self.logger.info("Cleared upload sessions")
