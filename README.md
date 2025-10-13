
# indexedcp

**indexedcp** is a Node.js library and CLI toolset for secure, efficient, and resumable file transfer. By default, Node.js environments buffer uploads on disk (`~/.indexcp/db/chunks.json`) so transfers survive restarts, while browser builds fall back to IndexedDB for offline and resumable support.

---

## Features

- 🔄 Resumable and offline-friendly uploads
- 📦 Chunked streaming with persistent buffering (filesystem on Node, IndexedDB in browsers)
- 🔒 API key authentication
- 🛡️ Path traversal protection
- 📦 Separate client/server imports for minimal bundle size
- 🔧 Simple CLI tools

---

## Installation

```bash
npm install -g indexedcp
```

---

## Quick Start

### CLI Usage

```bash
# Set your API key
export INDEXCP_API_KEY=your-secure-api-key

# Start server
indexedcp server 3000 ./uploads

# Upload files (single-step)
indexedcp upload http://localhost:3000/upload ./file1.txt ./file2.txt
```

### Programmatic Usage

```javascript
// Client (upload)
const IndexCPClient = require('indexedcp/client');
const client = new IndexCPClient({ apiKey: 'your-key' });
await client.addFile('./myfile.txt');
await client.uploadBufferedFiles('http://localhost:3000/upload');

// Server (receive)
const { IndexCPServer } = require('indexedcp/server');
new IndexCPServer({ port: 3000, outputDir: './uploads' }).listen(3000);
```

---

## Storage Modes

- **Node.js (default):** Chunks persist to the local filesystem at `~/.indexcp/db/chunks.json`, ensuring buffered uploads survive restarts.
- **Force in-memory IndexedDB:** Set `INDEXCP_CLI_MODE=false` before creating the client to revert to the previous fake-IndexedDB behaviour (useful for ephemeral test runs).
- **Browsers:** Always use the platform’s IndexedDB implementation; no filesystem access is attempted.

```bash
# Example: opt into in-memory storage for a single run
INDEXCP_CLI_MODE=false node upload-script.js
```

---

## Import Options

Choose the import style that fits your needs:

```javascript
// Client-only (browser/upload)
const IndexCPClient = require('indexedcp/client');

// Server-only (receive)
const { IndexCPServer } = require('indexedcp/server');

// Combined (both - backward compatible)
const { client: IndexCPClient, server } = require('indexedcp');
```

---

## CLI Reference

### Authentication

**Recommended: Environment Variable**
```bash
export INDEXCP_API_KEY=your-secure-api-key
```

**Alternative: Command Line** ⚠️
```bash
indexedcp upload http://localhost:3000/upload --api-key your-key ./file.txt
```

**Interactive:** If no key is provided, you'll be prompted securely.

### Commands

**Start Server**
```bash
indexedcp server <port> <output-dir> [--api-key <key>] [--path-mode <mode>]
```

**Path Modes:**
- `sanitize` (default) - Strip paths, prevent overwrites with unique suffix
- `allow-paths` - Allow subdirectories (with security validation)
- `ignore` - Generate unique filenames, ignore client paths

**Upload Files (Single-Step)**
```bash
indexedcp upload <url> [--api-key <key>] <file1> [file2] [...]
```

**Upload Files (Two-Step)**
```bash
indexedcp add <file1> [file2] [...]
indexedcp upload <url> [--api-key <key>]
```

---

## Path Handling Modes

The server supports three path handling modes to balance security and flexibility:

### `ignore` (Default)
- Generates unique filenames with format: `<timestamp>_<random>_<full-path>.ext`
- Path separators (`/` or `\`) replaced with `_` (single underscore)
- Other illegal characters replaced with `-` (dash) for easy parsing
- Guarantees no overwrites, perfect for audit trails
- Maintains complete traceability of original location
- Example: `reports/data.csv` → `1234567890_a1b2c3d4_reports_data.csv`
- Example: `my document.txt` → `1234567890_a1b2c3d4_my-document.txt`

### `sanitize`
- Strips paths, prevents overwrites with session tracking
- Uses simple filenames from client
- Example: `dir/file.txt` → `file.txt`

### `allow-paths`
- Allows subdirectories (with security validation)
- Best for trusted clients needing organization
- Example: `reports/2024/data.csv` → `reports/2024/data.csv`

**Usage:**
```javascript
// Programmatic (defaults to 'ignore' mode)
const server = new IndexCPServer({
  port: 3000,
  outputDir: './uploads',
  pathMode: 'ignore'  // or 'sanitize' or 'allow-paths'
});

// CLI (defaults to 'ignore' mode)
indexedcp server 3000 ./uploads

# Or specify a different mode
indexedcp server 3000 ./uploads --path-mode sanitize
```

See [`docs/PATH-MODES.md`](./docs/PATH-MODES.md) for complete guide.

---

## Examples

See the [`examples/`](./examples/) directory for implementations:

- **client-stream.js** - Stream files with IndexedDB buffering
- **server.js** - Minimal HTTP server with authentication
- **client-filename-mapping.js** - Custom filename handling
- **combined-usage.js** - Full client/server integration

---

## Testing

```bash
npm test  # 25 tests: 7 functional + 18 security
npm run test:path-modes  # 9 path mode tests
```

For details, see [`tests/README.md`](./tests/README.md)

---

## Security

Built-in protection against:
- Path traversal attacks
- Unauthorized access  
- Directory escaping

All uploads are validated and isolated to the configured output directory.

---

## License

MIT

---

## Contributing

Pull requests and issues welcome! Visit [bluehive.com/integrate](https://bluehive.com/integrate?utm_source=bluehive&utm_medium=chat&utm_campaign=bluehive-ai) for more information.
