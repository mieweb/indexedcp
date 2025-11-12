
# IndexedCP - Python Implementation

A file upload system with chunked upload support, offline buffering, and path security modes. Python port of the Node.js implementation.

## Installation

```bash
cd python

# Optional: Create virtual environment
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

pip install -e .
```

## Usage

### Server

```python
from indexedcp import IndexedCPServer
import uvicorn

server = IndexedCPServer(
    upload_dir="./uploads",      # Optional: defaults to current directory
    api_keys=["your-api-key"],
    path_mode="ignore",          # "ignore" | "sanitize" | "allow-paths"
    port=3000
)

app = server.create_app()
uvicorn.run(app, host="0.0.0.0", port=3000)
```

**Path Modes:**
- `ignore` (default): Unique filenames with timestamp (e.g., `1730728950_a1b2c3d4_reports_2024_data.csv`)
- `sanitize`: Strip all paths, basename only (e.g., `data.csv`)
- `allow-paths`: Preserve subdirectories (e.g., `reports/2024/data.csv`)

### Client

```python
from indexedcp import IndexedCPClient
import asyncio

async def main():
    client = IndexedCPClient(
        server_url="http://localhost:3000",
        api_key="your-api-key",
        chunk_size=1024 * 1024  # 1MB chunks
    )
    
    await client.initialize()
    await client.add_file("./document.pdf")
    result = await client.upload_buffered_files()
    await client.close()

asyncio.run(main())
```

**Background Upload:**
```python
await client.start_upload_background(check_interval=5.0)
# ... do other work ...
await client.stop_upload_background()
```

## Configuration

### Server Options

```python
IndexedCPServer(
    upload_dir=None,               # Upload directory (default: current directory)
    port=3000,                     # Server port
    api_keys=["key1", "key2"],     # Valid API keys (generates one if empty)
    path_mode="ignore",            # "ignore" | "sanitize" | "allow-paths"
    log_level="INFO"               # "DEBUG" | "INFO" | "WARN" | "ERROR"
)
```

### Client Options

```python
IndexedCPClient(
    server_url="http://localhost:3000",
    api_key="your-key",            # Or set INDEXEDCP_API_KEY env var
    storage_path=None,             # Default: ~/.indexcp/db/client.db
    chunk_size=1024*1024,          # Chunk size in bytes (1MB default)
    max_retries=float('inf'),      # Maximum retry attempts
    initial_retry_delay=1.0,       # Initial retry delay (seconds)
    max_retry_delay=60.0,          # Max retry delay (seconds)
    retry_multiplier=2.0,          # Exponential backoff multiplier
    on_upload_progress=callback,   # Progress callback
    log_level="INFO"
)
```

## API Endpoints

| Endpoint | Method | Auth | Description |
|----------|--------|------|-------------|
| `/upload` | POST | Required | Upload file chunks |
| `/health` | GET | None | Health check |

**Upload Request:**
```bash
curl -X POST http://localhost:3000/upload \
  -H "Authorization: Bearer your-api-key" \
  -H "X-Chunk-Index: 0" \
  -H "X-File-Name: document.pdf" \
  --data-binary @chunk.bin
```

## File Locations

**Client Database:** `~/.indexcp/db/client.db` (SQLite)  
**Server Uploads:** Current directory (configurable via `upload_dir`)

Path behavior matches Node.js implementation. See [`../docs/PATH-MODES.md`](../docs/PATH-MODES.md) for details.

## Examples

```bash
# Run server demo
python examples/server_demo.py

# Run client demo (in separate terminal)
python examples/client_demo.py
```

## Testing

```bash
# Run all tests
pytest

# Run specific test file
pytest tests/test_client.py

# Run with verbose output
pytest -v

# Run with coverage
pytest --cov=indexedcp
```

## Related

- **Node.js Implementation**: See parent directory for the original implementation
- **Documentation**: See `../docs/` for detailed guides (shared with Node.js version)

