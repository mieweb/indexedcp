# IndexedCP - Python Implementation

A minimal file upload system with no encryption support, ported from Node.js to Python.

## Features

- 🚀 **Minimal Code**: Simple, focused implementation
- 📦 **Easy Setup**: Standard Python packaging
- 📝 **Logging**: Centralized logging utility with configurable levels

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
│       └── __init__.py
├── tests/                  # Test files
│   └── __init__.py
├── docs/                   # Documentation
├── examples/               # Example scripts
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
- **Documentation**: See `docs/` for detailed guides (shared with Node.js version)
