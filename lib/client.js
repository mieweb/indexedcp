const fs = require('fs');
const fetch = require('node-fetch');
const readline = require('readline');

// Set up database for different environments
let openDB;
let isFileSystem = false;

if (typeof window === 'undefined') {
  // Node.js environment - default to filesystem-backed storage unless explicitly disabled
  const cliMode = process.env.INDEXCP_CLI_MODE;
  const useFileSystemStorage = cliMode !== 'false';

  if (useFileSystemStorage) {
    const { openFileSystemDB } = require('./filesystem-db');
    openDB = openFileSystemDB;
    isFileSystem = true;
  } else {
    require('fake-indexeddb/auto');
    const { openDB: idbOpenDB } = require('idb');
    openDB = idbOpenDB;
  }
} else {
  // Browser environment
  const { openDB: idbOpenDB } = require('idb');
  openDB = idbOpenDB;
}

class IndexCPClient {
  constructor(options = {}) {
    this.db = null;
    this.dbName = options.dbName || 'indexcp';
    this.storeName = options.storeName || 'chunks';
    this.apiKey = options.apiKey || null;
    this.chunkSize = options.chunkSize || 1024 * 1024; // Default 1MB
    this.serverUrl = options.serverUrl || null;
    
    // Encryption support (optional)
    this.encryption = options.encryption || false;
    
    if (this.encryption) {
      // Load encryption modules only if needed
      const cryptoUtils = require('./crypto-utils');
      const { openEncryptedDB } = require('./encrypted-db');
      
      this.cryptoUtils = cryptoUtils;
      this.encryptedDB = openEncryptedDB;
      this.sessionKeys = new Map(); // sessionId -> AES key (in memory only during capture)
    }
  }

  // ============================================================================
  // Backward Compatibility Properties
  // ============================================================================

  /**
   * Get cached public key info (for compatibility with old EncryptedClient)
   * @returns {Promise<Object|null>} - Cached public key info or null
   */
  get cachedPublicKey() {
    if (!this.encryption) return null;
    return this.getCachedPublicKey();
  }

  /**
   * Get cached key ID (for compatibility with old EncryptedClient)
   * @returns {Promise<string|null>} - Cached key ID or null
   */
  get cachedKeyId() {
    if (!this.encryption) return null;
    return this.getCachedPublicKey().then(key => key ? key.kid : null);
  }

  /**
   * Get active streams (for compatibility with old EncryptedClient)
   * Returns the in-memory sessionKeys Map
   * @returns {Map} - Map of sessionId -> AES session key Buffer
   */
  get activeStreams() {
    if (!this.encryption) return new Map();
    return this.sessionKeys || new Map();
  }

  async promptForApiKey() {
    return new Promise((resolve) => {
      const rl = readline.createInterface({
        input: process.stdin,
        output: process.stdout
      });
      
      rl.question('Enter API key: ', (apiKey) => {
        rl.close();
        resolve(apiKey.trim());
      });
    });
  }

  async getApiKey() {
    if (this.apiKey) {
      return this.apiKey;
    }
    
    // Check environment variable first
    if (process.env.INDEXCP_API_KEY) {
      this.apiKey = process.env.INDEXCP_API_KEY;
      return this.apiKey;
    }
    
    // Prompt user for API key
    this.apiKey = await this.promptForApiKey();
    return this.apiKey;
  }

  async initDB() {
    if (!this.db) {
      if (this.encryption) {
        // Use encrypted database schema
        this.db = await this.encryptedDB(this.dbName, 3);
      } else {
        // Use original simple schema
        this.db = await openDB(this.dbName, 1, {
          upgrade(db) {
            if (!db.objectStoreNames.contains('chunks')) {
              db.createObjectStore('chunks', { keyPath: 'id', autoIncrement: true });
            }
          }
        });
      }
    }
    return this.db;
  }

  // ============================================================================
  // Encryption Methods (only used when encryption: true)
  // ============================================================================

