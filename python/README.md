
# IndexedCP - Python Implementation

A file upload system with chunked upload support, offline buffering, path security modes, and optional encryption. Python port of the Node.js implementation.

## Features

- ✅ Chunked file uploads with SQLite storage
- ✅ Offline buffering and automatic retry
- ✅ Path security modes (ignore, sanitize, allow-paths)
- ✅ Background upload with exponential backoff
- ✅ RSA-4096 and AES-256-GCM cryptography utilities
- ✅ Pluggable keystore abstraction (filesystem, etc.)
- 🚧 Full encryption support (coming soon)

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
pytest tests/test_crypto.py

# Run with verbose output
pytest -v

# Run with coverage
pytest --cov=indexedcp
```

## Cryptography Utilities

The `CryptoUtils` class provides low-level cryptographic primitives for encryption support:

```python
from indexedcp import CryptoUtils

crypto = CryptoUtils()

# Generate RSA-4096 key pair
key_pair = crypto.generate_server_key_pair()
# Returns: {'publicKey': '...', 'privateKey': '...', 'kid': '...'}

# Generate AES-256 session key
session_key = crypto.generate_session_key()

# Wrap session key with RSA public key (RSA-OAEP-SHA256)
wrapped_key = crypto.wrap_session_key(session_key, key_pair['publicKey'])

# Unwrap session key with RSA private key
unwrapped_key = crypto.unwrap_session_key(wrapped_key, key_pair['privateKey'])

# Encrypt data with AES-256-GCM
metadata = {'sessionId': 'test', 'seq': 1, 'codec': 'raw'}
encrypted = crypto.encrypt_packet(b"data", session_key, metadata)
# Returns: {'ciphertext': b'...', 'iv': b'...', 'authTag': b'...', 'aad': b'...'}

# Decrypt data
decrypted = crypto.decrypt_packet(
    encrypted['ciphertext'],
    session_key,
    encrypted['iv'],
    encrypted['authTag'],
    encrypted['aad']
)

# Serialize for storage (converts bytes to base64 strings)
serialized = crypto.serialize_packet(encrypted)

# Deserialize from storage
deserialized = crypto.deserialize_packet(serialized)
```

**Cryptographic Specifications:**
- **RSA**: 4096-bit keys with OAEP padding and SHA-256 hash
- **AES**: 256-bit keys with GCM mode
- **IV**: 96-bit (12 bytes) random nonce per packet
- **Auth Tag**: 128-bit (16 bytes) for integrity verification
- **AAD**: Additional Authenticated Data includes sessionId, seq, codec, timestamp

## Keystore System

The keystore system provides secure storage for RSA key pairs with support for key rotation:

```python
from indexedcp import create_keystore, CryptoUtils

# Create filesystem keystore
keystore = create_keystore('filesystem', {
    'key_store_path': './server-keys'
})
await keystore.initialize()

# Generate and save key pair
crypto = CryptoUtils()
key_pair = crypto.generate_server_key_pair()

key_data = {
    'kid': key_pair['kid'],
    'publicKey': key_pair['publicKey'],
    'privateKey': key_pair['privateKey'],
    'createdAt': int(time.time() * 1000),
    'active': True
}
await keystore.save(key_data['kid'], key_data)

# Load key later
loaded_key = await keystore.load(key_data['kid'])

# List all keys
all_keys = await keystore.list()

# Delete old keys
await keystore.delete(old_kid)
```

**Keystore Features:**
- **File Permissions**: Keys stored with 0600 permissions (owner read/write only)
- **Directory Permissions**: Keystore directory uses 0700 (owner read/write/execute only)
- **Thread Safety**: File locking for concurrent operations
- **JSON Format**: Keys stored as JSON for easy inspection
- **Persistence**: Keys survive server restarts
- **Key Rotation**: Support for multiple key versions

**Supported Keystore Types:**
- `filesystem` - Store keys as JSON files (default, no external dependencies)
- Future: `mongodb`, `redis`, custom implementations

## Related

- **Node.js Implementation**: See parent directory for the original implementation
- **Documentation**: See `../docs/` for detailed guides (shared with Node.js version)

