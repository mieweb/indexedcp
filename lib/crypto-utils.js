const crypto = require('crypto');

/**
 * Cryptographic utilities for asymmetric envelope encryption
 * 
 * Design:
 * - RSA-OAEP (SHA-256) for key wrapping
 * - AES-256-GCM for data encryption
 * - Per-stream ephemeral session keys
 * - IV + AAD for authenticity and uniqueness
 */

class CryptoUtils {
  constructor() {
    this.AES_KEY_LENGTH = 32; // 256 bits
    this.IV_LENGTH = 12; // 96 bits for GCM
    this.AUTH_TAG_LENGTH = 16; // 128 bits
  }

  /**
   * Generate RSA key pair for server
   * @param {number} modulusLength - Key size in bits (default: 4096)
   * @returns {Promise<{publicKey: string, privateKey: string, kid: string}>}
   */
  async generateServerKeyPair(modulusLength = 4096) {
    return new Promise((resolve, reject) => {
      crypto.generateKeyPair(
        'rsa',
        {
          modulusLength,
          publicKeyEncoding: {
            type: 'spki',
            format: 'pem'
          },
          privateKeyEncoding: {
            type: 'pkcs8',
            format: 'pem'
          }
        },
        (err, publicKey, privateKey) => {
          if (err) {
            reject(err);
          } else {
            // Generate key ID from public key hash
            const kid = crypto
              .createHash('sha256')
              .update(publicKey)
              .digest('hex')
              .substring(0, 16);

            resolve({ publicKey, privateKey, kid });
          }
        }
      );
    });
  }

  /**
   * Generate ephemeral AES session key
   * @returns {Buffer} 256-bit AES key
   */
  generateSessionKey() {
    return crypto.randomBytes(this.AES_KEY_LENGTH);
  }

  /**
   * Wrap (encrypt) an AES session key with RSA public key
   * @param {Buffer} sessionKey - AES key to wrap
   * @param {string} publicKeyPem - RSA public key in PEM format
   * @returns {Buffer} Wrapped (encrypted) session key
   */
  wrapSessionKey(sessionKey, publicKeyPem) {
    const publicKey = crypto.createPublicKey(publicKeyPem);
    
    return crypto.publicEncrypt(
      {
        key: publicKey,
        padding: crypto.constants.RSA_PKCS1_OAEP_PADDING,
        oaepHash: 'sha256'
      },
      sessionKey
    );
  }

  /**
   * Unwrap (decrypt) an AES session key with RSA private key
   * @param {Buffer} wrappedKey - Encrypted session key
   * @param {string} privateKeyPem - RSA private key in PEM format
   * @returns {Buffer} Unwrapped AES session key
   */
  unwrapSessionKey(wrappedKey, privateKeyPem) {
    const privateKey = crypto.createPrivateKey(privateKeyPem);
    
    return crypto.privateDecrypt(
      {
        key: privateKey,
        padding: crypto.constants.RSA_PKCS1_OAEP_PADDING,
        oaepHash: 'sha256'
      },
      wrappedKey
    );
  }

  /**
   * Encrypt data with AES-GCM
   * @param {Buffer} data - Plaintext to encrypt
   * @param {Buffer} sessionKey - AES session key
   * @param {Object} metadata - Additional authenticated data (sessionId, seq, etc.)
   * @returns {Object} {ciphertext, iv, authTag, aad}
   */
  encryptPacket(data, sessionKey, metadata) {
    // Generate unique IV for this packet
    const iv = crypto.randomBytes(this.IV_LENGTH);
    
    // Prepare AAD (Additional Authenticated Data)
    const aad = Buffer.from(JSON.stringify({
      sessionId: metadata.sessionId,
      seq: metadata.seq,
      codec: metadata.codec || 'raw',
      timestamp: metadata.timestamp || Date.now()
    }));

    // Create cipher
    const cipher = crypto.createCipheriv('aes-256-gcm', sessionKey, iv);
    cipher.setAAD(aad);

    // Encrypt
    const ciphertext = Buffer.concat([
      cipher.update(data),
      cipher.final()
    ]);

    // Get authentication tag
    const authTag = cipher.getAuthTag();

    return {
      ciphertext,
      iv,
      authTag,
      aad
    };
  }

  /**
   * Decrypt data with AES-GCM
   * @param {Buffer} ciphertext - Encrypted data
   * @param {Buffer} sessionKey - AES session key
   * @param {Buffer} iv - Initialization vector
   * @param {Buffer} authTag - Authentication tag
   * @param {Buffer} aad - Additional authenticated data
   * @returns {Buffer} Decrypted plaintext
   */
  decryptPacket(ciphertext, sessionKey, iv, authTag, aad) {
    const decipher = crypto.createDecipheriv('aes-256-gcm', sessionKey, iv);
    decipher.setAAD(aad);
    decipher.setAuthTag(authTag);

    return Buffer.concat([
      decipher.update(ciphertext),
      decipher.final()
    ]);
  }

  /**
   * Serialize encrypted packet for storage
   * @param {Object} packet - Encrypted packet data
   * @returns {Object} Serialized packet suitable for IndexedDB
   */
  serializePacket(packet) {
    return {
      ciphertext: packet.ciphertext.toString('base64'),
      iv: packet.iv.toString('base64'),
      authTag: packet.authTag.toString('base64'),
      aad: packet.aad.toString('base64')
    };
  }

  /**
   * Deserialize encrypted packet from storage
   * @param {Object} serialized - Serialized packet from IndexedDB
   * @returns {Object} Packet with Buffer instances
   */
  deserializePacket(serialized) {
    return {
      ciphertext: Buffer.from(serialized.ciphertext, 'base64'),
      iv: Buffer.from(serialized.iv, 'base64'),
      authTag: Buffer.from(serialized.authTag, 'base64'),
      aad: Buffer.from(serialized.aad, 'base64')
    };
  }

  /**
   * Parse AAD to extract metadata
   * @param {Buffer} aad - Additional authenticated data
   * @returns {Object} Metadata object
   */
  parseAAD(aad) {
    return JSON.parse(aad.toString());
  }

  /**
   * Validate key ID format
   * @param {string} kid - Key ID to validate
   * @returns {boolean}
   */
  isValidKeyId(kid) {
    return typeof kid === 'string' && /^[a-f0-9]{16}$/.test(kid);
  }

  /**
   * Generate session ID
   * @returns {string} Unique session identifier
   */
  generateSessionId() {
    return crypto.randomBytes(16).toString('hex');
  }
}

module.exports = new CryptoUtils();
