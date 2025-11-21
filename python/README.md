
# IndexedCP - Python Client

Python client implementation for IndexedCP with chunked upload support, offline buffering, and optional encryption.

> **Note**: This package provides only the **client** implementation. Use the Node.js server from the parent directory.

## Features

- Chunked file uploads with SQLite storage
- Offline buffering and automatic retry
- Background upload with exponential backoff
- **End-to-end encryption with RSA-4096 + AES-256-GCM**
- Asymmetric envelope encryption (per-stream session keys)
- Encrypted storage at rest
- Pluggable keystore abstraction (filesystem, etc.)
- Compatible with Node.js encrypted server

## Installation

```bash
cd python

# Optional: Create virtual environment
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

pip install -e .
```

## Quick Start

### 1. Start the Node.js Server

From the parent directory:

```bash
cd ..
node server.js --port 3000 --apiKey demo-key-12345

# Or use the CLI
indexcp server --port 3000 --apiKey demo-key-12345
```

See [../README.md](../README.md) for server documentation.

### 2. Use the Python Client

```python
from indexedcp import IndexedCPClient
import asyncio

async def main():
    client = IndexedCPClient(
        server_url="http://localhost:3000/upload",
        api_key="demo-key-12345",
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

## Client Configuration

```python
IndexedCPClient(
    server_url="http://localhost:3000/upload",
    api_key="your-key",            # Or set INDEXEDCP_API_KEY env var
    storage_path=None,             # Default: ~/.indexcp/db/client.db
    chunk_size=1024*1024,          # Chunk size in bytes (1MB default)
    encryption=False,              # Enable encryption (default: False)
    max_retries=float('inf'),      # Maximum retry attempts
    initial_retry_delay=1.0,       # Initial retry delay (seconds)
    max_retry_delay=60.0,          # Max retry delay (seconds)
    retry_multiplier=2.0,          # Exponential backoff multiplier
    on_upload_progress=callback,   # Progress callback
    on_upload_error=callback,      # Error callback
    on_upload_complete=callback,   # Completion callback
    log_level="INFO"
)
```

## File Locations

**Client Database:** `~/.indexcp/db/client.db` (SQLite)  
**Server Uploads:** Configured in Node.js server (see [../README.md](../README.md))

## Encryption Support

The Python client now supports **end-to-end encryption** compatible with the Node.js server!

### Key Features

- 🔐 **RSA-4096** for key wrapping
- 🔐 **AES-256-GCM** for data encryption
- 🔐 **Per-stream ephemeral keys** (unique key per file)
- 🔐 **Encrypted storage** at rest (SQLite)
- 🔐 **Offline encryption** (cache public key, encrypt later)
- 🔐 **Backward compatible** (encryption optional)

### Quick Start with Encryption

1. **Start encrypted server:**
```bash
# Terminal 1: Start Node.js server with encryption
cd ..
node server.js --encryption
```

2. **Upload encrypted files:**
```python
from indexedcp import IndexedCPClient
import asyncio

async def main():
    client = IndexedCPClient(
        server_url="http://localhost:3000/upload",
        api_key="your-key",
        encryption=True  # Enable encryption
    )
    
    await client.initialize()
    await client.fetch_public_key()  # Fetch once, cached for future use
    
    # Files are automatically encrypted before storage
    session_id = await client.add_file("./sensitive_document.pdf")
    
    # Upload encrypted packets to server
    results = await client.upload_buffered_files()
    
    await client.close()

asyncio.run(main())
```

**See [docs/ENCRYPTION.md](./docs/ENCRYPTION.md) for complete encryption guide.**

## Examples

```bash
# Terminal 1: Start server
python examples/demo_server.py

# Terminal 2: Run client demo
python examples/demo_client_upload.py
```

See [examples/README.md](examples/README.md) for details.

## Testing

```bash
# Run all tests
pytest tests/ -v

# Run specific test suites
pytest tests/test_client.py -v              # Basic client tests
pytest tests/test_crypto.py -v              # Cryptography tests
pytest tests/test_keystore.py -v            # Keystore tests
pytest tests/test_client_encryption.py -v   # Encryption tests (NEW!)

# Run integration tests (requires Node.js server running)
# Start server first:
# node ../server.js --port 9999 --apiKey test-integration-key-12345 --outputDir ./tests/uploads
pytest tests/test_integration.py -v

# Run with coverage
pytest --cov=indexedcp --cov-report=html
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
```

**Cryptographic Specifications:**
- **RSA**: 4096-bit keys with OAEP padding and SHA-256 hash
- **AES**: 256-bit keys with GCM mode
- **IV**: 96-bit (12 bytes) random nonce per packet
- **Auth Tag**: 128-bit (16 bytes) for integrity verification
- **AAD**: Additional Authenticated Data includes sessionId, seq, codec, timestamp

## Keystore System

The keystore system provides secure storage for RSA key pairs:

```python
from indexedcp import create_keystore, CryptoUtils
import time

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
```

**Keystore Features:**
- **File Permissions**: Keys stored with 0600 permissions (owner read/write only)
- **Directory Permissions**: 0700 (owner read/write/execute only)
- **Thread Safety**: File locking for concurrent operations
- **JSON Format**: Keys stored as JSON
- **Persistence**: Keys survive restarts

## Architecture

This Python implementation provides the **client-side** components:
- Client for chunked uploads
- Cryptographic utilities
- Keystore abstractions

The **server implementation** is in Node.js (parent directory) and provides:
- HTTP server with FastAPI
- Path security modes
- File upload handling
- See [../README.md](../README.md) for server documentation

## Related

- **Node.js Server**: See [../README.md](../README.md) for server setup
- **Documentation**: See [../docs/](../docs/) for detailed guides
- **Path Modes**: See [../docs/PATH-MODES.md](../docs/PATH-MODES.md)

