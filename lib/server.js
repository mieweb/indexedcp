const http = require('http');
const fs = require('fs');
const path = require('path');
const crypto = require('crypto');

class IndexCPServer {
  constructor(options = {}) {
    this.outputDir = options.outputDir || process.cwd();
    this.port = options.port || 3000;
    this.apiKey = options.apiKey || this.generateApiKey();
    this.filenameGenerator = options.filenameGenerator || null; // Optional custom filename generator
    
    // Path handling mode:
    // 'ignore' (default) - Generate unique filenames with original name appended
    // 'sanitize' - Strip all paths, prevent overwrites with unique suffix
    // 'allow-paths' - Allow client to create subdirectories
    this.pathMode = options.pathMode || 'ignore';
    
    // Track filenames across chunks for the same upload session
    this.uploadSessions = new Map(); // clientFileName -> actualFileName
    
    // Encryption support (optional)
    this.encryption = options.encryption || false;
    
    if (this.encryption) {
      // Load encryption modules only if needed
      const cryptoUtils = require('./crypto-utils');
      const { createKeyStore } = require('./keystores');
      
      this.cryptoUtils = cryptoUtils;
      this.keyPairs = new Map(); // kid -> { publicKey, privateKey, createdAt, active }
      this.activeKeyId = null;
      this.sessionCache = new Map(); // sessionId -> unwrapped AES key
      
      // Keystore configuration
      if (options.keyStore) {
        this.keyStore = options.keyStore;
      } else {
        const keystoreType = options.keystoreType || 'filesystem';
        const keystoreOptions = options.keystoreOptions || {};
        this.keyStore = createKeyStore(keystoreType, keystoreOptions);
      }
      
      this.maxKeyAge = options.maxKeyAge || (90 * 24 * 60 * 60 * 1000); // 90 days default
    }
    
    this.server = null;
  }

  generateApiKey() {
    return crypto.randomBytes(32).toString('hex');
  }

  // ============================================================================
  // Encryption Methods (only used when encryption: true)
  // ============================================================================

  /**
   * Load persisted keys from keystore on startup
   * @private
   */
  async loadPersistedKeys() {
    if (!this.encryption) return;
    
    try {
      const keys = await this.keyStore.loadAll();
      
      for (const keyData of keys) {
        this.keyPairs.set(keyData.kid, {
          publicKey: keyData.publicKey,
          privateKey: keyData.privateKey,
          createdAt: keyData.createdAt,
          active: keyData.active
        });
        
        if (keyData.active) {
          this.activeKeyId = keyData.kid;
        }
      }
      
      console.log(`✓ Loaded ${keys.length} persisted key pair(s) from keystore`);
      if (this.activeKeyId) {
        console.log(`  Active key: ${this.activeKeyId}`);
      }
    } catch (error) {
      console.warn('⚠ Failed to load persisted keys:', error.message);
    }
  }

  /**
   * Persist key pair to keystore
   * @private
   */
  async persistKeyPair(keyData) {
    if (!this.encryption) return;
    
    try {
      await this.keyStore.save(keyData.kid, {
        kid: keyData.kid,
        publicKey: keyData.publicKey,
        privateKey: keyData.privateKey,
        createdAt: keyData.createdAt,
        active: keyData.active
      });
      console.log(`✓ Persisted key pair ${keyData.kid} to keystore`);
    } catch (error) {
      console.error('✗ Failed to persist key pair:', error);
      throw error;
    }
  }

  /**
   * Cleanup expired keys from keystore
   * @private
   */
  async cleanupExpiredKeys() {
    if (!this.encryption) return;
    
    const now = Date.now();
    const expiredKeys = [];
    
    for (const [kid, keyData] of this.keyPairs.entries()) {
      const age = now - keyData.createdAt;
      if (age > this.maxKeyAge) {
        expiredKeys.push(kid);
      }
    }
    
    for (const kid of expiredKeys) {
      try {
        await this.keyStore.delete(kid);
        this.keyPairs.delete(kid);
        console.log(`✓ Cleaned up expired key: ${kid}`);
      } catch (error) {
        console.warn(`⚠ Failed to cleanup key ${kid}:`, error.message);
      }
    }
    
    if (expiredKeys.length > 0) {
      console.log(`✓ Cleaned up ${expiredKeys.length} expired key(s)`);
    }
  }

