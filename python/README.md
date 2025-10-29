# IndexedCP - Python Implementation

A minimal file upload system with no encryption support, ported from Node.js to Python.

## Features

- 🚀 **Minimal Code**: Simple, focused implementation
- 📦 **Easy Setup**: Standard Python packaging

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
