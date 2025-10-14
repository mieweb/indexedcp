# Migration to SQLite-Backed Storage

## Overview

As of this version, **indexedcp** has migrated from JSON-based file persistence to a SQLite-backed IndexedDB implementation using IndexedDBShim + WebSQL. This provides better performance, transactional consistency, and standard compliance.

## What Changed

### Before (JSON-based)
- **Storage**: `~/.indexcp/db/chunks.json`
- **Format**: Plain JSON file
- **Issues**: 
  - No transaction support
  - Risk of data corruption on crashes
  - Full file read/write for every operation
  - Limited scalability

### After (SQLite-based)
- **Storage**: `~/.indexcp/db/indexedcp.sqlite`
- **Format**: SQLite database
- **Benefits**:
  - Full ACID transaction support
  - Better performance with indexed queries
  - Standard IndexedDB implementation
  - Handles large datasets efficiently
  - Cross-session durability

## Migration Path

### For End Users
**No action required!** The migration happens automatically:

1. On first run after upgrade, a new SQLite database is created
2. Old `chunks.json` files (if any) are ignored
3. New chunks are stored in the SQLite database
4. Everything works the same from the user perspective

### For Developers

#### If You're Using `IndexCPClient`
**No code changes needed!** The API remains the same:

```javascript
const IndexCPClient = require('indexedcp/client');
const client = new IndexCPClient();

// Same API as before
await client.addFile('./myfile.txt');
await client.uploadBufferedFiles('http://server.com/upload');
```

#### If You Need In-Memory Storage (Testing)
Set the environment variable before creating the client:

```bash
INDEXCP_CLI_MODE=false node my-script.js
```

```javascript
// Or in code:
process.env.INDEXCP_CLI_MODE = 'false';
const IndexCPClient = require('indexedcp/client');
```

#### If You Were Directly Accessing the Database
If you were reading `chunks.json` directly, you'll need to update your code to query the SQLite database:

```javascript
const client = new IndexCPClient();
const db = await client.initDB();

// Use IndexedDB API
const tx = db.transaction('chunks', 'readonly');
const store = tx.objectStore('chunks');
const chunks = await store.getAll();
```

## Storage Location

The SQLite database is stored at:
```
~/.indexcp/db/indexedcp.sqlite
```

You can inspect it using standard SQLite tools:
```bash
sqlite3 ~/.indexcp/db/indexedcp.sqlite
```

## Database Schema

The SQLite database uses a table called `chunks`:

```sql
CREATE TABLE chunks (
  id TEXT PRIMARY KEY,
  fileName TEXT,
  chunkIndex INTEGER,
  data BLOB
)
```

## Performance Characteristics

### JSON-based (Old)
- **Write**: O(n) - entire file rewritten
- **Read**: O(n) - entire file parsed
- **Delete**: O(n) - entire file rewritten
- **Query**: O(n) - linear search

### SQLite-based (New)
- **Write**: O(log n) - indexed insert
- **Read**: O(log n) - indexed lookup
- **Delete**: O(log n) - indexed delete
- **Query**: O(log n) - indexed search
- **Transactions**: Full ACID support

## Troubleshooting

### Issue: "Could not dynamically require sqlite3"
**Solution**: Rebuild native bindings:
```bash
npm rebuild sqlite3
```

### Issue: Permission denied on database file
**Solution**: Ensure `~/.indexcp/db/` directory has write permissions:
```bash
chmod 755 ~/.indexcp/db/
```

### Issue: Database locked
**Solution**: Ensure no other process is accessing the database. SQLite allows multiple readers but only one writer at a time.

## Dependencies

New dependencies added:
- `indexeddbshim`: ^16.1.0 - IndexedDB polyfill for Node.js
- `websql`: ^2.0.3 - WebSQL implementation using SQLite3
- `setimmediate`: ^1.0.5 - Required by IndexedDBShim

Existing dependencies (still used):
- `fake-indexeddb`: ^6.0.1 - For in-memory testing mode
- `idb`: ^7.1.1 - Promise-based IndexedDB wrapper
- `node-fetch`: ^2.7.0 - For HTTP uploads

## Rollback

If you need to rollback to the JSON-based storage:
1. Checkout the previous version: `npm install indexedcp@<previous-version>`
2. Remove the SQLite database: `rm -rf ~/.indexcp/db/*.sqlite*`

However, note that:
- Old `chunks.json` files are not automatically restored
- You'll lose transaction safety and performance benefits
- The JSON-based system is deprecated and unsupported

## Support

For issues or questions:
- Create an issue on GitHub
- Include your Node.js version (`node --version`)
- Include error messages and stack traces
- Mention your operating system

## Technical Details

### How It Works
1. `lib/sqlite-db.js` wraps WebSQL with an IndexedDB-like API
2. WebSQL uses SQLite3 for actual storage
3. Binary data (Buffer) is stored as base64 in BLOB columns
4. Transactions ensure data consistency
5. Same API surface as fake-indexeddb for compatibility

### Why SQLite?
- **Universal**: Works on all platforms (Windows, macOS, Linux)
- **Zero-config**: No server setup required
- **Reliable**: Battle-tested for 20+ years
- **Standard**: Supports SQL and has great tooling
- **Embedded**: Single file, no external dependencies

### Why Not Just Use SQLite Directly?
- **Standard API**: IndexedDB is a web standard
- **Browser Compatibility**: Same API works in browsers
- **Abstraction**: Easier to swap implementations
- **Testing**: Can use in-memory fake-indexeddb for tests