  /**
   * Generate and activate a new RSA key pair
   * @returns {Promise<string>} Key ID
   */
  async generateKeyPair() {
    if (!this.encryption) {
      throw new Error('Encryption not enabled. Set encryption: true in constructor.');
    }
    
    const keyPair = await this.cryptoUtils.generateServerKeyPair();
    
    const keyData = {
      publicKey: keyPair.publicKey,
      privateKey: keyPair.privateKey,
      createdAt: Date.now(),
      active: true,
      kid: keyPair.kid
    };
    
    this.keyPairs.set(keyPair.kid, keyData);
    
    // Deactivate old keys (but keep them for decryption)
    if (this.activeKeyId && this.activeKeyId !== keyPair.kid) {
      const oldKey = this.keyPairs.get(this.activeKeyId);
      if (oldKey) {
        oldKey.active = false;
        // Ensure kid is set (for keys loaded from old versions)
        if (!oldKey.kid) {
          oldKey.kid = this.activeKeyId;
        }
        // Update old key in keystore
        await this.persistKeyPair(oldKey);
      }
    }
    
    this.activeKeyId = keyPair.kid;
    
    // Persist new key to keystore
    await this.persistKeyPair(keyData);
    
    console.log(`✓ Generated new RSA key pair (kid: ${keyPair.kid})`);
    return keyPair.kid;
  }

  /**
   * Get active public key
   */
  getActivePublicKey() {
    if (!this.encryption) {
      throw new Error('Encryption not enabled. Set encryption: true in constructor.');
    }
    
    if (!this.activeKeyId) {
      throw new Error('No active key pair. Call generateKeyPair() first.');
    }
    
    const keyPair = this.keyPairs.get(this.activeKeyId);
    return {
      publicKey: keyPair.publicKey,
      kid: this.activeKeyId,
      expiresAt: keyPair.createdAt + (30 * 24 * 60 * 60 * 1000) // 30 days
    };
  }

  /**
   * Get private key by kid
   */
  getPrivateKey(kid) {
    if (!this.encryption) {
      throw new Error('Encryption not enabled. Set encryption: true in constructor.');
    }
    
    const keyPair = this.keyPairs.get(kid);
    if (!keyPair) {
      throw new Error(`Unknown key ID: ${kid}`);
    }
    return keyPair.privateKey;
  }

  /**
   * Rotate keys (AC4)
   */
  async rotateKeys() {
    if (!this.encryption) {
      throw new Error('Encryption not enabled. Set encryption: true in constructor.');
    }
    
    console.log('🔄 Rotating encryption keys...');
    const newKid = await this.generateKeyPair();
    console.log(`✓ Key rotation complete. New kid: ${newKid}`);
    console.log(`  Old keys remain available for decryption`);
    return newKid;
  }

  /**
   * Get server encryption status
   */
  getEncryptionStatus() {
    if (!this.encryption) {
      return { encryption: false };
    }
    
    return {
      encryption: true,
      activeKeyId: this.activeKeyId,
      totalKeys: this.keyPairs.size,
      activeSessions: this.sessionCache.size
    };
  }

  // ============================================================================
  // End Encryption Methods
  // ============================================================================

  createServer() {
    this.server = http.createServer((req, res) => {
      // CORS headers for browser clients
      res.setHeader('Access-Control-Allow-Origin', '*');
      res.setHeader('Access-Control-Allow-Methods', 'GET, POST, OPTIONS');
      res.setHeader('Access-Control-Allow-Headers', 'Content-Type, Authorization, X-Chunk-Index, X-File-Name');
      
      if (req.method === 'OPTIONS') {
        res.writeHead(200);
        res.end();
        return;
      }

      // Public key endpoint (unauthenticated, encryption only)
      if (this.encryption && req.method === 'GET' && req.url === '/public-key') {
        this.handlePublicKeyRequest(req, res);
        return;
      }

      // Authenticate all other endpoints
      const authHeader = req.headers['authorization'];
      const providedApiKey = authHeader && authHeader.startsWith('Bearer ') 
        ? authHeader.slice(7) 
        : null;
        
      if (!providedApiKey || providedApiKey !== this.apiKey) {
        res.writeHead(401, { 'Content-Type': 'application/json' });
        res.end(JSON.stringify({ error: 'Invalid or missing API key' }));
        return;
      }

      // Route requests
      if (req.method === 'POST' && req.url === '/upload') {
        this.handleUpload(req, res);
      } else if (this.encryption && req.method === 'POST' && req.url === '/upload-encrypted') {
        this.handleEncryptedUpload(req, res);
      } else if (this.encryption && req.method === 'POST' && req.url === '/rotate-keys') {
        this.handleKeyRotation(req, res);
      } else {
        res.writeHead(404);
        res.end('Not Found');
      }
    });

    return this.server;
  }

