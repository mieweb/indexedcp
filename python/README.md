
# IndexedCP - Python Implementation

A minimal file upload system with optional storage backends, ported from Node.js to Python.

## Features

- **Client & Server**: Complete file transfer system
- **Path Security**: Three modes (sanitize, ignore, allow-paths)
- **Chunked Upload**: Support for large file uploads
- **API Authentication**: Secure API key-based auth
- **Retry Logic**: Exponential backoff for failed uploads
- **Offline Support**: SQLite-backed buffering
- **Minimal Code**: Simple, focused implementation

## Installation

### Using pip

```bash
cd python
pip install -e .
```

### Development Setup

```bash
cd python
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
pip install -r requirements-dev.txt
```

## Quick Start

### Server Usage

Create a basic upload server with FastAPI:

```python
from indexedcp import IndexedCPServer
import uvicorn

# Create server
server = IndexedCPServer(
    upload_dir="./uploads",
    api_keys=["your-secure-api-key"],
    path_mode="ignore",  # or "sanitize", "allow-paths"
    port=3000
)

# Create FastAPI app
app = server.create_app()

# Run server
if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=3000)
```

#### Server Path Modes

**`ignore` (Default - Unique Filenames)**
- Generates unique filename with timestamp + random
- Preserves original path as underscores
- Best for: Audit trails, traceability

```python
server = IndexedCPServer(
    upload_dir="./uploads",
    path_mode="ignore"
)
# Client sends: "reports/2024/data.csv"
# Server saves: "./uploads/1730728950_a1b2c3d4_reports_2024_data.csv"
```

**`sanitize` (High Security)**
- Strips all directory paths
- Only uses base filename
- Rejects path separators and traversal attempts
- Best for: Untrusted clients, public uploads

```python
server = IndexedCPServer(
    upload_dir="./uploads",
    path_mode="sanitize"
)
# Client sends: "reports/2024/data.csv"
# Server saves: "./uploads/data.csv"
```

**`allow-paths` (Subdirectories)**
- Allows clients to create subdirectories
- Still protects against traversal attacks
- Best for: Trusted clients, organized uploads

```python
server = IndexedCPServer(
    upload_dir="./uploads",
    path_mode="allow-paths"
)
# Client sends: "reports/2024/data.csv"
# Server saves: "./uploads/reports/2024/data.csv"
```

#### Server Configuration

```python
IndexedCPServer(
    upload_dir="./uploads",        # Upload directory path
    port=3000,                     # Server port
    api_keys=["key1", "key2"],     # List of valid API keys
    path_mode="sanitize",          # Path handling mode
    log_level="INFO",              # Logging level
    encryption=False               # Encryption (not yet implemented)
)
```

#### Server API Methods

```python
server = IndexedCPServer(upload_dir="./uploads", api_keys=["test-key"])

# Create FastAPI application
app = server.create_app()

# Get server information
info = server.get_server_info()
print(info)
# {
#   "port": 3000,
#   "upload_dir": "./uploads",
#   "path_mode": "sanitize",
#   "api_keys_count": 1,
#   "encryption": False,
#   "active_sessions": 0
# }

# Clear upload sessions (for cleanup)
server.clear_sessions()
```

#### Server Endpoints

| Endpoint | Method | Auth | Description |
|----------|--------|------|-------------|
| `/upload` | POST | Yes | Upload file chunks |
| `/health` | GET | No | Health check |

**Upload Request:**
```bash
curl -X POST http://localhost:3000/upload \
  -H "Authorization: Bearer your-api-key" \
  -H "X-Chunk-Index: 0" \
  -H "X-File-Name: document.pdf" \
  --data-binary @chunk_0.bin
```

**Upload Response:**
```json
{
  "message": "Chunk received",
  "actualFilename": "document.pdf",
  "chunkIndex": 0,
  "clientFilename": "document.pdf"
}
```

### Logger Usage

```python
from indexedcp import create_logger

# Create a logger with default INFO level
logger = create_logger("IndexedCP.Client")
logger.info("Client initialized")

# Create a logger with specific level
logger = create_logger("IndexedCP.Server", level="DEBUG")
logger.debug("Debug information")
logger.info("Server started")
logger.warning("Warning message")
logger.error("Error occurred")

# Use environment variable for log level
# Set INDEXEDCP_LOG_LEVEL=DEBUG in your environment
import os
os.environ['INDEXEDCP_LOG_LEVEL'] = 'DEBUG'
logger = create_logger("IndexedCP.Module")
```

### Storage Usage

IndexedCP provides a pluggable storage abstraction layer for persistent key-value storage. The default implementation uses SQLite for ACID-compliant, thread-safe persistence.

