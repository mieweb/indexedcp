# Attic - Dead Code Archive

This directory contains code that has been removed from active use but preserved for historical reference.

## Files

### `encrypted-server.js` (archived 2025-10-12)
**Reason**: Refactored into unified `lib/server.js`  
**Context**: Originally created as separate class for encryption support. Violated DRY principle by duplicating server logic. Encryption is now an optional feature in the main `IndexCPServer` class via `encryption: true` flag.

### `encrypted-client.js` (archived 2025-10-12)
**Reason**: Refactored into unified `lib/client.js`  
**Context**: Originally created as separate class for encryption support. Violated DRY principle by duplicating client logic. Encryption is now an optional feature in the main `IndexCPClient` class via `encryption: true` flag.

## Migration Guide

**Old approach** (separate classes):
```javascript
const EncryptedServer = require('./lib/encrypted-server');
const server = new EncryptedServer({ port: 3000 });
```

**New approach** (unified with flag):
```javascript
const { IndexCPServer } = require('./lib/server');
const server = new IndexCPServer({ 
  port: 3000,
  encryption: true 
});
```

Same pattern for client:
```javascript
// Old
const EncryptedClient = require('./lib/encrypted-client');

// New
const IndexCPClient = require('./lib/client');
const client = new IndexCPClient({ encryption: true });
```

## Benefits of Refactoring

✅ **DRY** - Single source of truth for server and client logic  
✅ **Backward Compatible** - Existing code works without changes (encryption defaults to `false`)  
✅ **Simpler API** - One class with optional feature, not two separate classes  
✅ **Easier Maintenance** - Changes to upload logic only need to happen in one place  
✅ **Clearer Intent** - `encryption: true` makes intent obvious in constructor

## Recovery

If you need to reference the old implementation:
- Files are preserved exactly as they were
- Git history contains full development history
- New implementation follows same encryption logic, just integrated better
