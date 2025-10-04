"""
IndexedCP Python Client Implementation

This module provides a Python client for the IndexedCP file transfer system,
compatible with the Node.js server implementation. Now uses IndexedDB-like storage
for better compatibility with the JavaScript version.
"""

import os
import json
import requests
import getpass
from pathlib import Path
from typing import Optional, Dict, Any, List
from dataclasses import dataclass

# Import our IndexedDB-like interface
from .indexeddb import openDB


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
        self.store_name = "chunks"
        self.api_key: Optional[str] = None
        self.db = None
        self._init_db()
    
    def _init_db(self):
        """Initialize the IndexedDB-like database for chunk storage."""
        def upgrade_db(db):
            if 'chunks' not in db.object_store_names:
                db.create_object_store('chunks', {'keyPath': 'id', 'autoIncrement': True})
        
        self.db = openDB(self.db_name, 1, upgrade_db)
    
    def _prompt_for_api_key(self) -> str:
        """Prompt user for API key securely."""
        return getpass.getpass("Enter API key: ").strip()
    
    def get_api_key(self) -> str:
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
        
        with open(file_path, "rb") as f:
            while True:
                chunk_data = f.read(self.chunk_size)
                if not chunk_data:
                    break
                
                chunk_id = f"{file_path}-{chunk_count}"
                
                # Store chunk using IndexedDB-like interface
                chunk_record = {
                    'id': chunk_id,
                    'fileName': str(file_path),
                    'chunkIndex': chunk_count,
                    'data': chunk_data
                }
                
                self.db.add(self.store_name, chunk_record)
                chunk_count += 1
        
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
        api_key = self.get_api_key()
        
        # Get all records using IndexedDB-like interface
        all_records = self.db.get_all(self.store_name)
        
        print(f"Found {len(all_records)} buffered chunks")
        
        if not all_records:
            print("No buffered files to upload")
            return {}
        
        # Group records by file name
        file_groups: Dict[str, List[dict]] = {}
        for record in all_records:
            file_name = record['fileName']
            if file_name not in file_groups:
                file_groups[file_name] = []
            file_groups[file_name].append(record)
        
        print(f"Grouped into {len(file_groups)} files: {list(file_groups.keys())}")
        
        upload_results = {}
        
        # Upload each file's chunks in order
        for file_name, chunks in file_groups.items():
            print(f"Uploading {file_name} with {len(chunks)} chunks...")
            
            # Sort chunks by index
            chunks.sort(key=lambda x: x['chunkIndex'])
            
            server_filename = None
            
            for chunk_record in chunks:
                chunk_id = chunk_record['id']
                chunk_index = chunk_record['chunkIndex'] 
                chunk_data = chunk_record['data']
                
                print(f"Uploading chunk {chunk_index} for {file_name}")
                
                response_data = self.upload_chunk(
                    server_url, chunk_data, chunk_index, file_name, api_key
                )
                
                # Capture server-determined filename from first chunk response
                if response_data and response_data.get("actualFilename") and not server_filename:
                    server_filename = response_data["actualFilename"]
                
                # Remove uploaded chunk from buffer
                self.db.delete(self.store_name, chunk_id)
            
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
            api_key = self.get_api_key()
        
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
            error_msg = f"Failed to upload chunk {index} for file '{file_name}': {str(e)}"
            print(error_msg)
            raise requests.RequestException(error_msg) from e
    
    def buffer_and_upload(self, file_path: str, server_url: str):
        """
        Convenience method to buffer a file and immediately upload it.
        
        Args:
            file_path: Path to the file to upload
            server_url: URL of the upload endpoint
        """
        api_key = self.get_api_key()
        
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
        all_records = self.db.get_all(self.store_name)
        file_names = set()
        for record in all_records:
            file_names.add(record['fileName'])
        return list(file_names)
    
    def clear_buffer(self):
        """Clear all chunks from the buffer."""
        # Get object store and clear it
        transaction = self.db.transaction([self.store_name], 'readwrite')
        store = transaction.object_store(self.store_name)
        store.clear()
        print("Buffer cleared")