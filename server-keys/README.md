# Server Keys Directory

⚠️ **SECURITY WARNING** ⚠️

This directory contains **RSA private keys** used by the EncryptedServer to decrypt client data.

## Important Security Notes

🔒 **Never commit these files to version control**  
- Already excluded in `.gitignore`
- Private keys must remain secret

🔒 **Secure this directory in production**
```bash
# Recommended permissions
chmod 700 server-keys/
chmod 600 server-keys/*.json
```

🔒 **Backup these keys securely**
- Without these keys, client data cannot be decrypted
- Store backups in encrypted, access-controlled storage
- Consider using hardware security modules (HSMs) for production

## File Format

Each file is named `<kid>.json` where `kid` is the key ID.

```json
{
  "kid": "unique-key-identifier",
  "publicKey": "-----BEGIN PUBLIC KEY-----\n...",
  "privateKey": "-----BEGIN PRIVATE KEY-----\n...",
  "createdAt": 1234567890000,
  "active": true
}
```

## Key Lifecycle

- **Active keys** are used for new client encryptions
- **Inactive keys** are retained to decrypt old client data
- **Expired keys** are automatically cleaned up based on `maxKeyAge`

## Switching to MongoDB

For production deployments with multiple servers, consider using MongoDB keystore:

```javascript
const server = new EncryptedServer({
  keystoreType: 'mongodb',
  keystoreOptions: {
    client: mongoClient
  }
});
```

See [KEYSTORE-QUICKSTART.md](../docs/KEYSTORE-QUICKSTART.md) for details.

## Key Rotation

Keys are rotated via:
```javascript
await server.rotateKeys();
```

Old keys remain in this directory for decrypting existing client data.

## Recovery

If keys are lost:
- ❌ Client data encrypted with those keys **cannot be decrypted**
- ✅ New clients can fetch new public keys and continue
- ⚠️ Backup strategy is critical!

## Further Reading

- [Encryption Documentation](../docs/ENCRYPTION.md)
- [Keystore Quick Start](../docs/KEYSTORE-QUICKSTART.md)
- [Security Best Practices](../docs/ENCRYPTION.md#security-model)
