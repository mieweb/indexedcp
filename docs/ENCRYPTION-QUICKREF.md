# Encryption Quick Reference

> **📢 API Update (2024-12-08)**: Encryption has been integrated into the main `IndexedCPServer` and `IndexedCPClient` classes with an `encryption: true` flag. The separate `EncryptedServer` and `EncryptedClient` classes are deprecated. See [MIGRATION-GUIDE.md](./MIGRATION-GUIDE.md) for migration instructions.

## 🚀 Quick Start (5 minutes)

### Server Setup
```javascript
const { IndexedCPServer } = require('indexedcp/lib/server');
const server = new IndexedCPServer({ 
  port: 3000,
  encryption: true,  // Enable encryption support
  keystoreType: 'filesystem'  // Or 'mongodb', 'memory'
});
await server.listen(3000);
// ✓ RSA key pair generated automatically
// ✓ Keys persisted to keystore (survives restarts)
// ✓ Public key available at GET /public-key
```

### Server Setup with MongoDB
```javascript
const { MongoClient } = require('mongodb');
const mongoClient = await MongoClient.connect('mongodb://localhost:27017');

const { IndexedCPServer } = require('indexedcp/lib/server');
const server = new IndexedCPServer({ 
  port: 3000,
  encryption: true,  // Enable encryption support
  keystoreType: 'mongodb',
  keystoreOptions: {
    client: mongoClient,
    databaseName: 'indexedcp',
    collectionName: 'server_keys'
  }
});
await server.listen(3000);
```

### Client Usage
```javascript
const IndexedCPClient = require('indexedcp/lib/client');
const client = new IndexedCPClient({
  serverUrl: 'http://localhost:3000',
  apiKey: 'your-api-key',
  encryption: true  // Enable encryption support
});

// 1. Fetch key (once)
await client.fetchPublicKey();

// 2. Encrypt files
await client.addFile('./sensitive.txt');

// 3. Upload
await client.uploadBufferedFiles('http://localhost:3000');
```

## 📋 Cheat Sheet

### Client Methods
| Method | Purpose | When |
|--------|---------|------|
| `fetchPublicKey()` | Get server's public key | Before first use |
| `getCachedPublicKey()` | Load cached key | For offline mode |
| `startStream(fileName)` | Begin new session | Manual streaming |
| `addPacket(sessionId, data, seq)` | Encrypt single packet | Manual streaming |
| `addFile(filePath)` | Encrypt entire file | Most common |
| `uploadBufferedFiles(url)` | Upload all queued data | When online |
| `getEncryptionStatus()` | Check state | Debugging |

### Server Methods
| Method | Purpose | When |
|--------|---------|------|
| `generateKeyPair()` | Create RSA keys | Auto on start |
| `getActivePublicKey()` | Get current key | Manual key serving |
| `rotateKeys()` | Generate new key | Monthly/quarterly |
| `getEncryptionStatus()` | Check state | Monitoring |

### Server Endpoints
| Endpoint | Method | Auth | Purpose |
|----------|--------|------|---------|
| `/public-key` | GET | No | Fetch public key |
| `/upload-encrypted` | POST | Yes | Upload encrypted data |
| `/rotate-keys` | POST | Yes | Trigger rotation |

### Keystore Options
| Type | Persistence | Use Case | Setup |
|------|-------------|----------|-------|
| `filesystem` | Disk | Single server, default | `keystoreType: 'filesystem'` |
| `mongodb` | MongoDB | Multi-server, production | Requires `mongodb` package + client |
| `memory` | None | Testing only | `keystoreType: 'memory'` |
| Custom | Depends | Redis, PostgreSQL, etc. | Extend `BaseKeyStore` |

**Keystore Configuration:**
```javascript
{
  keystoreType: 'filesystem',      // or 'mongodb', 'memory'
  keystoreOptions: {
    // Filesystem
    keyStorePath: './server-keys',
    
    // MongoDB
    client: mongoClient,
    databaseName: 'indexedcp',
    collectionName: 'server_keys'
  },
  maxKeyAge: 90 * 24 * 60 * 60 * 1000  // 90 days
}
```

## 🔐 Security Checklist

### Production Deployment
- [ ] Use HTTPS for all endpoints
- [ ] Rotate keys monthly/quarterly
- [ ] Store API keys in environment variables
- [ ] Monitor key expiration dates
- [ ] Implement rate limiting on `/public-key`
- [ ] Log all encryption/decryption operations
- [ ] Test key rotation process
- [ ] Back up server private keys securely
- [ ] Implement key recovery procedures
- [ ] Test offline-to-online transitions

### Code Security
- [ ] Never log unwrapped session keys
- [ ] Clear session keys after use (automatic)
- [ ] Validate all packet structures
- [ ] Check key IDs match expected values
- [ ] Handle AAD mismatches gracefully
- [ ] Test with corrupted packets
- [ ] Verify IV uniqueness
- [ ] Test authentication tag validation

## 🛠️ Troubleshooting

### "No public key available"
```javascript
// Ensure server is running
// Call fetchPublicKey() before encrypting
await client.fetchPublicKey();

// Or check cached keys
const cached = await client.getCachedPublicKey();
if (!cached) {
  // Need to connect online first
}
```