  /**
   * Fetch public key from server (AC0)
   */
  async fetchPublicKey() {
    if (!this.encryption) {
      throw new Error('Encryption not enabled. Set encryption: true in constructor.');
    }
    
    if (!this.serverUrl) {
      throw new Error('serverUrl required for fetchPublicKey()');
    }
    
    const response = await fetch(`${this.serverUrl}/public-key`);
    
    if (!response.ok) {
      throw new Error(`Failed to fetch public key: ${response.statusText}`);
    }
    
    const publicKeyInfo = await response.json();
    
    // Cache the public key in IndexedDB
    const db = await this.initDB();
    const tx = db.transaction('keyCache', 'readwrite');
    await tx.objectStore('keyCache').put({
      kid: publicKeyInfo.kid,
      publicKey: publicKeyInfo.publicKey,
      fetchedAt: Date.now(),
      expiresAt: publicKeyInfo.expiresAt
    });
    await tx.done;
    
    console.log(`✓ Fetched and cached server public key (kid: ${publicKeyInfo.kid})`);
    return publicKeyInfo;
  }

  /**
   * Get cached public key for offline use (AC2)
   */
  async getCachedPublicKey() {
    if (!this.encryption) {
      throw new Error('Encryption not enabled. Set encryption: true in constructor.');
    }
    
    const db = await this.initDB();
    const tx = db.transaction('keyCache', 'readonly');
    const keys = await tx.objectStore('keyCache').getAll();
    await tx.done;
    
    if (keys.length === 0) {
      return null;
    }
    
    // Return most recent non-expired key
    const now = Date.now();
    const validKeys = keys.filter(k => k.expiresAt > now);
    
    if (validKeys.length === 0) {
      return null;
    }
    
    validKeys.sort((a, b) => b.fetchedAt - a.fetchedAt);
    return validKeys[0];
  }

  /**
   * Start encrypted stream for a file
   */
  async startStream(fileName) {
    if (!this.encryption) {
      throw new Error('Encryption not enabled. Set encryption: true in constructor.');
    }
    
    const db = await this.initDB();
    
    // Get public key (cached or fetch)
    let publicKeyInfo = await this.getCachedPublicKey();
    if (!publicKeyInfo && this.serverUrl) {
      publicKeyInfo = await this.fetchPublicKey();
    }
    
    if (!publicKeyInfo) {
      throw new Error('No public key available. Call fetchPublicKey() first or provide serverUrl.');
    }
    
    // Generate session key and ID
    const sessionKey = await this.cryptoUtils.generateSessionKey();
    const sessionId = await this.cryptoUtils.generateSessionId();
    
    // Wrap session key with server's public key
    const wrappedKey = await this.cryptoUtils.wrapSessionKey(
      sessionKey,
      publicKeyInfo.publicKey
    );
    
    // Store session in IndexedDB
    const tx = db.transaction('sessions', 'readwrite');
    await tx.objectStore('sessions').put({
      sessionId,
      kid: publicKeyInfo.kid,
      wrappedKey,
      fileName,
      createdAt: Date.now()
    });
    await tx.done;
    
    // Keep session key in memory for packet encryption
    this.sessionKeys.set(sessionId, sessionKey);
    
    console.log(`✓ Started encrypted stream: ${sessionId} for ${fileName}`);
    return sessionId;
  }

  /**
   * Add encrypted packet to buffer
   */
  async addPacket(sessionId, data, seq) {
    if (!this.encryption) {
      throw new Error('Encryption not enabled. Set encryption: true in constructor.');
    }
    
    const db = await this.initDB();
    
    // Get session key from memory
    const sessionKey = this.sessionKeys.get(sessionId);
    if (!sessionKey) {
      throw new Error(`No session key for ${sessionId}. Call startStream() first.`);
    }
    
    // Encrypt packet
    const encrypted = await this.cryptoUtils.encryptPacket(data, sessionKey, {
      sessionId,
      seq,
      codec: 'raw',
      timestamp: Date.now()
    });
    
    // Store encrypted packet
    const tx = db.transaction('packets', 'readwrite');
    await tx.objectStore('packets').put({
      id: `${sessionId}-${seq}`,
      sessionId,
      seq,
      ciphertext: encrypted.ciphertext,
      iv: encrypted.iv,
      authTag: encrypted.authTag,
      aad: encrypted.aad,
      status: 'pending',
      createdAt: Date.now()
    });
    await tx.done;
  }