  handleUpload(req, res) {
    const chunkIndex = req.headers['x-chunk-index'];
    const clientFileName = req.headers['x-file-name'] || 'uploaded_file.txt';
    
    let outputFile;
    let actualFileName;
    
    // Handle different path modes
    if (this.pathMode === 'ignore') {
      // Mode: 'ignore' - Generate unique filename with full path preserved
      const timestamp = Date.now();
      const random = crypto.randomBytes(4).toString('hex');
      
      // Preserve full path by replacing separators with single underscore
      // Strip leading ./ or .\
      let fullPath = clientFileName.replace(/^\.\//, '').replace(/^\.\\/, '');
      
      // Replace path separators with single underscore
      fullPath = fullPath.replace(/[/\\]+/g, '_');
      
      // Extract extension
      const ext = path.extname(fullPath);
      const nameWithoutExt = fullPath.slice(0, fullPath.length - ext.length);
      
      // Sanitize to be filesystem-safe:
      // - Keep letters, numbers, underscores (path markers), dots, and existing dashes
      // - Replace all other characters with dash
      const safeName = nameWithoutExt.replace(/[^a-zA-Z0-9._-]/g, '-');
      
      // Format: <timestamp>_<random>_<full-path-with-underscores>.<ext>
      let proposedName = `${timestamp}_${random}_${safeName}${ext}`;
      
      // Check filename length (most filesystems support 255 chars)
      const MAX_FILENAME_LENGTH = 255;
      if (proposedName.length > MAX_FILENAME_LENGTH) {
        // Truncate the safe name part to fit
        const prefixLength = `${timestamp}_${random}_`.length;
        const maxSafeNameLength = MAX_FILENAME_LENGTH - prefixLength - ext.length;
        const truncatedName = safeName.slice(0, maxSafeNameLength);
        proposedName = `${timestamp}_${random}_${truncatedName}${ext}`;
      }
      
      actualFileName = proposedName;
      outputFile = path.join(this.outputDir, actualFileName);
      
    } else if (this.pathMode === 'allow-paths') {
      // Mode: 'allow-paths' - Allow subdirectories from client
      // Still protect against traversal attacks
      const cleanedFileName = clientFileName.replace(/^\.\//, '').replace(/^\.\\/, '');
      
      // Reject traversal attempts and absolute paths
      const hasTraversal = cleanedFileName.includes('..');
      const hasAbsolutePath = cleanedFileName.startsWith('/') || 
                             /^[A-Za-z]:/.test(cleanedFileName) ||
                             cleanedFileName.startsWith('\\\\');
      
      if (hasTraversal || hasAbsolutePath) {
        console.error(`Security: Rejected filename with traversal/absolute path: ${clientFileName}`);
        res.writeHead(400, { 'Content-Type': 'application/json' });
        res.end(JSON.stringify({ 
          error: 'Invalid filename',
          message: 'Filename must not contain traversal sequences or absolute paths'
        }));
        return;
      }
      
      // Allow paths but normalize separators
      actualFileName = cleanedFileName.split(/[/\\]+/).join(path.sep);
      outputFile = path.join(this.outputDir, actualFileName);
      
      // Security: Verify the resolved path is inside outputDir
      const resolvedOutputFile = path.resolve(outputFile);
      const resolvedOutputDir = path.resolve(this.outputDir);
      if (!resolvedOutputFile.startsWith(resolvedOutputDir + path.sep) && 
          resolvedOutputFile !== resolvedOutputDir) {
        console.error(`Security: Path traversal attempt blocked: ${clientFileName}`);
        res.writeHead(403, { 'Content-Type': 'application/json' });
        res.end(JSON.stringify({ error: 'Access denied: invalid path' }));
        return;
      }
      
      // Create subdirectories if needed
      const outputFileDir = path.dirname(outputFile);
      if (!fs.existsSync(outputFileDir)) {
        fs.mkdirSync(outputFileDir, { recursive: true });
      }
      
    } else {
      // Mode: 'sanitize' (default) - Strip paths, prevent overwrites
      
      // Use custom generator if provided
      if (this.filenameGenerator && typeof this.filenameGenerator === 'function') {
        actualFileName = this.filenameGenerator(clientFileName, chunkIndex, req);
      } else {
        actualFileName = path.basename(clientFileName);
      }
      
      // Strip common relative path prefixes
      const cleanedFileName = clientFileName.replace(/^\.\//, '').replace(/^\.\\/, '');
      
      // Reject if filename contains path separators or traversal attempts  
      const hasPathSeparators = cleanedFileName.includes('/') || 
                                cleanedFileName.includes('\\');
      const hasTraversal = clientFileName.includes('..');
      const hasAbsolutePath = clientFileName.startsWith('/') || 
                             /^[A-Za-z]:/.test(clientFileName) ||
                             clientFileName.startsWith('\\\\');
      
      if (hasPathSeparators || hasTraversal || hasAbsolutePath) {
        console.error(`Security: Rejected filename with path components: ${clientFileName}`);
        res.writeHead(400, { 'Content-Type': 'application/json' });
        res.end(JSON.stringify({ 
          error: 'Invalid filename',
          message: 'Filename must not contain path separators or traversal sequences'
        }));
        return;
      }
      
      // Use only the basename to ensure we stay in outputDir
      const safeName = path.basename(actualFileName);
      
      // Validate that we have a valid filename after sanitization
      if (!safeName || safeName === '.' || safeName === '..' || safeName.length === 0) {
        res.writeHead(400, { 'Content-Type': 'application/json' });
        res.end(JSON.stringify({ error: 'Invalid filename' }));
        return;
      }
      
      actualFileName = safeName;
      
      // Check if we have a session for this file
      const isFirstChunk = !chunkIndex || chunkIndex === '0' || parseInt(chunkIndex) === 0;
      
      if (this.uploadSessions.has(clientFileName)) {
        // Use the same filename from the first chunk
        actualFileName = this.uploadSessions.get(clientFileName);
      } else {
        // First chunk - check for overwrites and create session
        outputFile = path.join(this.outputDir, actualFileName);
        
        if (fs.existsSync(outputFile)) {
          const ext = path.extname(actualFileName);
          const base = path.basename(actualFileName, ext);
          const timestamp = Date.now();
          actualFileName = `${base}_${timestamp}${ext}`;
        }
        
        // Store the filename for subsequent chunks
        this.uploadSessions.set(clientFileName, actualFileName);
      }
      
      outputFile = path.join(this.outputDir, actualFileName);
      
      // Security: Verify the resolved path is inside outputDir
      const resolvedOutputFile = path.resolve(outputFile);
      const resolvedOutputDir = path.resolve(this.outputDir);
      if (!resolvedOutputFile.startsWith(resolvedOutputDir + path.sep) && 
          resolvedOutputFile !== resolvedOutputDir) {
        console.error(`Security: Path traversal attempt blocked: ${clientFileName}`);
        res.writeHead(403, { 'Content-Type': 'application/json' });
        res.end(JSON.stringify({ error: 'Access denied: invalid path' }));
        return;
      }
    }
    
    // Ensure output directory exists
    if (!fs.existsSync(this.outputDir)) {
      fs.mkdirSync(this.outputDir, { recursive: true });
    }
    
    const writeStream = fs.createWriteStream(outputFile, { flags: 'a' });
    
    req.pipe(writeStream);
    
    req.on('end', () => {
      console.log(`Chunk ${chunkIndex} received for ${clientFileName} -> ${actualFileName}`);
      
      // Return response with actual filename used
      res.writeHead(200, { 'Content-Type': 'application/json' });
      res.end(JSON.stringify({
        message: 'Chunk received',
        actualFilename: actualFileName,
        chunkIndex: parseInt(chunkIndex),
        clientFilename: clientFileName
      }));
    });

    req.on('error', (error) => {
      console.error('Upload error:', error);
      if (!res.headersSent) {
        res.writeHead(500, { 'Content-Type': 'application/json' });
        res.end(JSON.stringify({ error: 'Upload error', message: error.message }));
      }
    });

    writeStream.on('error', (error) => {
      console.error('Write error:', error);
      if (!res.headersSent) {
        res.writeHead(500, { 'Content-Type': 'application/json' });
        res.end(JSON.stringify({ error: 'Write error', message: error.message }));
      }
    });
  }

  // ============================================================================
  // Encrypted Upload Handlers (only used when encryption: true)
  // ============================================================================

  /**
   * Handle public key fetch (unauthenticated)
   */
  handlePublicKeyRequest(req, res) {
    try {
      const publicKeyInfo = this.getActivePublicKey();
      res.writeHead(200, { 'Content-Type': 'application/json' });
      res.end(JSON.stringify(publicKeyInfo));
    } catch (error) {
      res.writeHead(500, { 'Content-Type': 'application/json' });
      res.end(JSON.stringify({ error: error.message }));
    }
  }

  /**
   * Handle key rotation (authenticated)
   */
  async handleKeyRotation(req, res) {
    try {
      const newKid = await this.rotateKeys();
      res.writeHead(200, { 'Content-Type': 'application/json' });
      res.end(JSON.stringify({ 
        message: 'Keys rotated successfully',
        newKeyId: newKid 
      }));
    } catch (error) {
      res.writeHead(500, { 'Content-Type': 'application/json' });
      res.end(JSON.stringify({ error: error.message }));
    }
  }

  /**
   * Handle encrypted packet upload
   */
  async handleEncryptedUpload(req, res) {
    let body = '';
    
    req.on('data', chunk => {
      body += chunk.toString();
    });
    
    req.on('end', async () => {
      try {
        const packet = JSON.parse(body);
        
        // Validate packet structure
        if (!packet.sessionId || !packet.kid || !packet.wrappedKey || 
            !packet.ciphertext || !packet.iv || !packet.authTag || !packet.aad) {
          res.writeHead(400, { 'Content-Type': 'application/json' });
          res.end(JSON.stringify({ error: 'Invalid packet structure' }));
          return;
        }
        
        // Get or unwrap session key
        let sessionKey = this.sessionCache.get(packet.sessionId);
        
        if (!sessionKey) {
          // Unwrap session key using server's private key
          const privateKey = this.getPrivateKey(packet.kid);
          const wrappedKeyBuffer = Buffer.from(packet.wrappedKey, 'base64');
          sessionKey = await this.cryptoUtils.unwrapSessionKey(
            wrappedKeyBuffer,
            privateKey
          );
          
          // Cache the unwrapped key for this session
          this.sessionCache.set(packet.sessionId, sessionKey);
        }
        
        // Decrypt packet
        const ciphertextBuffer = Buffer.from(packet.ciphertext, 'base64');
        const ivBuffer = Buffer.from(packet.iv, 'base64');
        const authTagBuffer = Buffer.from(packet.authTag, 'base64');
        const aadBuffer = Buffer.from(packet.aad, 'base64');
        
        const plaintext = await this.cryptoUtils.decryptPacket(
          ciphertextBuffer,
          sessionKey,
          ivBuffer,
          authTagBuffer,
          aadBuffer
        );
        
        // Generate filename for this packet
        const fileName = packet.fileName || `session-${packet.sessionId}.txt`;
        const chunkIndex = packet.seq || 0;
        
        // Use existing handleUpload logic by setting appropriate headers
        const fakeReq = {
          headers: {
            'x-chunk-index': chunkIndex.toString(),
            'x-file-name': `session:${packet.sessionId}`
          },
          pipe: (writeStream) => {
            writeStream.write(plaintext);
            writeStream.end();
          },
          on: (event, handler) => {
            if (event === 'end') {
              // Call immediately since we already have all data
              setImmediate(handler);
            }
          }
        };
        
        // Ensure output directory exists
        if (!fs.existsSync(this.outputDir)) {
          fs.mkdirSync(this.outputDir, { recursive: true });
        }
        
        // Generate output filename
        let actualFileName;
        const sessionCacheKey = `session:${packet.sessionId}`;
        
        if (this.uploadSessions.has(sessionCacheKey)) {
          actualFileName = this.uploadSessions.get(sessionCacheKey);
        } else {
          const timestamp = Date.now();
          const random = crypto.randomBytes(4).toString('hex');
          const ext = path.extname(fileName);
          const baseName = path.basename(fileName, ext);
          actualFileName = `${timestamp}_${random}_${baseName}${ext}`;
          this.uploadSessions.set(sessionCacheKey, actualFileName);
        }
        
        const outputFile = path.join(this.outputDir, actualFileName);
        const writeStream = fs.createWriteStream(outputFile, { flags: 'a' });
        
        writeStream.write(plaintext);
        writeStream.end();
        
        writeStream.on('finish', () => {
          console.log(`✓ Decrypted and saved packet ${packet.seq} for session ${packet.sessionId}`);
          res.writeHead(200, { 'Content-Type': 'application/json' });
          res.end(JSON.stringify({
            message: 'Packet decrypted and saved',
            actualFilename: actualFileName
          }));
        });
        
        writeStream.on('error', (error) => {
          console.error('Write error:', error);
          res.writeHead(500, { 'Content-Type': 'application/json' });
          res.end(JSON.stringify({ error: 'Write error', message: error.message }));
        });
        
      } catch (error) {
        console.error('Decryption error:', error);
        res.writeHead(500, { 'Content-Type': 'application/json' });
        res.end(JSON.stringify({ error: 'Decryption failed', message: error.message }));
      }
    });
    
    req.on('error', (error) => {
      console.error('Request error:', error);
      if (!res.headersSent) {
        res.writeHead(500, { 'Content-Type': 'application/json' });
        res.end(JSON.stringify({ error: 'Request error', message: error.message }));
      }
    });
  }

  // ============================================================================
  // End Encrypted Upload Handlers
  // ============================================================================

  async listen(port, callback) {
    const serverPort = port || this.port;
    
    // Initialize encryption if enabled
    if (this.encryption) {
      await this.keyStore.initialize();
      console.log('✓ Keystore initialized');
      
      await this.loadPersistedKeys();
      
      if (!this.activeKeyId) {
        await this.generateKeyPair();
      }
      
      await this.cleanupExpiredKeys();
    }
    
    if (!this.server) {
      this.createServer();
    }
    
    this.server.listen(serverPort, () => {
      console.log(`Server listening on http://localhost:${serverPort}`);
      console.log(`API Key: ${this.apiKey}`);
      
      if (this.encryption) {
        console.log(`Active Key ID: ${this.activeKeyId}`);
        console.log('Endpoints:');
        console.log('  GET  /public-key        - Fetch server public key');
        console.log('  POST /upload-encrypted  - Upload encrypted packets');
        console.log('  POST /upload            - Legacy unencrypted upload');
        console.log('  POST /rotate-keys       - Rotate encryption keys');
      } else {
        console.log('Endpoints:');
        console.log('  POST /upload            - Upload files');
      }
      
      if (callback) callback();
    });
  }

  close() {
    if (this.server) {
      this.server.close();
    }
    
    // Close keystore connection if encryption enabled
    if (this.encryption && this.keyStore) {
      this.keyStore.close();
    }
    
    // Clear sensitive data
    if (this.encryption) {
      this.keyPairs.clear();
      this.sessionCache.clear();
    }
  }
}

// Helper function to create a simple server like in the example
function createSimpleServer(outputFile, port = 3000) {
  const OUTPUT_FILE = outputFile || path.join(process.cwd(), 'uploaded_file.txt');

  const server = http.createServer((req, res) => {
    if (req.method === 'POST' && req.url === '/upload') {
      const writeStream = fs.createWriteStream(OUTPUT_FILE, { flags: 'a' });
      req.pipe(writeStream);
      req.on('end', () => {
        res.writeHead(200);
        res.end('Chunk received\n');
      });
    } else {
      res.writeHead(404);
      res.end();
    }
  });

  server.listen(port, () => {
    console.log(`Server listening on http://localhost:${port}`);
  });

  return server;
}

module.exports = {
  IndexCPServer,
  createSimpleServer
};