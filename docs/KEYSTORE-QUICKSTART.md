# Keystore Quick Start

## What is a Keystore?

A **keystore** is a persistent storage backend for the server's RSA encryption keys. Without a keystore, keys are lost when the server restarts, making it impossible to decrypt old client data.

## Why You Need It

✅ **Key Rotation** - Old keys remain available after rotation  
✅ **Server Restarts** - Keys persist across deployments  
✅ **Multi-Server** - Share keys across instances (with MongoDB)  
✅ **Data Recovery** - Never lose ability to decrypt client data

## Quick Start

### Default (Filesystem)

Zero configuration required:

```javascript
const EncryptedServer = require('indexedcp/lib/encrypted-server');

const server = new EncryptedServer({
  port: 3000
});

await server.listen(3000);
// ✓ Keys automatically saved to ./server-keys/
```

### MongoDB (Production)

For distributed deployments:

```bash
npm install mongodb
```

```javascript
const { MongoClient } = require('mongodb');
const EncryptedServer = require('indexedcp/lib/encrypted-server');

const mongoClient = await MongoClient.connect('mongodb://localhost:27017');

const server = new EncryptedServer({
  port: 3000,
  keystoreType: 'mongodb',
  keystoreOptions: {
    client: mongoClient
  }
});

await server.listen(3000);
// ✓ Keys saved to MongoDB indexedcp.server_keys collection
```

### Memory (Testing)

For ephemeral test environments:

```javascript
const server = new EncryptedServer({
  port: 3000,
  keystoreType: 'memory'
});

await server.listen(3000);
// ⚠️ Keys lost on restart!
```

## Configuration

### All Options

```javascript
{
  // Which keystore to use
  keystoreType: 'filesystem' | 'mongodb' | 'memory',
  
  // Type-specific options
  keystoreOptions: {
    // === Filesystem ===
    keyStorePath: './server-keys',         // Directory for JSON files
    
    // === MongoDB ===
    client: mongoClient,                   // MongoClient instance (required)
    databaseName: 'indexedcp',             // Database name
    collectionName: 'server_keys'          // Collection name
  },
  
  // Global options
  maxKeyAge: 90 * 24 * 60 * 60 * 1000     // 90 days (cleanup threshold)
}
```

## Comparison

| Feature | Filesystem | MongoDB | Memory |
|---------|-----------|---------|--------|
| **Persistence** | ✅ Disk | ✅ Database | ❌ None |
| **Multi-Server** | ❌ Local only | ✅ Shared | ❌ Local only |
| **Setup** | None | `npm install mongodb` | None |
| **Performance** | Fast | Fast | Fastest |
| **Use Case** | Single server | Production | Testing |

## Key Lifecycle

```
1. Server starts → Initialize keystore
2. Load persisted keys (if any)
3. Generate initial key (if needed)
4. Server ready ✓

During operation:
5. Rotate keys → New key generated
6. Old key deactivated (but kept)
7. Both keys persisted
8. Old keys cleaned up after maxKeyAge
```

## Examples

### Check Keystore Status

```javascript
const status = server.getEncryptionStatus();
console.log(`Active key: ${status.activeKeyId}`);
console.log(`Total keys: ${status.totalKeys}`);
```

### Manual Key Rotation

```javascript
const newKid = await server.rotateKeys();
console.log(`Rotated to ${newKid}`);
// Old keys still available for decryption
```

### Custom Cleanup Age

```javascript
const server = new EncryptedServer({
  port: 3000,
  maxKeyAge: 30 * 24 * 60 * 60 * 1000  // 30 days instead of 90
});
```

## Troubleshooting

### "Unknown key ID" errors

**Symptom**: Server can't decrypt client data after restart

**Cause**: Using memory keystore or no keystore

**Fix**: Switch to filesystem or mongodb keystore:

```javascript
const server = new EncryptedServer({
  keystoreType: 'filesystem'  // Add this line
});
```

### MongoDB connection issues

**Symptom**: `MongoClient is required` error

**Fix**: Pass connected MongoClient:

```javascript
const mongoClient = await MongoClient.connect('mongodb://localhost:27017');

const server = new EncryptedServer({
  keystoreType: 'mongodb',
  keystoreOptions: {
    client: mongoClient  // Must pass client instance
  }
});
```

### Keys not persisting

**Check 1**: Verify keystore type
```javascript
console.log(server.keyStore.constructor.name);
// Should be: FileSystemKeyStore or MongoDBKeyStore
```

**Check 2**: Check file permissions (filesystem)
```bash
ls -la ./server-keys/
# Should show .json files
```

**Check 3**: Check MongoDB connection (mongodb)
```javascript
const db = mongoClient.db('indexedcp');
const keys = await db.collection('server_keys').find({}).toArray();
console.log(`Keys in MongoDB: ${keys.length}`);
```

## Migration

### From Memory to Filesystem

**Before** (keys lost on restart):
```javascript
const server = new EncryptedServer({ port: 3000 });
```

**After** (keys persist):
```javascript
const server = new EncryptedServer({
  port: 3000,
  keystoreType: 'filesystem'  // Add this
});
```

No other changes needed!

### From Filesystem to MongoDB

**Step 1**: Install mongodb
```bash
npm install mongodb
```

**Step 2**: Update configuration
```javascript
const { MongoClient } = require('mongodb');
const mongoClient = await MongoClient.connect('mongodb://localhost:27017');

const server = new EncryptedServer({
  port: 3000,
  keystoreType: 'mongodb',              // Change this
  keystoreOptions: {                    // Add this
    client: mongoClient
  }
});
```

**Step 3**: (Optional) Migrate existing keys
```bash
# Copy filesystem keys to MongoDB
node scripts/migrate-keys.js --from filesystem --to mongodb
```

## Security Notes

### Filesystem Keystore
- Keys stored as JSON files: `<keyStorePath>/<kid>.json`
- Contains private keys - secure this directory!
- Recommended: Use file permissions (e.g., `chmod 600`)
- Consider encrypting the filesystem

### MongoDB Keystore
- Keys stored in MongoDB collection
- Use authentication: `mongodb://user:pass@host:27017`
- Enable encryption at rest
- Use TLS/SSL for connections
- Consider field-level encryption

### Key Rotation
- Rotate keys regularly (monthly/quarterly)
- Old keys remain available for 90 days (configurable)
- Monitor `maxKeyAge` and adjust as needed

## Further Reading

- [Full Documentation](./ENCRYPTION.md) - Complete encryption guide
- [Implementation Summary](./KEYSTORE-SUMMARY.md) - Technical details
- [Quick Reference](./ENCRYPTION-QUICKREF.md) - API cheat sheet
- [Examples](../examples/) - Working code examples

## Support

Issues or questions? Check:
1. This guide
2. [Troubleshooting section](./ENCRYPTION.md#troubleshooting)
3. [GitHub Issues](https://github.com/your-repo/issues)