  /**
   * Get encryption status
   */
  async getEncryptionStatus() {
    if (!this.encryption) {
      return { encryption: false };
    }
    
    const db = await this.initDB();
    
    const [sessions, packets, keys] = await Promise.all([
      db.getAll('sessions'),
      db.getAll('packets'),
      db.getAll('keyCache')
    ]);
    
    const pendingPackets = packets.filter(p => p.status === 'pending');
    const currentKey = keys.length > 0 ? keys[keys.length - 1].kid : null;
    
    return {
      encryption: true,
      isEncrypted: true,
      activeSessions: sessions.length,
      pendingPackets: pendingPackets.length,
      cachedKeys: keys.length,
      currentKeyId: currentKey
    };
  }

  // ============================================================================
  // End Encryption Methods
  // ============================================================================

  async addFile(filePath) {
    const db = await this.initDB();
    
    // Handle encryption mode
    if (this.encryption) {
      return this.addFileEncrypted(filePath);
    }
    
    // Original unencrypted logic
    return new Promise((resolve, reject) => {
      const readStream = fs.createReadStream(filePath, { highWaterMark: this.chunkSize });
      let chunkIndex = 0;
      const fileName = filePath;
      const chunks = [];

      readStream.on('data', (chunk) => {
        chunks.push({
          id: `${fileName}-${chunkIndex}`, 
          fileName: fileName,
          chunkIndex: chunkIndex,
          data: chunk 
        });
        chunkIndex++;
      });

      readStream.on('end', async () => {
        try {
          // Add all chunks to IndexedDB
          for (const chunk of chunks) {
            await db.add(this.storeName, chunk);
          }
          console.log(`File ${fileName} added to buffer with ${chunkIndex} chunks`);
          resolve(chunkIndex);
        } catch (error) {
          reject(error);
        }
      });

      readStream.on('error', reject);
    });
  }

  /**
   * Add file with encryption enabled
   * @private
   */
  async addFileEncrypted(filePath) {
    const db = await this.initDB();
    const fileName = filePath;
    let sessionId;
    
    try {
      // Start encrypted stream
      sessionId = await this.startStream(fileName);
      
      return new Promise((resolve, reject) => {
        const readStream = fs.createReadStream(filePath, { highWaterMark: this.chunkSize });
        let seq = 0;
        const packetPromises = [];

        readStream.on('data', (chunk) => {
          const currentSeq = seq++;
          const promise = this.addPacket(sessionId, chunk, currentSeq);
          packetPromises.push(promise);
        });

        readStream.on('end', async () => {
          try {
            // Wait for all packets to be encrypted and stored
            await Promise.all(packetPromises);
            
            // Clear session key from memory (AC1 - keys only during capture)
            this.sessionKeys.delete(sessionId);
            
            console.log(`✓ File ${fileName} encrypted and buffered (${seq} packets)`);
            resolve(sessionId);
          } catch (error) {
            // Clean up session key on error
            this.sessionKeys.delete(sessionId);
            reject(error);
          }
        });

        readStream.on('error', (error) => {
          // Clean up session key on error
          this.sessionKeys.delete(sessionId);
          reject(error);
        });
      });
    } catch (error) {
      // Clean up session key if stream start failed
      if (sessionId) {
        this.sessionKeys.delete(sessionId);
      }
      throw error;
    }
  }