```python
from indexedcp import create_storage
import asyncio

async def main():
    # Create SQLite storage (default)
    storage = create_storage('sqlite', db_path='./data.db')
    
    # Initialize storage (creates tables, etc.)
    await storage.initialize()
    
    # Save data
    await storage.save('user:123', {
        'name': 'Alice',
        'email': 'alice@example.com',
        'age': 30
    })
    
    # Load data
    user_data = await storage.load('user:123')
    print(f"User: {user_data['name']}")
    
    # Check existence
    exists = await storage.exists('user:123')
    print(f"User exists: {exists}")
    
    # List all keys
    all_keys = await storage.list()
    print(f"All keys: {all_keys}")
    
    # Load all data
    all_data = await storage.load_all()
    print(f"Total items: {len(all_data)}")
    
    # Delete data
    deleted = await storage.delete('user:123')
    print(f"Deleted: {deleted}")
    
    # Close storage
    await storage.close()


# Run with asyncio
asyncio.run(main())
```

#### Using Context Manager

The storage supports async context managers for automatic resource management:

```python
from indexedcp import SQLiteStorage

async def main():
    async with SQLiteStorage(db_path='./data.db') as storage:
        await storage.save('key', {'value': 'data'})
        data = await storage.load('key')
        print(data)
    # Storage automatically closed after context

asyncio.run(main())
```

#### Factory Pattern

Create storage instances using the factory function:

```python
from indexedcp import create_storage

# SQLite storage (default)
storage = create_storage('sqlite', db_path='./mydata.db', table_name='custom_table')

# With custom options
storage = create_storage('sqlite', 
    db_path='./app.db',
    table_name='app_storage',
    log_level='DEBUG'
)
```

### Storage API

All storage implementations follow the `BaseStorage` abstract interface:

| Method | Description | Returns |
|--------|-------------|---------|
| `initialize()` | Setup storage backend | `None` |
| `save(key, data)` | Store data dictionary | `None` |
| `load(key)` | Retrieve data by key | `Dict \| None` |
| `load_all()` | Retrieve all stored data | `List[Dict]` |
| `delete(key)` | Remove data by key | `bool` |
| `exists(key)` | Check if key exists | `bool` |
| `list()` | List all keys | `List[str]` |
| `close()` | Cleanup resources | `None` |

### Advanced Storage Features

#### SQLite-Specific Methods

```python
from indexedcp import SQLiteStorage

async def main():
    storage = SQLiteStorage(db_path='./data.db')
    await storage.initialize()
    
    # Count total items
    count = await storage.count()
    print(f"Total items: {count}")
    
    # Cleanup old entries (older than 30 days)
    max_age = 30 * 24 * 60 * 60  # 30 days in seconds
    deleted_count = await storage.cleanup_old(max_age)
    print(f"Cleaned up {deleted_count} old entries")
    
    await storage.close()

asyncio.run(main())
```

### Client Usage

IndexedCP client provides file buffering and upload queue management with SQLite storage for offline operation.

```python
from indexedcp import IndexedCPClient
import asyncio

async def main():
    # Create client with configuration
    client = IndexedCPClient(
        server_url="http://localhost:3000",
        api_key="your-api-key",
        storage_path="./client-db.sqlite",
        chunk_size=1024 * 1024,  # 1MB chunks
        max_retries=5,  # Maximum retry attempts (default: infinite)
        initial_retry_delay=1.0,  # Initial retry delay in seconds
        max_retry_delay=60.0,  # Maximum retry delay in seconds
        retry_multiplier=2.0  # Exponential backoff multiplier
    )
    
    # Initialize storage
    await client.initialize()
    
    # Add files to upload queue (works offline)
    await client.add_file("./document.pdf")
    await client.add_file("./image.jpg")
    
    # Upload all buffered files
    result = await client.upload_buffered_files()
    print(f"Upload results: {result}")
    
    # Close client
    await client.close()

asyncio.run(main())
```

#### Upload Features

**Retry Logic with Exponential Backoff:**
```python
client = IndexedCPClient(
    server_url="http://localhost:3000",
    api_key="your-key",
    max_retries=5,  # Retry up to 5 times
    initial_retry_delay=1.0,  # Start with 1 second delay
    max_retry_delay=60.0,  # Cap at 60 seconds
    retry_multiplier=2.0  # Double delay each time (1s, 2s, 4s, 8s, 16s...)
)
```

**Progress Callbacks:**
```python
def on_progress(event):
    print(f"Chunk {event['chunkIndex']} for {event['fileName']}: {event['status']}")
    if event['status'] == 'failed':
        print(f"  Retry {event['retryCount']}, next in {event['nextRetryIn']/1000}s")

client = IndexedCPClient(
    server_url="http://localhost:3000",
    api_key="your-key",
    on_upload_progress=on_progress
)
```

**Background Upload:**
```python
async def main():
    client = IndexedCPClient(
        server_url="http://localhost:3000",
        api_key="your-key"
    )
    await client.initialize()
    
    # Add files to queue
    await client.add_file("./large-file.mp4")
    
    # Start background upload (non-blocking)
    await client.start_upload_background(check_interval=5.0)
    
    # Do other work while upload happens in background
    await asyncio.sleep(30)
    
    # Stop background upload
    await client.stop_upload_background()
    await client.close()

asyncio.run(main())
```

