# IndexedDBShim Implementation

## Overview
Successfully implemented IndexedDBShim v10.1.0 with better-sqlite3 for SQLite-backed persistent storage in Node.js production environments.

## Implementation Details

### Storage Strategy
The client now uses different storage backends based on the environment:

1. **Production Mode** (Default Node.js):
   - Uses `indexeddbshim` with `better-sqlite3`
   - SQLite-backed persistent storage
   - Data persists across process restarts
   - Location: `~/.indexcp/` (configurable via IndexedDBShim)

2. **Test Mode** (`NODE_ENV=test` or `INDEXEDCP_TEST_MODE=true`):
   - Uses `fake-indexeddb` (in-memory)
   - Fast, ephemeral storage
   - No cleanup needed between tests
   - Prevents test pollution

3. **CLI Mode** (`INDEXEDCP_CLI_MODE=true`):
   - Legacy filesystem-db (JSON files)
   - Maintains backward compatibility
   - Used by specific CLI commands

4. **Browser Mode**:
   - Uses native IndexedDB
   - No changes from previous implementation

### Dependencies Added
```json
{
  "indexeddbshim": "^10.1.0",
  "better-sqlite3": "^11.7.0"
}
```

### Code Changes

#### lib/client.js
- Updated storage initialization to detect environment
- Production uses IndexedDBShim with SQLite backend
- Tests use fake-indexeddb for speed
- No changes to encryption logic (encryption layer is independent)

#### Test Files Updated
All test files now set `INDEXEDCP_TEST_MODE=true` to use in-memory storage:
- `tests/test-all.js` - Updated test runner
- `tests/test-all-examples.js`
- `tests/test-encryption.js`
- `tests/test-security.js`
- `tests/test-path-modes.js`

## Encryption Impact

✅ **NO encryption-related changes required**

The encryption layer (`crypto-utils.js`) is completely independent of the storage layer:
- Encryption happens **before** data reaches IndexedDB
- IndexedDBShim just stores the encrypted buffers
- No changes to AES-GCM, RSA-OAEP, or key management

## Server Impact

✅ **NO server-side changes**

The server (`lib/server.js`) does not use IndexedDB:
- Server uses keystores (filesystem/memory/MongoDB)
- Uploaded files stored directly on disk
- No IndexedDB dependency on server

## Testing

All tests pass successfully:
- ✅ Functional tests
- ✅ Security tests  
- ✅ Restart persistence tests
- ✅ Encryption tests
- ✅ CLI tests

Tests run fast using in-memory fake-indexeddb while production gets durable SQLite storage.

## Benefits

1. **Durability**: Data survives process crashes and restarts
2. **ACID Transactions**: SQLite provides proper transactional consistency
3. **Browser Parity**: Same IndexedDB API as browsers
4. **No Regression**: Tests remain fast with fake-indexeddb
5. **Clean Separation**: Test mode vs production mode clearly defined

## Usage

### Production (Persistent Storage)
```javascript
const client = new IndexedCPClient();
// Automatically uses IndexedDBShim with SQLite
```

### Testing (In-Memory)
```javascript
process.env.INDEXEDCP_TEST_MODE = 'true';
const client = new IndexedCPClient();
// Uses fake-indexeddb (ephemeral)
```

### CLI Mode (Legacy)
```javascript
process.env.INDEXEDCP_CLI_MODE = 'true';
const client = new IndexedCPClient();
// Uses filesystem-db (JSON files)
```

## Migration Notes

- No breaking changes to public API
- Existing code continues to work
- Encryption mode unchanged
- Tests use same interfaces
- SQLite database created automatically on first use
