#!/usr/bin/env python3
"""
IndexedCP Python Streaming Example

This example demonstrates streaming file upload similar to the JavaScript client-stream.js example.
"""

import sys
import os
from pathlib import Path

# Add the parent directory to Python path so we can import indexedcp
sys.path.insert(0, str(Path(__file__).parent.parent))

from indexedcp import IndexCPClient


class StreamingUploader:
    """Example class showing streaming-style upload functionality."""
    
    def __init__(self, server_url: str, chunk_size: int = 1024 * 1024):
        self.server_url = server_url
        self.client = IndexCPClient(chunk_size=chunk_size)
    
    def upload_file_streaming(self, file_path: str):
        """
        Upload a file using streaming approach (similar to JS client-stream.js).
        
        This method reads the file in chunks, buffers them temporarily,
        then uploads and removes each chunk immediately.
        """
        file_path = Path(file_path)
        if not file_path.exists():
            raise FileNotFoundError(f"File not found: {file_path}")
        
        print(f"Starting streaming upload of {file_path}")
        
        # Get API key
        api_key = self.client.get_api_key()
        
        chunk_index = 0
        uploaded_chunks = []
        
        # Read and upload file in chunks
        with open(file_path, "rb") as f:
            while True:
                chunk_data = f.read(self.client.chunk_size)
                if not chunk_data:
                    break
                
                print(f"Processing chunk {chunk_index} ({len(chunk_data)} bytes)")
                
                # Upload chunk immediately
                try:
                    response_data = self.client.upload_chunk(
                        self.server_url, chunk_data, chunk_index, str(file_path), api_key
                    )
                    uploaded_chunks.append({
                        'index': chunk_index,
                        'size': len(chunk_data),
                        'response': response_data
                    })
                    print(f"Successfully uploaded chunk {chunk_index}")
                    
                except Exception as e:
                    print(f"Failed to upload chunk {chunk_index}: {e}")
                    raise
                
                chunk_index += 1
        
        print(f"Upload complete! Uploaded {len(uploaded_chunks)} chunks")
        
        # Return upload summary
        total_size = sum(chunk['size'] for chunk in uploaded_chunks)
        return {
            'file_path': str(file_path),
            'total_chunks': len(uploaded_chunks),
            'total_size': total_size,
            'server_response': uploaded_chunks[0]['response'] if uploaded_chunks else None
        }


def main():
    """Example demonstrating streaming upload."""
    
    # Create a larger test file
    test_file = Path(__file__).parent / "large_test_file.txt"
    print(f"Creating test file: {test_file}")
    
    with open(test_file, "w") as f:
        # Create a ~5MB file
        for i in range(50000):
            f.write(f"This is line {i:05d} of the test file for streaming upload demo.\n")
    
    file_size = test_file.stat().st_size
    print(f"Created test file with size: {file_size:,} bytes")
    
    # Server URL (adjust as needed)
    server_url = "http://localhost:3000/upload"
    
    # Create streaming uploader with 1MB chunks
    uploader = StreamingUploader(server_url, chunk_size=1024 * 1024)
    
    try:
        # Attempt streaming upload
        print("\n=== Starting Streaming Upload ===")
        result = uploader.upload_file_streaming(str(test_file))
        
        print(f"\n=== Upload Results ===")
        print(f"File: {result['file_path']}")
        print(f"Total chunks: {result['total_chunks']}")
        print(f"Total size: {result['total_size']:,} bytes")
        
        if result['server_response']:
            print(f"Server response: {result['server_response']}")
        
    except Exception as e:
        print(f"\nUpload failed: {e}")
        print("\nTo test this example:")
        print("1. Start the IndexedCP server:")
        print("   cd ../.. && node bin/indexcp server 3000 ./uploads")
        print("2. Set your API key:")
        print("   export INDEXCP_API_KEY=your-api-key-here")
        print("3. Run this script again")
    
    finally:
        # Clean up test file
        if test_file.exists():
            test_file.unlink()
            print(f"\nCleaned up test file: {test_file}")


if __name__ == "__main__":
    main()