### "Unknown key ID"
```javascript
// Possible causes:
// 1. Server restarted with memory keystore
// 2. Key expired (check maxKeyAge)
// 3. Wrong server

// With filesystem/mongodb keystore: keys persist automatically
// Check keystore configuration:
const status = server.getEncryptionStatus();
console.log('Total keys:', status.totalKeys);

// If using memory keystore, switch to filesystem:
const server = new EncryptedServer({
  keystoreType: 'filesystem'  // Keys persist across restarts
});
```

### "Decryption failed"
```javascript
// Possible causes:
// 1. Wrong key (check kid matches)
// 2. Packet corruption
// 3. AAD mismatch

// Debug:
const packet = await db.get('packets', packetId);
console.log('Packet kid:', packet.kid);
console.log('Server has kid:', server.keyPairs.has(packet.kid));
```

### Performance Issues
```javascript
// Reduce chunk size
const client = new EncryptedClient({
  chunkSize: 512 * 1024 // 512KB instead of 1MB
});

// Check encryption overhead
const start = Date.now();
await client.addFile(largFile);
console.log('Time:', Date.now() - start);
```

## 📊 Performance Targets

| Operation | Target | Typical |
|-----------|--------|---------|
| Key generation | < 3s | ~2s |
| Key wrapping | < 10ms | ~5ms |
| Packet encryption (1MB) | < 100ms | ~17ms |
| Packet decryption (1MB) | < 100ms | ~17ms |
| Throughput | > 10 MB/s | ~17 MB/s |

## 🧪 Testing Commands

```bash
# Run all encryption tests
npm run test:encryption

# Run all tests (includes encryption)
npm test

# Run encryption demo
node examples/encryption-demo.js

# Run examples
node examples/encrypted-server.js &
node examples/encrypted-client.js
```

## 📚 API Payload Examples

### Fetch Public Key
```bash
curl http://localhost:3000/public-key
```
Response:
```json
{
  "publicKey": "-----BEGIN PUBLIC KEY-----\n...",
  "kid": "a1b2c3d4e5f6g7h8",
  "expiresAt": 1731384650117
}
```

### Upload Encrypted Packet
```bash
curl -X POST http://localhost:3000/upload-encrypted \
  -H "Authorization: Bearer your-api-key" \
  -H "Content-Type: application/json" \
  -d '{
    "sessionId": "abc123...",
    "seq": 0,
    "kid": "a1b2c3d4e5f6g7h8",
    "wrappedKey": "base64...",
    "ciphertext": "base64...",
    "iv": "base64...",
    "authTag": "base64...",
    "aad": "base64...",
    "fileName": "test.txt"
  }'
```
Response:
```json
{
  "message": "Encrypted packet received and decrypted",
  "sessionId": "abc123...",
  "seq": 0,
  "actualFilename": "1234567890_abc_test.txt"
}
```

### Rotate Keys
```bash
curl -X POST http://localhost:3000/rotate-keys \
  -H "Authorization: Bearer your-api-key"
```
Response:
```json
{
  "message": "Keys rotated successfully",
  "kid": "new-key-id"
}
```

## 🔧 Environment Variables

```bash
# Client
export INDEXEDCP_API_KEY=your-api-key
export INDEXEDCP_ENCRYPTION=true  # Enable encryption (default)

# Server
export PORT=3000
export API_KEY=your-api-key
export OUTPUT_DIR=./uploads
```

## 📖 Further Reading

- [Full Documentation](./ENCRYPTION.md) - Complete encryption guide
- [Implementation Summary](./ENCRYPTION-SUMMARY.md) - Technical details
- [Main README](../README.md) - Project overview
- [Examples](../examples/) - Working code samples

## 💡 Best Practices

### DO ✅
- Always use HTTPS in production
- Rotate keys regularly (monthly recommended)
- Cache public key for offline use
- Test offline-to-online transitions
- Monitor key expiration
- Log all encryption operations
- Validate all inputs

### DON'T ❌
- Log unwrapped session keys
- Hardcode API keys in source
- Skip HTTPS in production
- Ignore key expiration warnings
- Reuse IVs (auto-generated)
- Store private keys in VCS
- Trust client-provided keys

## 🐛 Debug Mode

```javascript
// Enable verbose logging (if implemented)
const client = new EncryptedClient({
  verbose: true,
  serverUrl: 'http://localhost:3000'
});

// Check internal state
console.log('Active streams:', client.activeStreams.size);
console.log('Cached key:', client.cachedKeyId);
console.log('Key expires:', new Date(client.keyExpiresAt));

// Server state
console.log('Active key:', server.activeKeyId);
console.log('Total keys:', server.keyPairs.size);
console.log('Sessions:', server.sessionCache.size);
```

## 📞 Support

- GitHub Issues: [mieweb/IndexedCP](https://github.com/mieweb/IndexedCP)
- Documentation: `docs/ENCRYPTION.md`
- Examples: `examples/encrypted-*.js`
- Tests: `tests/test-encryption.js`

---

**Last Updated**: October 2025  
**Version**: 1.0.0  
**Status**: Production Ready
