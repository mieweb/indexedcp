"""
IndexedCP Python Client Implementation

This module provides a Python client for the IndexedCP file transfer system,
compatible with the Node.js server implementation.
"""

import os
import json
import requests
import sqlite3
import hashlib
import getpass
from pathlib import Path
from typing import Optional, Dict, Any, List
from dataclasses import dataclass


@dataclass
class ChunkRecord:
    """Represents a file chunk stored in the buffer."""
    id: str
    file_name: str
    chunk_index: int
    data: bytes


class IndexCPClient:
    """Python client for IndexedCP file transfer system."""
    
    def __init__(self, db_name: str = "indexcp", chunk_size: int = 1024 * 1024):
        """
        Initialize the IndexedCP client.
        
        Args:
            db_name: Name of the database for storing chunks
            chunk_size: Size of each chunk in bytes (default: 1MB)
        """
        self.db_name = db_name
        self.chunk_size = chunk_size
        self.api_key: Optional[str] = None
        self.db_path = self._get_db_path()
        self._init_db()
    
    def _get_db_path(self) -> Path:
        """Get the path for the SQLite database."""
        home_dir = Path.home()
        db_dir = home_dir / ".indexcp"
        db_dir.mkdir(exist_ok=True)
        return db_dir / f"{self.db_name}.db"
    
    def _init_db(self):
        """Initialize the SQLite database for chunk storage."""
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS chunks (
                    id TEXT PRIMARY KEY,
                    file_name TEXT NOT NULL,
                    chunk_index INTEGER NOT NULL,
                    data BLOB NOT NULL
                )
            """)
            conn.commit()
    
    def _prompt_for_api_key(self) -> str:
        """Prompt user for API key securely."""
        return getpass.getpass("Enter API key: ").strip()
    
    async def get_api_key(self) -> str:
        """Get API key from environment variable or user input."""
        if self.api_key:
            return self.api_key
        
        # Check environment variable first
        env_key = os.environ.get("INDEXCP_API_KEY")
        if env_key:
            self.api_key = env_key
            return self.api_key
        
        # Prompt user for API key
        self.api_key = self._prompt_for_api_key()
        return self.api_key
    
    def get_api_key_sync(self) -> str:
        """Synchronous version of get_api_key for CLI usage."""
        if self.api_key:
            return self.api_key
        
        # Check environment variable first
        env_key = os.environ.get("INDEXCP_API_KEY")
        if env_key:
            self.api_key = env_key
            return self.api_key
        
        # Prompt user for API key
        self.api_key = self._prompt_for_api_key()
        return self.api_key
    
    def add_file(self, file_path: str) -> int:
        """
        Add a file to the buffer by splitting it into chunks.
        
        Args:
            file_path: Path to the file to add
            
        Returns:
            Number of chunks created
            
        Raises:
            FileNotFoundError: If the file does not exist
            IOError: If there's an error reading the file
        """
        file_path = Path(file_path)
        if not file_path.exists():
            raise FileNotFoundError(f"File not found: {file_path}")
        
        chunk_count = 0
        
        with sqlite3.connect(self.db_path) as conn:
            with open(file_path, "rb") as f:
                while True:
                    chunk_data = f.read(self.chunk_size)
                    if not chunk_data:
                        break
                    
                    chunk_id = f"{file_path}-{chunk_count}"
                    
                    conn.execute(
                        "INSERT OR REPLACE INTO chunks (id, file_name, chunk_index, data) VALUES (?, ?, ?, ?)",
                        (chunk_id, str(file_path), chunk_count, chunk_data)
                    )
                    chunk_count += 1
            
            conn.commit()
        
        print(f"File {file_path} added to buffer with {chunk_count} chunks")
        return chunk_count
    
    def upload_buffered_files(self, server_url: str) -> Dict[str, str]:
        """
        Upload all buffered files to the server.
        
        Args:
            server_url: URL of the upload endpoint
            
        Returns:
            Dictionary mapping client filenames to server filenames
            
        Raises:
            requests.RequestException: If there's an error during upload
        """
        api_key = self.get_api_key_sync()
        
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.execute("SELECT * FROM chunks ORDER BY file_name, chunk_index")
            all_records = cursor.fetchall()
        
        print(f"Found {len(all_records)} buffered chunks")
        
        if not all_records:
            print("No buffered files to upload")
            return {}
        
        # Group records by file name
        file_groups: Dict[str, List[tuple]] = {}
        for record in all_records:
            file_name = record[1]  # file_name column
            if file_name not in file_groups:
                file_groups[file_name] = []
            file_groups[file_name].append(record)
        
        print(f"Grouped into {len(file_groups)} files: {list(file_groups.keys())}")
        
        upload_results = {}
        
        # Upload each file's chunks in order
        for file_name, chunks in file_groups.items():
            print(f"Uploading {file_name} with {len(chunks)} chunks...")
            
            # Sort chunks by index (already sorted by SQL query, but being explicit)
            chunks.sort(key=lambda x: x[2])  # chunk_index column
            
            server_filename = None
            
            for chunk_record in chunks:
                chunk_id, _, chunk_index, chunk_data = chunk_record
                print(f"Uploading chunk {chunk_index} for {file_name}")
                
                response_data = self.upload_chunk(
                    server_url, chunk_data, chunk_index, file_name, api_key
                )
                
                # Capture server-determined filename from first chunk response
                if response_data and response_data.get("actualFilename") and not server_filename:
                    server_filename = response_data["actualFilename"]
                
                # Remove uploaded chunk from buffer
                with sqlite3.connect(self.db_path) as conn:
                    conn.execute("DELETE FROM chunks WHERE id = ?", (chunk_id,))
                    conn.commit()
            
            # Store the mapping of client filename to server filename
            upload_results[file_name] = server_filename or Path(file_name).name
            
            if server_filename and server_filename != Path(file_name).name:
                print(f"Upload complete for {file_name} -> Server saved as: {server_filename}")
            else:
                print(f"Upload complete for {file_name}")
        
        return upload_results
    
    def upload_chunk(self, server_url: str, chunk_data: bytes, index: int, 
                    file_name: str, api_key: Optional[str] = None) -> Optional[Dict[str, Any]]:
        """
        Upload a single chunk to the server.
        
        Args:
            server_url: URL of the upload endpoint
            chunk_data: Raw chunk data
            index: Chunk index
            file_name: Original file name
            api_key: API key for authentication
            
        Returns:
            Response data from server, if any
            
        Raises:
            requests.RequestException: If upload fails
            ValueError: If authentication fails
        """
        if not api_key:
            api_key = self.get_api_key_sync()
        
        headers = {
            "Content-Type": "application/octet-stream",
            "X-Chunk-Index": str(index),
            "X-File-Name": file_name,
            "Authorization": f"Bearer {api_key}"
        }
        
        try:
            response = requests.post(server_url, data=chunk_data, headers=headers)
            
            if response.status_code == 401:
                raise ValueError("Authentication failed: Invalid API key")
            
            response.raise_for_status()
            
            # Try to parse response as JSON (new format) or fall back to text
            response_data = None
            content_type = response.headers.get("content-type", "")
            
            try:
                if "application/json" in content_type:
                    response_data = response.json()
                    
                    # Log server-determined filename if it differs from client filename
                    actual_filename = response_data.get("actualFilename")
                    if (actual_filename and actual_filename != file_name and 
                        actual_filename != Path(file_name).name):
                        print(f"Server used filename: {actual_filename} (client sent: {file_name})")
                else:
                    # Backward compatibility: plain text response
                    response_data = {"message": response.text}
            except (json.JSONDecodeError, ValueError):
                # If JSON parsing fails, fall back to treating as plain text
                response_data = {"message": response.text}
            
            return response_data
            
        except requests.RequestException as e:
            print(f"Upload failed: {e}")
            raise
    
    def buffer_and_upload(self, file_path: str, server_url: str):
        """
        Convenience method to buffer a file and immediately upload it.
        
        Args:
            file_path: Path to the file to upload
            server_url: URL of the upload endpoint
        """
        api_key = self.get_api_key_sync()
        
        # Create temporary chunks and upload immediately
        file_path = Path(file_path)
        if not file_path.exists():
            raise FileNotFoundError(f"File not found: {file_path}")
        
        chunk_index = 0
        
        with open(file_path, "rb") as f:
            while True:
                chunk_data = f.read(self.chunk_size)
                if not chunk_data:
                    break
                
                self.upload_chunk(server_url, chunk_data, chunk_index, str(file_path), api_key)
                chunk_index += 1
        
        print("Upload complete.")
    
    def get_buffered_files(self) -> List[str]:
        """
        Get list of files currently in the buffer.
        
        Returns:
            List of file names in the buffer
        """
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.execute("SELECT DISTINCT file_name FROM chunks")
            return [row[0] for row in cursor.fetchall()]
    
    def clear_buffer(self):
        """Clear all chunks from the buffer."""
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("DELETE FROM chunks")
            conn.commit()
        print("Buffer cleared")