  async uploadBufferedFiles(serverUrl) {
    const targetUrl = serverUrl || this.serverUrl;
    if (!targetUrl) {
      throw new Error('serverUrl required for upload');
    }
    
    // Handle encryption mode
    if (this.encryption) {
      return this.uploadEncryptedFiles(targetUrl);
    }
    
    // Original unencrypted logic
    const apiKey = await this.getApiKey();
    
    const db = await this.initDB();
    const transaction = db.transaction(this.storeName, 'readonly');
    const store = transaction.objectStore(this.storeName);
    const allRecords = await store.getAll();
    
    console.log(`Found ${allRecords.length} buffered chunks`);
    
    if (allRecords.length === 0) {
      console.log('No buffered files to upload');
      return {};
    }
    
    // Group records by fileName
    const fileGroups = {};
    allRecords.forEach(record => {
      if (!fileGroups[record.fileName]) {
        fileGroups[record.fileName] = [];
      }
      fileGroups[record.fileName].push(record);
    });

    console.log(`Grouped into ${Object.keys(fileGroups).length} files:`, Object.keys(fileGroups));

    const uploadResults = {}; // Track server-determined filenames

    // Upload each file's chunks in order
    for (const [fileName, chunks] of Object.entries(fileGroups)) {
      console.log(`Uploading ${fileName} with ${chunks.length} chunks...`);
      
      // Sort chunks by index
      chunks.sort((a, b) => a.chunkIndex - b.chunkIndex);
      
      let serverFilename = null;
      
      for (const chunk of chunks) {
        console.log(`Uploading chunk ${chunk.chunkIndex} for ${fileName}`);
        const response = await this.uploadChunk(serverUrl, chunk.data, chunk.chunkIndex, fileName, apiKey);
        
        // Capture server-determined filename from first chunk response
        if (response.data && response.data.actualFilename && !serverFilename) {
          serverFilename = response.data.actualFilename;
        }
        
        await db.delete(this.storeName, chunk.id);
      }
      
      // Store the mapping of client filename to server filename
      uploadResults[fileName] = serverFilename || require('path').basename(fileName);
      
      if (serverFilename && serverFilename !== require('path').basename(fileName)) {
        console.log(`Upload complete for ${fileName} -> Server saved as: ${serverFilename}`);
      } else {
        console.log(`Upload complete for ${fileName}`);
      }
    }
    
    return uploadResults; // Return mapping of client filenames to server filenames
  }

  /**
   * Upload encrypted files (encryption mode)
   * @private
   */
  async uploadEncryptedFiles(serverUrl) {
    const apiKey = await this.getApiKey();
    const db = await this.initDB();
    
    // Get all pending packets grouped by session
    const packets = await db.getAll('packets');
    const pendingPackets = packets.filter(p => p.status === 'pending');
    
    console.log(`Found ${pendingPackets.length} encrypted packets to upload`);
    
    if (pendingPackets.length === 0) {
      console.log('No buffered files to upload');
      return {};
    }
    
    // Group by sessionId
    const sessionGroups = {};
    pendingPackets.forEach(packet => {
      if (!sessionGroups[packet.sessionId]) {
        sessionGroups[packet.sessionId] = [];
      }
      sessionGroups[packet.sessionId].push(packet);
    });
    
    const uploadResults = {};
    
    // Upload each session
    for (const [sessionId, sessionPackets] of Object.entries(sessionGroups)) {
      // Get session metadata
      const session = await db.get('sessions', sessionId);
      if (!session) {
        console.warn(`⚠ Session ${sessionId} not found, skipping`);
        continue;
      }
      
      console.log(`Uploading ${session.fileName} (${sessionPackets.length} encrypted packets)...`);
      
      // Sort packets by sequence number
      sessionPackets.sort((a, b) => a.seq - b.seq);
      
      let serverFilename = null;
      
      // Upload each packet
      for (const packet of sessionPackets) {
        const payload = {
          sessionId: packet.sessionId,
          kid: session.kid,
          wrappedKey: Buffer.from(session.wrappedKey).toString('base64'), // Convert to base64 for JSON transport
          ciphertext: Buffer.from(packet.ciphertext).toString('base64'),
          iv: Buffer.from(packet.iv).toString('base64'),
          authTag: Buffer.from(packet.authTag).toString('base64'),
          aad: Buffer.from(packet.aad).toString('base64'),
          seq: packet.seq,
          fileName: session.fileName
        };
        
        const response = await fetch(`${serverUrl}/upload-encrypted`, {
          method: 'POST',
          headers: {
            'Content-Type': 'application/json',
            'Authorization': `Bearer ${apiKey}`
          },
          body: JSON.stringify(payload)
        });
        
        if (!response.ok) {
          throw new Error(`Upload failed: ${response.statusText}`);
        }
        
        const result = await response.json();
        if (result.actualFilename && !serverFilename) {
          serverFilename = result.actualFilename;
        }
        
        // Mark packet as uploaded
        const tx = db.transaction('packets', 'readwrite');
        packet.status = 'uploaded';
        await tx.objectStore('packets').put(packet);
        await tx.done;
      }
      
      uploadResults[session.fileName] = serverFilename || session.fileName;
      console.log(`✓ Upload complete: ${session.fileName}`);
    }
    
    return uploadResults;
  }

