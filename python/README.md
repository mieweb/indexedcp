# IndexedCP Python Client

A Python implementation of the IndexedCP client for secure, efficient, and resumable file transfer. This client is compatible with the Node.js IndexedCP server.

## Features

- **Chunked file transfer** with configurable chunk sizes
- **SQLite-based buffering** for reliable, resumable uploads
- **API key authentication** for secure transfers
- **CLI and library interfaces** for flexibility
- **Cross-platform compatibility** (Windows, macOS, Linux)
- **Compatible with Node.js IndexedCP server**

## Installation

### From Source

```bash
git clone https://github.com/mieweb/IndexedCP.git
cd IndexedCP/python
pip install -r requirements.txt
```

### Dependencies

- Python 3.7+
- `requests` library for HTTP operations
- SQLite3 (included with Python)

## Quick Start

### Library Usage

```python
from indexedcp import IndexCPClient

# Create client
client = IndexCPClient()

# Add file to buffer
client.add_file('./myfile.txt')

# Upload to server
results = client.upload_buffered_files('http://localhost:3000/upload')
print(f"Upload results: {results}")

# Or upload directly without buffering
client.buffer_and_upload('./myfile.txt', 'http://localhost:3000/upload')
```

### CLI Usage

```bash
# Set API key (recommended)
export INDEXCP_API_KEY=your-api-key-here

# Add file to buffer
python3 bin/indexcp add ./myfile.txt

# List buffered files
python3 bin/indexcp list

# Upload buffered files
python3 bin/indexcp upload http://localhost:3000/upload

# Direct upload without buffering
python3 bin/indexcp buffer-and-upload ./myfile.txt http://localhost:3000/upload

# Clear buffer
python3 bin/indexcp clear
```

## API Reference

### IndexCPClient Class

#### Constructor

```python
IndexCPClient(db_name="indexcp", chunk_size=1024*1024)
```

- `db_name`: Name of the SQLite database for storing chunks
- `chunk_size`: Size of each chunk in bytes (default: 1MB)

#### Methods

##### `add_file(file_path: str) -> int`

Add a file to the buffer by splitting it into chunks.

- **file_path**: Path to the file to add
- **Returns**: Number of chunks created
- **Raises**: `FileNotFoundError` if file doesn't exist

##### `upload_buffered_files(server_url: str) -> Dict[str, str]`

Upload all buffered files to the server.

- **server_url**: URL of the upload endpoint
- **Returns**: Dictionary mapping client filenames to server filenames
- **Raises**: `requests.RequestException` for upload errors

##### `buffer_and_upload(file_path: str, server_url: str)`

Convenience method to buffer and immediately upload a file.

- **file_path**: Path to the file to upload
- **server_url**: URL of the upload endpoint

##### `get_buffered_files() -> List[str]`

Get list of files currently in the buffer.

- **Returns**: List of file paths in the buffer

##### `clear_buffer()`

Clear all chunks from the buffer.

##### `get_api_key_sync() -> str`

Get API key from environment variable or user input.

- **Returns**: API key string
- **Note**: Checks `INDEXCP_API_KEY` environment variable first, then prompts user

## Configuration

### API Key Authentication

The client supports multiple ways to provide API keys:

1. **Environment Variable (Recommended)**:
   ```bash
   export INDEXCP_API_KEY=your-secure-api-key
   ```

2. **Direct Assignment**:
   ```python
   client = IndexCPClient()
   client.api_key = "your-api-key"
   ```

3. **Interactive Prompt**: If no API key is set, the client will prompt you securely.

### Chunk Size

You can customize the chunk size for different use cases:

```python
# Small chunks for slow connections
client = IndexCPClient(chunk_size=64*1024)  # 64KB chunks

# Large chunks for fast connections
client = IndexCPClient(chunk_size=5*1024*1024)  # 5MB chunks
```

### Database Location

The client stores chunks in a SQLite database located at:
- Linux/macOS: `~/.indexcp/indexcp.db`
- Windows: `%USERPROFILE%\.indexcp\indexcp.db`

## Examples

### Basic Upload Example

```python
from indexedcp import IndexCPClient

def upload_example():
    client = IndexCPClient()
    
    # Add multiple files
    client.add_file('./document.pdf')
    client.add_file('./image.jpg')
    
    # List what's in buffer
    files = client.get_buffered_files()
    print(f"Files to upload: {files}")
    
    # Upload everything
    results = client.upload_buffered_files('http://localhost:3000/upload')
    
    for client_file, server_file in results.items():
        print(f"Uploaded: {client_file} -> {server_file}")

if __name__ == "__main__":
    upload_example()
```

### Streaming Upload Example

```python
from indexedcp import IndexCPClient

def streaming_upload(file_path, server_url):
    """Upload file in streaming fashion (chunk by chunk)."""
    client = IndexCPClient(chunk_size=1024*1024)  # 1MB chunks
    
    with open(file_path, 'rb') as f:
        chunk_index = 0
        while True:
            chunk_data = f.read(client.chunk_size)
            if not chunk_data:
                break
            
            # Upload chunk immediately
            client.upload_chunk(server_url, chunk_data, chunk_index, file_path)
            print(f"Uploaded chunk {chunk_index}")
            chunk_index += 1
    
    print("Streaming upload complete!")

# Usage
streaming_upload('./large_file.zip', 'http://localhost:3000/upload')
```

## Testing

Run the test suite:

```bash
python3 test_client.py
```

Run integration tests (requires IndexedCP server):

```bash
python3 test_integration.py
```

## Compatibility

This Python client is fully compatible with the Node.js IndexedCP server. It implements the same protocol:

- HTTP POST requests to upload endpoint
- `Authorization: Bearer <api-key>` header for authentication
- `X-Chunk-Index` header for chunk sequencing
- `X-File-Name` header for filename information
- `Content-Type: application/octet-stream` for binary data

## Error Handling

The client handles various error conditions:

- **File not found**: Raises `FileNotFoundError`
- **Network errors**: Raises `requests.RequestException`
- **Authentication errors**: Raises `ValueError` with clear message
- **Server errors**: Propagates HTTP status codes and error messages

## Contributing

Contributions are welcome! Please ensure:

1. Code follows Python PEP 8 style guidelines
2. All tests pass (`python3 test_client.py`)
3. New features include appropriate tests
4. Documentation is updated for API changes

## License

MIT License - see the main repository LICENSE file for details.