**Context Manager:**
```python
async def main():
    async with IndexedCPClient(
        server_url="http://localhost:3000",
        api_key="your-key"
    ) as client:
        await client.add_file("./file.txt")
        await client.upload_buffered_files()
    # Client automatically closed

asyncio.run(main())
```

### Client API

| Method | Description | Returns |
|--------|-------------|---------|
| `initialize()` | Setup storage and client | `None` |
| `add_file(filepath)` | Add file to upload queue | `int` (chunk count) |
| `upload_buffered_files(server_url)` | Upload all queued files | `Dict[str, str]` |
| `start_upload_background(server_url, check_interval)` | Start background upload | `None` |
| `stop_upload_background()` | Stop background upload | `None` |
| `close()` | Cleanup resources | `None` |

### Configuration Options

#### Client Constructor

```python
IndexedCPClient(
    server_url=None,           # Server URL for uploads
    api_key=None,              # API key (or set INDEXEDCP_API_KEY env var)
    storage_path=None,         # SQLite path (default: ~/.indexcp/db/client.db)
    chunk_size=1024*1024,      # Chunk size in bytes (default: 1MB)
    encryption=False,          # Encryption support (not yet implemented)
    log_level=None,            # Log level (or set INDEXEDCP_LOG_LEVEL env var)
    max_retries=float('inf'),  # Maximum retry attempts (default: infinite)
    initial_retry_delay=1.0,   # Initial retry delay in seconds
    max_retry_delay=60.0,      # Maximum retry delay in seconds
    retry_multiplier=2.0,      # Exponential backoff multiplier
    on_upload_progress=None,   # Callback(event) for progress updates
    on_upload_error=None,      # Callback(error) for errors
    on_upload_complete=None    # Callback(summary) for completion
)
```

## Features

### Upload Functionality

-  **Chunked uploads** with configurable chunk size
-  **Retry logic** with exponential backoff
-  **Progress tracking** via callbacks
-  **Session tracking** for multi-chunk files
-  **Background upload** with automatic retry
-  **Error handling** with detailed error history
-  **Offline support** with SQLite buffering
-  **Status tracking** (pending → uploaded → confirmed)

### Retry Mechanism

The client implements exponential backoff retry logic:

1. **First failure**: Retry after 1 second (initial_retry_delay)
2. **Second failure**: Retry after 2 seconds (1 × 2^1)
3. **Third failure**: Retry after 4 seconds (1 × 2^2)
4. **Fourth failure**: Retry after 8 seconds (1 × 2^3)
5. **Continues** until max_retry_delay (60s) or max_retries reached

Each chunk tracks:
- Retry count
- Last attempt timestamp
- Next retry time
- Error history (last 5 errors)

## Project Structure

```
python/
├── src/
│   └── indexedcp/              # Main package
│       ├── __init__.py         # Package exports
│       ├── logger.py           # Logging utilities
│       ├── client.py           # Client implementation
│       ├── server.py           # Server implementation
│       └── storage/            # Storage abstraction layer
│           ├── __init__.py
│           ├── base_storage.py     # Abstract base class
│           └── sqlite_storage.py   # SQLite implementation
├── tests/                      # Test files
│   ├── test_client.py          # Client unit tests
│   ├── test_server.py          # Server unit tests
│   └── test_integration.py     # Integration tests (15 tests)
├── examples/                   # Demo scripts
│   ├── server_demo.py          # Interactive server demo
│   ├── client_demo.py          # Interactive client demo
│   ├── README.md               # Demo documentation
│   ├── QUICKSTART.md           # Quick command reference
│   └── DATABASE_STRUCTURE.md   # Database explanation
├── docs/                       # Documentation
├── pyproject.toml              # Project metadata
├── requirements.txt            # Runtime dependencies
└── requirements-dev.txt        # Development dependencies
```

## Running the Demo

See the complete client-server demonstration in action:

```bash
# Terminal 1 - Start the server
cd python
source venv/bin/activate
python examples/server_demo.py

# Terminal 2 - Run the client demo
cd python
source venv/bin/activate
python examples/client_demo.py
```

The demo showcases:
- Simple file upload
- Multiple files batch upload
- Large file chunking (3.5MB → 4 chunks)
- Background upload with auto-retry
- Database inspection pauses to view stored chunks

For detailed instructions, see `examples/README.md`

## Development

### Run Tests

```bash
# Run all tests
pytest

# Run specific test file
pytest tests/test_client_upload.py

# Run with verbose output
pytest -v

# Run with coverage
pytest --cov=indexedcp
```

### Testing Upload Functionality

The upload tests include:
-  Basic file upload
-  Retry logic with simulated failures
-  Progress callbacks
-  Exponential backoff
-  Max retries limit
-  Background upload
-  Multiple files upload
-  Chunk ordering
-  Session tracking
-  Error history limit

## Related

- **Node.js Implementation**: See parent directory for the original implementation
- **Documentation**: See `../docs/` for detailed guides (shared with Node.js version)

