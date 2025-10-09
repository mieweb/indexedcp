#!/usr/bin/env python3
"""
IndexedCP Demo Client
Enhanced CLI client with detailed progress information
"""

import sys
import os
from pathlib import Path
import time

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from indexedcp import IndexCPClient


class ProgressClient(IndexCPClient):
    """Enhanced client with progress tracking."""
    
    def upload_chunk_with_progress(self, server_url: str, chunk_data: bytes, 
                                   index: int, file_name: str, total_chunks: int,
                                   api_key=None):
        """Upload a single chunk with progress display."""
        start_time = time.time()
        
        # Show progress
        progress = ((index + 1) / total_chunks) * 100
        bar_length = 40
        filled = int(bar_length * (index + 1) / total_chunks)
        bar = '█' * filled + '░' * (bar_length - filled)
        
        print(f"\r   [{bar}] {progress:.1f}% | Chunk {index + 1}/{total_chunks} | {len(chunk_data)} bytes", 
              end='', flush=True)
        
        # Upload the chunk
        result = self.upload_chunk(server_url, chunk_data, index, file_name, api_key)
        
        elapsed = time.time() - start_time
        
        return result, elapsed
    
    def upload_file_with_progress(self, file_path: str, server_url: str):
        """Upload a file with detailed progress tracking."""
        api_key = self.get_api_key()
        
        file_path = Path(file_path)
        if not file_path.exists():
            raise FileNotFoundError(f"❌ File not found: {file_path}")
        
        # Calculate total chunks
        file_size = file_path.stat().st_size
        total_chunks = (file_size + self.chunk_size - 1) // self.chunk_size
        
        print(f"\n📤 Uploading File")
        print(f"   File: {file_path.name}")
        print(f"   Size: {file_size:,} bytes ({file_size / (1024*1024):.2f} MB)")
        print(f"   Chunk Size: {self.chunk_size:,} bytes")
        print(f"   Total Chunks: {total_chunks}")
        print(f"\n⏳ Upload Progress:")
        
        chunk_index = 0
        total_time = 0
        
        with open(file_path, "rb") as f:
            while True:
                chunk_data = f.read(self.chunk_size)
                if not chunk_data:
                    break
                
                result, elapsed = self.upload_chunk_with_progress(
                    server_url, chunk_data, chunk_index, 
                    str(file_path), total_chunks, api_key
                )
                
                total_time += elapsed
                chunk_index += 1
        
        print("\n")  # New line after progress bar
        
        # Calculate statistics
        avg_time = total_time / total_chunks if total_chunks > 0 else 0
        throughput = file_size / total_time if total_time > 0 else 0
        
        print(f"\n✅ Upload Complete!")
        print(f"   Total Time: {total_time:.2f} seconds")
        print(f"   Average Time per Chunk: {avg_time:.3f} seconds")
        print(f"   Throughput: {throughput / (1024*1024):.2f} MB/s")


def main():
    """Main function for the demo client."""
    print("=" * 60)
    print("IndexedCP Demo Client")
    print("=" * 60)
    
    # Check arguments
    if len(sys.argv) < 2:
        print("\n❌ Usage: python client_demo.py <file_path> [chunk_size_kb]")
        print("\nExamples:")
        print("   python client_demo.py sample.txt")
        print("   python client_demo.py large_file.zip 512")
        print("\nNote: Make sure INDEXCP_API_KEY environment variable is set")
        print("      or you'll be prompted to enter it.")
        sys.exit(1)
    
    file_path = sys.argv[1]
    
    # Optional chunk size argument (in KB)
    chunk_size = 256 * 1024  # Default: 256KB
    if len(sys.argv) > 2:
        try:
            chunk_size = int(sys.argv[2]) * 1024
            print(f"\n📦 Using custom chunk size: {chunk_size // 1024} KB")
        except ValueError:
            print(f"\n⚠️  Invalid chunk size, using default: {chunk_size // 1024} KB")
    
    # Check if file exists
    if not Path(file_path).exists():
        print(f"\n❌ Error: File '{file_path}' not found!")
        sys.exit(1)
    
    # Server URL
    server_url = "http://localhost:3000/upload"
    
    print(f"\n🎯 Target Server: {server_url}")
    print(f"📦 Chunk Size: {chunk_size // 1024} KB")
    
    # Check for API key
    if not os.environ.get("INDEXCP_API_KEY"):
        print("\n⚠️  INDEXCP_API_KEY not found in environment variables")
        print("   You'll be prompted to enter it manually")
    
    print("=" * 60)
    
    try:
        # Create client
        client = ProgressClient(chunk_size=chunk_size)
        
        # Upload file
        client.upload_file_with_progress(file_path, server_url)
        
        print("\n" + "=" * 60)
        print("✨ Demo Complete!")
        print("   Check the './uploads' directory on the server")
        print("=" * 60)
        
    except KeyboardInterrupt:
        print("\n\n🛑 Upload cancelled by user")
        sys.exit(1)
    except Exception as e:
        print(f"\n\n❌ Error: {str(e)}")
        sys.exit(1)


if __name__ == "__main__":
    main()