  async uploadChunk(serverUrl, chunk, index, fileName, apiKey) {
    if (!apiKey) {
      apiKey = await this.getApiKey();
    }
    
    const response = await fetch(serverUrl, {
      method: 'POST',
      headers: { 
        'Content-Type': 'application/octet-stream', 
        'X-Chunk-Index': index.toString(),
        'X-File-Name': fileName,
        'Authorization': `Bearer ${apiKey}`
      },
      body: chunk
    });
    
    if (!response.ok) {
      if (response.status === 401) {
        throw new Error('Authentication failed: Invalid API key');
      }
      throw new Error(`Upload failed: ${response.statusText}`);
    }
    
    // Try to parse response as JSON (new format) or fall back to text (backward compatibility)
    let responseData = null;
    const contentType = response.headers.get('content-type');
    
    try {
      if (contentType && contentType.includes('application/json')) {
        responseData = await response.json();
        
        // Log server-determined filename if it differs from client filename
        if (responseData.actualFilename && responseData.actualFilename !== fileName && responseData.actualFilename !== require('path').basename(fileName)) {
          console.log(`Server used filename: ${responseData.actualFilename} (client sent: ${fileName})`);
        }
      } else {
        // Backward compatibility: plain text response
        responseData = { message: await response.text() };
      }
    } catch (parseError) {
      // If JSON parsing fails, fall back to treating as plain text
      responseData = { message: await response.text() };
    }
    
    // Attach response data to the response object for caller access
    response.data = responseData;
    
    return response;
  }

  async bufferAndUpload(filePath, serverUrl) {
    const apiKey = await this.getApiKey();
    const db = await this.initDB();

    return new Promise((resolve, reject) => {
      const readStream = fs.createReadStream(filePath, { highWaterMark: 1024 * 1024 }); // 1MB chunks
      let chunkIndex = 0;

      readStream.on('data', async (chunk) => {
        try {
          await db.add(this.storeName, { id: chunkIndex, data: chunk });
          chunkIndex++;
        } catch (error) {
          reject(error);
        }
      });

      readStream.on('end', async () => {
        try {
          for (let i = 0; i < chunkIndex; i++) {
            const record = await db.get(this.storeName, i);
            if (record) {
              await this.uploadChunk(serverUrl, record.data, i, filePath, apiKey);
              await db.delete(this.storeName, i);
            }
          }
          console.log('Upload complete.');
          resolve();
        } catch (error) {
          reject(error);
        }
      });

      readStream.on('error', reject);
    });
  }
}

module.exports = IndexCPClient;
