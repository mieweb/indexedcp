# Migration Guide: Unified Encryption API

## Overview

Encryption support has been **integrated** into the main `IndexedCPServer` and `IndexedCPClient` classes. The separate `EncryptedServer` and `EncryptedClient` classes have been deprecated and archived.

## Why This Change?

✅ **DRY (Don't Repeat Yourself)** - Single source of truth  
✅ **Simpler API** - One class instead of two  
✅ **Backward Compatible** - Existing code works without changes  
✅ **Easier to Maintain** - Changes only need to happen once  

## Migration Steps

### Server Migration

**Before** (using separate class):
```javascript
const EncryptedServer = require('indexedcp/lib/encrypted-server');

const server = new EncryptedServer({
  port: 3000,
  outputDir: './uploads',
  keystoreType: 'filesystem'
});

await server.listen(3000);
```

**After** (using unified class):
```javascript
const { IndexedCPServer } = require('indexedcp/lib/server');

const server = new IndexedCPServer({
  port: 3000,
  outputDir: './uploads',
  encryption: true,              // ← Add this flag
  keystoreType: 'filesystem'
});

await server.listen(3000);
```

### Client Migration

**Before** (using separate class):
```javascript
const EncryptedClient = require('indexedcp/lib/encrypted-client');

const client = new EncryptedClient({
  serverUrl: 'http://localhost:3000',
  apiKey: 'your-key'
});

await client.fetchPublicKey();
await client.addFile('./file.txt');
await client.uploadBufferedFiles();
```

**After** (using unified class):
```javascript
const IndexedCPClient = require('indexedcp/lib/client');

const client = new IndexedCPClient({
  serverUrl: 'http://localhost:3000',
  apiKey: 'your-key',
  encryption: true               // ← Add this flag
});

await client.fetchPublicKey();
await client.addFile('./file.txt');
await client.uploadBufferedFiles();
```

## API Compatibility

### All Methods Preserved

Both server and client methods remain **exactly the same**:

#### Server Methods
- ✅ `generateKeyPair()` - works when `encryption: true`
- ✅ `getActivePublicKey()` - works when `encryption: true`
- ✅ `rotateKeys()` - works when `encryption: true`
- ✅ `getEncryptionStatus()` - returns `{ encryption: false }` when disabled
- ✅ `listen(port)` - works with or without encryption
- ✅ `close()` - works with or without encryption

#### Client Methods
- ✅ `fetchPublicKey()` - works when `encryption: true`
- ✅ `getCachedPublicKey()` - works when `encryption: true`
- ✅ `startStream(fileName)` - works when `encryption: true`
- ✅ `addPacket(sessionId, data, seq)` - works when `encryption: true`
- ✅ `getEncryptionStatus()` - returns `{ encryption: false }` when disabled
- ✅ `addFile(filePath)` - works with or without encryption
- ✅ `uploadBufferedFiles(url)` - works with or without encryption

### Automatic Behavior

When `encryption: false` (default):
- Server handles `/upload` endpoint (original unencrypted)
- Client stores raw chunks in IndexedDB
- No crypto modules loaded (smaller bundle size)

When `encryption: true`:
- Server handles both `/upload` (legacy) and `/upload-encrypted`
- Client stores encrypted packets with wrapped keys
- Crypto modules loaded only when needed

## Migration Checklist

### For Server Code
- [ ] Replace `require('./lib/encrypted-server')` with `require('./lib/server')`
- [ ] Change `new EncryptedServer(...)` to `new IndexedCPServer(...)`
- [ ] Add `encryption: true` to constructor options
- [ ] Test key rotation and decryption
- [ ] Verify keystore persistence

### For Client Code
- [ ] Replace `require('./lib/encrypted-client')` with `require('./lib/client')`
- [ ] Change `new EncryptedClient(...)` to `new IndexedCPClient(...)`
- [ ] Add `encryption: true` to constructor options
- [ ] Test offline encryption (AC2)
- [ ] Test upload with encrypted packets

### For Examples
- [ ] Update example files to use unified classes
- [ ] Add `encryption: true` flag where needed
- [ ] Test all examples end-to-end

### For Tests
- [ ] Update test imports
- [ ] Add `encryption: true` to test fixtures
- [ ] Verify all ACs still pass

## Benefits

### 1. **Easier to Understand**
```javascript
// Clear intent: encryption is a feature, not a separate thing
const server = new IndexedCPServer({ encryption: true });
```

### 2. **No Duplication**
- Upload logic exists in one place
- Bug fixes apply to both modes
- New features work everywhere

### 3. **Gradual Adoption**
```javascript
// Start without encryption
const client = new IndexedCPClient({ apiKey: 'key' });

// Enable later without changing class
const client = new IndexedCPClient({ 
  apiKey: 'key',
  encryption: true  // Just add this
});
```

### 4. **Bundle Size**
```javascript
// Without encryption: crypto modules not loaded
const client = new IndexedCPClient({ /* no encryption */ });
// Smaller bundle size!

// With encryption: crypto modules loaded only when needed
const client = new IndexedCPClient({ encryption: true });
```

## Rollback Plan

If you need to rollback:

1. Old classes are preserved in `.attic/` directory
2. Copy them back to `lib/`:
   ```bash
   cp .attic/encrypted-server.js lib/
   cp .attic/encrypted-client.js lib/
   ```
3. Update imports back to old classes
4. File a GitHub issue explaining why rollback was needed

## Questions?

- Check [ENCRYPTION.md](./ENCRYPTION.md) for full documentation
- See [KEYSTORE-QUICKSTART.md](./KEYSTORE-QUICKSTART.md) for keystore setup
- Review examples in `examples/` directory
- Open an issue on GitHub

## Timeline

- **2025-10-12**: Unified API introduced
- **Old API**: Moved to `.attic/` (deprecated, not deleted)
- **Support**: Both APIs work during transition period
- **Future**: Old classes will be removed in next major version

**Recommendation**: Migrate now for easier maintenance and cleaner code! 🎯
