# IndexedDBShim Implementation

## Overview

The codebase now uses **IndexedDBShim** for persistent storage in Node.js environments, providing true IndexedDB compatibility with SQLite backend.

## What Changed

### Before

- **Production**: Custom JSON files (`filesystem-db.js` and `encrypted-db.js`)
- **Testing**: fake-indexeddb (in-memory)
- **Issues**: No transactional consistency, limited IndexedDB API compatibility

### After

- **Production**: IndexedDBShim with SQLite backend (persistent, transactional)
- **Testing**: fake-indexeddb (in-memory, unchanged)
- **Benefits**: Full ACID compliance, true IndexedDB parity, cross-session durability

## Storage Locations

### Production Mode (NODE_ENV !== 'test')

- **Location**: `~/.indexcp/idb/`
- **Format**: SQLite database files (`.sqlite`)
- **Persistence**: Data survives Node.js restarts
- **Example files**:
  - `D_indexcp.sqlite` - Main database
  - `D_encryption-test.sqlite` - Encrypted sessions
  - `__sysdb__.sqlite` - System metadata

### Test Mode (NODE_ENV === 'test')

- **Location**: In-memory only
- **Format**: fake-indexeddb
- **Persistence**: None (ephemeral)

## Encryption Impact

**NO ENCRYPTION CHANGES REQUIRED** ✓

- Encryption happens **before** storage
- Data is already encrypted and serialized to base64 when stored
- IndexedDBShim just sees JSON-compatible data
- All encryption logic remains identical

## Usage

### Normal Client

```javascript
const IndexedCPClient = require("./client.js");
const client = new IndexedCPClient({ dbName: "mydb" });

// In production: Uses IndexedDBShim with SQLite
// In tests: Uses fake-indexeddb
```

### Encrypted Client

```javascript
const IndexedCPClient = require("./client.js");
const client = new IndexedCPClient({
  dbName: "mydb",
  encryption: true, // Uses IndexedDBShim with encrypted schema
});
```

### Testing

```bash
# Use fake-indexeddb (ephemeral)
NODE_ENV=test node test-script.js

# Use IndexedDBShim (persistent)
NODE_ENV=production node app.js
```

## Technical Details

### Client Setup (lib/client.js)

```javascript
if (isTestMode) {
  // fake-indexeddb (in-memory)
  require("fake-indexeddb/auto");
} else {
  // IndexedDBShim (SQLite-backed)
  setGlobalVars(global, {
    checkOrigin: false,
    databaseBasePath: "~/.indexcp/idb",
    deleteDatabaseFiles: false,
  });
}
```

### Encrypted DB (lib/encrypted-db.js)

- Completely rewritten to use IndexedDBShim/fake-indexeddb
- Removed custom JSON file storage class
- Now uses native IndexedDB API through shim

## Dependencies

### Updated package.json

```json
{
  "dependencies": {
    "indexeddbshim": "^10.1.0",
    "fake-indexeddb": "^6.0.1",
    "idb": "^7.1.1"
  }
}
```

**Note**: Version 10.1.0 is used to avoid canvas native dependencies in v15+

## Migration Path

### For Existing Users

No migration needed! The first run will create new SQLite databases. Old JSON files remain untouched in `~/.indexcp/encrypted-db/` (if they exist).

### Cleanup Old Files (Optional)

```bash
# Remove old JSON-based storage (if present)
rm -rf ~/.indexcp/db/
rm -rf ~/.indexcp/encrypted-db/
```

## Verification

Test that IndexedDBShim is working:

```bash
# Production mode test
NODE_ENV=production node -e "
const client = require('./client.js');
const c = new client({ dbName: 'test' });
c.initDB().then(() => console.log('✓ IndexedDBShim working'));
"

# Check database files
ls -lh ~/.indexcp/idb/
```

## Benefits

1. **Transactional Consistency**: ACID-compliant operations
2. **Browser Parity**: Identical behavior between Node.js and browsers
3. **Persistence**: Data survives restarts (unlike fake-indexeddb)
4. **Standards-Compliant**: Full IndexedDB API support
5. **No Encryption Changes**: Crypto layer unchanged

## Performance

- **Reads/Writes**: Faster than JSON file operations
- **Transactions**: Atomic with rollback support
- **Indexes**: Native SQLite indexes for efficient queries
- **Storage**: Efficient binary storage with compression

## Troubleshooting

### Database locked errors

- Ensure only one process accesses the database
- Close connections properly

### Permission errors

- Check `~/.indexcp/idb/` directory permissions
- Ensure write access to home directory

### Test mode not working

- Set `NODE_ENV=test` environment variable
- Verify fake-indexeddb is installed

---

## Summary

IndexedDBShim provides production-grade persistent storage for Node.js with zero changes to encryption logic. Tests continue to use ephemeral fake-indexeddb for speed.
