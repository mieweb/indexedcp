````markdown
# IndexedCP - Python Implementation

A minimal file upload system with optional storage backends, ported from Node.js to Python.

## Features

- 🚀 **Minimal Code**: Simple, focused implementation
- 📦 **Easy Setup**: Standard Python packaging
- 📝 **Logging**: Centralized logging utility with configurable levels
- 💾 **Pluggable Storage**: Abstract storage layer with SQLite implementation

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

### Basic Usage (Coming Soon)

```python
from indexedcp import IndexedCPClient, IndexedCPServer

# Server
server = IndexedCPServer(port=3000)
await server.start()

# Client
client = IndexedCPClient(server_url="http://localhost:3000")
await client.upload_file("myfile.txt")
```

## Project Structure

```
python/
├── src/
│   └── indexedcp/          # Main package
│       ├── __init__.py     # Package exports
│       ├── logger.py       # Logging utilities
│       └── storage/        # Storage abstraction layer
│           ├── __init__.py
│           ├── base_storage.py     # Abstract base class
│           └── sqlite_storage.py   # SQLite implementation
├── tests/                  # Test files
│   ├── __init__.py
│   ├── test_logger.py
│   └── test_storage.py
├── docs/                   # Documentation
├── examples/               # Example scripts
│   └── logger_demo.py
├── pyproject.toml          # Project metadata
├── requirements.txt        # Runtime dependencies
└── requirements-dev.txt    # Development dependencies
```

## Development

### Run Tests

```bash
pytest
```

## Related

- **Node.js Implementation**: See parent directory for the original implementation
- **Documentation**: See `../docs/` for detailed guides (shared with Node.js version)
