# Path Handling Modes

IndexedCP supports three path handling modes to balance security and flexibility based on your use case.

## Modes

### Why Choose `ignore` Mode?

- **Complete traceability**: Full path is preserved in the filename
- **Clear parsing**: Single `_` marks path boundaries, `-` marks sanitized characters
- **Easy extraction**: Split on `_` to get path components
- **Database friendly**: Query by path components using underscore delimiters
- **No information loss**: Know exactly where the file came from
- **Collision-free**: Timestamp + random ensures uniqueness

---

### `sanitize` ✅ High Security

**Best for:** Untrusted clients, public uploads when you want to preserve simple filenames

**Behavior:**
- Strips all directory paths from filenames
- Only uses the base filename (e.g., `dir/file.txt` → `file.txt`)
- Tracks upload sessions to prevent chunked uploads from creating multiple files
- Rejects path separators (`/`, `\`), traversal attempts (`..`), and absolute paths
- All files go directly into the configured output directory

**Example:**
```javascript
const server = new IndexCPServer({
  port: 3000,
  outputDir: './uploads',
  pathMode: 'sanitize'  // default
});
```

```bash
# CLI
indexedcp server 3000 ./uploads --path-mode sanitize
```

**Client sends:** `reports/2024/data.csv`  
**Server saves:** `./uploads/data.csv`

---

### `allow-paths` ⚠️ Use with Trusted Clients

**Best for:** Organized uploads from known/trusted clients, preserving folder structure

**Behavior:**
- Allows clients to create subdirectories
- Still protects against path traversal (`../`) and absolute paths (`/`, `C:\`)
- Validates that resolved paths stay within output directory
- Creates subdirectories automatically as needed
- Useful for maintaining organized upload structure

**Example:**
```javascript
const server = new IndexCPServer({
  port: 3000,
  outputDir: './uploads',
  pathMode: 'allow-paths'
});
```

```bash
# CLI
indexedcp server 3000 ./uploads --path-mode allow-paths
```

**Client sends:** `reports/2024/data.csv`  
**Server saves:** `./uploads/reports/2024/data.csv`

**Security Note:** Still blocks:
- `../etc/passwd` ❌
- `/etc/passwd` ❌
- `C:\Windows\System32\file` ❌
- `\\server\share\file` ❌

---

## Comparison Table

| Feature | `ignore` | `sanitize` | `allow-paths` |
|---------|----------|------------|---------------|
| Path handling | Generates unique name with full path preserved | Strips path, uses filename only | Creates subdirectories |
| Filename format | `<timestamp>_<random>_<full-path>.<ext>` | `<filename>.<ext>` or `<filename>_<session>.<ext>` | `<path>/<filename>.<ext>` |
| Path separators | Replaced with `_` (single underscore) | N/A | Preserved |
| Other special chars | Replaced with `-` (dash) | Replaced with `_` | Replaced with `_` |

---

## Security Features (All Modes)

All modes include:
- ✅ API key authentication
- ✅ Path resolution validation
- ✅ Output directory boundary checks
- ✅ Protection against empty/invalid filenames

Modes `sanitize` and `allow-paths` additionally block:
- ❌ Parent directory traversal (`../`, `..\\`)
- ❌ Absolute paths (`/`, `C:\`, `\\server`)
- ❌ Path injection attempts

---

## Usage Examples

### Programmatic

```javascript
const { IndexCPServer } = require('indexedcp/server');

// Default: Unique filenames with traceability (ignore mode)
const server1 = new IndexCPServer({
  port: 3000,
  outputDir: './uploads'
  // pathMode defaults to 'ignore'
});

// Simple filenames (sanitize mode)
const server2 = new IndexCPServer({
  port: 3001,
  outputDir: './simple-uploads',
  pathMode: 'sanitize'
});

// Allow subdirectories (allow-paths mode)
const server3 = new IndexCPServer({
  port: 3002,
  outputDir: './organized-uploads',
  pathMode: 'allow-paths'
});
```

### CLI

```bash
# Default (ignore mode - generates unique filenames)
export INDEXCP_API_KEY=your-secure-key
indexedcp server 3000 ./uploads

# Simple filenames (sanitize mode)
indexedcp server 3000 ./uploads --path-mode sanitize

# Allow paths (allow-paths mode)
indexedcp server 3000 ./uploads --path-mode allow-paths
```

---

## Testing

Run the path mode test suite:

```bash
npm run test:path-modes
```

This validates:
- ✅ Simple filenames in sanitize mode
- ✅ Path rejection in sanitize mode
- ✅ Subdirectory support in allow-paths mode
- ✅ Security validation in allow-paths mode
- ✅ Unique generation in ignore mode
- ✅ All security checks for each mode

---

## Recommendations

### Choose `ignore` when: (Default - Recommended for most uses)
- 📝 Need audit trails with timestamps
- 🔢 Generating unique identifiers is important
- 🗄️ Mapping filenames in a database
- 🔐 Want maximum server-side control
- 🔍 Need traceability with original filenames preserved
- 🏭 Production systems requiring reliability
- ⚡ Most use cases (it's the default!)

### Choose `sanitize` when:
- 👥 Accepting uploads from untrusted users
- 🔒 Security is the top priority but you want simple filenames
- 📁 Flat file structure is acceptable
- 🌐 Running a public upload service with human-readable names

### Choose `allow-paths` when:
- 🤝 Working with known/trusted clients
- 📂 Need to preserve folder structure
- 🎯 Clients need control over organization
- 🏢 Internal tools and applications

---

## Migration Guide

**New default:** Existing code now defaults to `ignore` mode (was `sanitize`).

### If you want the old behavior:
```javascript
// Explicitly set to sanitize for backward compatibility
const server = new IndexCPServer({ 
  pathMode: 'sanitize',
  ...
});
```

### Benefits of new default (`ignore`):
- **Session tracking** for chunked uploads (prevents multiple files for same upload)
- **Guaranteed unique filenames** (no overwrite issues)
- **Original filename preserved** (better traceability)
- **Production-ready** (timestamps make auditing easier)

If you were relying on subdirectories, update to:

```javascript
// For subdirectory support
const server = new IndexCPServer({ 
  pathMode: 'allow-paths',
  ...
});
```

---

## See Also

- [../README.md](../README.md) - Main documentation
- [../tests/README.md](../tests/README.md) - Test suite documentation
- [../tests/test-path-modes.js](../tests/test-path-modes.js) - Path mode test implementation
- [../examples/server-ignore-mode.js](../examples/server-ignore-mode.js) - Ignore mode example
