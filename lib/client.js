const fs = require("fs");
const fetch = require("node-fetch");
const readline = require("readline");
const { createLogger } = require("./logger");

// Set up database for different environments
let openDB;

if (typeof window === "undefined") {
  // Node.js environment
  const isTestMode = process.env.NODE_ENV === "test";

  if (isTestMode) {
    // Testing: Use fake-indexeddb (ephemeral, in-memory)
    require("fake-indexeddb/auto");
    const { openDB: idbOpenDB } = require("idb");
    openDB = idbOpenDB;
  } else {
    // Production: Use IndexedDBShim (persistent, SQLite-backed)
    const path = require("path");
    const os = require("os");

    // Configure IndexedDBShim with persistent storage location
    const dbDir = path.join(os.homedir(), ".indexcp", "idb");
    if (!fs.existsSync(dbDir)) {
      fs.mkdirSync(dbDir, { recursive: true });
    }

    // Initialize IndexedDBShim - it sets up global indexedDB
    const setGlobalVars = require("indexeddbshim");
    setGlobalVars(global, {
      checkOrigin: false, // Allow opaque origins in Node.js
      databaseBasePath: dbDir,
      deleteDatabaseFiles: false,
    });

    const { openDB: idbOpenDB } = require("idb");
    openDB = idbOpenDB;
  }
} else {
  // Browser environment
  const { openDB: idbOpenDB } = require("idb");
  openDB = idbOpenDB;
}

class IndexedCPClient {
  constructor(options = {}) {
    this.db = null;
    this.dbName = options.dbName || "indexcp";
    this.storeName = options.storeName || "chunks";
    this.apiKey = options.apiKey || null;
    this.chunkSize = options.chunkSize || 1024 * 1024; // Default 1MB
    this.serverUrl = options.serverUrl || null;

    // Logger configuration
    this.logger = createLogger({
      level: options.logLevel,
      prefix: "[IndexedCPClient]",
    });

    // Background upload retry settings
    this.maxRetries = options.maxRetries || Infinity; // Default: retry forever
    this.initialRetryDelay = options.initialRetryDelay || 1000; // 1 second
    this.maxRetryDelay = options.maxRetryDelay || 60000; // 60 seconds max
    this.retryMultiplier = options.retryMultiplier || 2; // Exponential backoff

    // Background upload state
    this.backgroundUploadTimer = null;
    this.backgroundUploadRunning = false;
    this.onUploadProgress = options.onUploadProgress || null; // Callback for progress
    this.onUploadError = options.onUploadError || null; // Callback for errors
    this.onUploadComplete = options.onUploadComplete || null; // Callback for completion

    // Encryption support (optional)
    this.encryption = options.encryption || false;

    if (this.encryption) {
      // Load encryption modules only if needed
      const cryptoUtils = require("./crypto-utils");
      const { openEncryptedDB } = require("./encrypted-db");

      this.cryptoUtils = cryptoUtils;
      this.encryptedDB = openEncryptedDB;
      this.sessionKeys = new Map(); // sessionId -> AES key (in memory only during capture)
      this.sessionSeqCounters = new Map(); // sessionId -> next sequence number (auto-increment)
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
    return this.getCachedPublicKey().then((key) => (key ? key.kid : null));
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
        output: process.stdout,
      });

      rl.question("Enter API key: ", (apiKey) => {
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
    if (process.env.INDEXEDCP_API_KEY) {
      this.apiKey = process.env.INDEXEDCP_API_KEY;
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
            if (!db.objectStoreNames.contains("chunks")) {
              db.createObjectStore("chunks", {
                keyPath: "id",
                autoIncrement: true,
              });
            }
          },
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
      throw new Error(
        "Encryption not enabled. Set encryption: true in constructor."
      );
    }

    if (!this.serverUrl) {
      throw new Error("serverUrl required for fetchPublicKey()");
    }

    const response = await fetch(`${this.serverUrl}/public-key`);

    if (!response.ok) {
      throw new Error(`Failed to fetch public key: ${response.statusText}`);
    }

    const publicKeyInfo = await response.json();

    // Cache the public key in IndexedDB
    const db = await this.initDB();
    const tx = db.transaction("keyCache", "readwrite");
    await tx.objectStore("keyCache").put({
      kid: publicKeyInfo.kid,
      publicKey: publicKeyInfo.publicKey,
      fetchedAt: Date.now(),
      expiresAt: publicKeyInfo.expiresAt,
    });
    await tx.done;

    this.logger.info(
      `✓ Fetched and cached server public key (kid: ${publicKeyInfo.kid})`
    );
    return publicKeyInfo;
  }

  /**
   * Get cached public key for offline use (AC2)
   */
  async getCachedPublicKey() {
    if (!this.encryption) {
      throw new Error(
        "Encryption not enabled. Set encryption: true in constructor."
      );
    }

    const db = await this.initDB();
    const tx = db.transaction("keyCache", "readonly");
    const keys = await tx.objectStore("keyCache").getAll();
    await tx.done;

    if (keys.length === 0) {
      return null;
    }

    // Return most recent non-expired key
    const now = Date.now();
    const validKeys = keys.filter((k) => k.expiresAt > now);

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
      throw new Error(
        "Encryption not enabled. Set encryption: true in constructor."
      );
    }

    const db = await this.initDB();

    // Get public key (cached or fetch)
    let publicKeyInfo = await this.getCachedPublicKey();
    if (!publicKeyInfo && this.serverUrl) {
      publicKeyInfo = await this.fetchPublicKey();
    }

    if (!publicKeyInfo) {
      throw new Error(
        "No public key available. Call fetchPublicKey() first or provide serverUrl."
      );
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
    const tx = db.transaction("sessions", "readwrite");
    await tx.objectStore("sessions").put({
      sessionId,
      kid: publicKeyInfo.kid,
      wrappedKey,
      fileName,
      createdAt: Date.now(),
    });
    await tx.done;

    // Keep session key in memory for packet encryption
    this.sessionKeys.set(sessionId, sessionKey);

    // Initialize sequence counter for this session
    this.sessionSeqCounters.set(sessionId, 0);

    this.logger.info(
      `✓ Started encrypted stream: ${sessionId} for ${fileName}`
    );
    return sessionId;
  }

  /**
   * Add encrypted packet to buffer
   * @param {string} sessionId - Session identifier
   * @param {Buffer|ArrayBuffer|Uint8Array} data - Packet data
   * @param {number} [seq] - Packet sequence number (auto-increments if not provided)
   */
  async addPacket(sessionId, data, seq = null) {
    if (!this.encryption) {
      throw new Error(
        "Encryption not enabled. Set encryption: true in constructor."
      );
    }

    const db = await this.initDB();

    // Get session key from memory
    const sessionKey = this.sessionKeys.get(sessionId);
    if (!sessionKey) {
      throw new Error(
        `No session key for ${sessionId}. Call startStream() first.`
      );
    }

    // Auto-increment sequence number if not provided
    if (seq === null) {
      seq = this.sessionSeqCounters.get(sessionId);
      if (seq === undefined) {
        throw new Error(
          `No sequence counter for ${sessionId}. Call startStream() first.`
        );
      }
      this.sessionSeqCounters.set(sessionId, seq + 1);
    }

    // Encrypt packet
    const encrypted = await this.cryptoUtils.encryptPacket(data, sessionKey, {
      sessionId,
      seq,
      codec: "raw",
      timestamp: Date.now(),
    });

    // Store encrypted packet
    const tx = db.transaction("packets", "readwrite");
    await tx.objectStore("packets").put({
      id: `${sessionId}-${seq}`,
      sessionId,
      seq,
      ciphertext: encrypted.ciphertext,
      iv: encrypted.iv,
      authTag: encrypted.authTag,
      aad: encrypted.aad,
      status: "pending",
      createdAt: Date.now(),
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
      db.getAll("sessions"),
      db.getAll("packets"),
      db.getAll("keyCache"),
    ]);

    const pendingPackets = packets.filter((p) => p.status === "pending");
    const currentKey = keys.length > 0 ? keys[keys.length - 1].kid : null;

    return {
      encryption: true,
      isEncrypted: true,
      activeSessions: sessions.length,
      pendingPackets: pendingPackets.length,
      cachedKeys: keys.length,
      currentKeyId: currentKey,
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
      const readStream = fs.createReadStream(filePath, {
        highWaterMark: this.chunkSize,
      });
      let chunkIndex = 0;
      const fileName = filePath;
      const chunks = [];

      readStream.on("data", (chunk) => {
        chunks.push({
          id: `${fileName}-${chunkIndex}`,
          fileName: fileName,
          chunkIndex: chunkIndex,
          data: chunk,
        });
        chunkIndex++;
      });

      readStream.on("end", async () => {
        try {
          // Add all chunks to IndexedDB
          for (const chunk of chunks) {
            await db.add(this.storeName, chunk);
          }
          this.logger.info(
            `File ${fileName} added to buffer with ${chunkIndex} chunks`
          );
          resolve(chunkIndex);
        } catch (error) {
          reject(error);
        }
      });

      readStream.on("error", reject);
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
        const readStream = fs.createReadStream(filePath, {
          highWaterMark: this.chunkSize,
        });
        let seq = 0;
        const packetPromises = [];

        readStream.on("data", (chunk) => {
          const currentSeq = seq++;
          const promise = this.addPacket(sessionId, chunk, currentSeq);
          packetPromises.push(promise);
        });

        readStream.on("end", async () => {
          try {
            // Wait for all packets to be encrypted and stored
            await Promise.all(packetPromises);

            // Clear session key from memory (AC1 - keys only during capture)
            this.sessionKeys.delete(sessionId);

            this.logger.info(
              `✓ File ${fileName} encrypted and buffered (${seq} packets)`
            );
            resolve(sessionId);
          } catch (error) {
            // Clean up session key on error
            this.sessionKeys.delete(sessionId);
            reject(error);
          }
        });

        readStream.on("error", (error) => {
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
      throw new Error("serverUrl required for upload");
    }

    // Handle encryption mode
    if (this.encryption) {
      return this.uploadEncryptedFiles(targetUrl);
    }

    // Original unencrypted logic
    const apiKey = await this.getApiKey();

    const db = await this.initDB();
    const transaction = db.transaction(this.storeName, "readonly");
    const store = transaction.objectStore(this.storeName);
    const allRecords = await store.getAll();

    this.logger.info(`Found ${allRecords.length} buffered chunks`);

    if (allRecords.length === 0) {
      this.logger.info("No buffered files to upload");
      return {};
    }

    // Group records by fileName
    const fileGroups = {};
    allRecords.forEach((record) => {
      if (!fileGroups[record.fileName]) {
        fileGroups[record.fileName] = [];
      }
      fileGroups[record.fileName].push(record);
    });

    this.logger.info(
      `Grouped into ${Object.keys(fileGroups).length} files:`,
      Object.keys(fileGroups)
    );

    // Upload all files in parallel (non-blocking)
    const uploadPromises = Object.entries(fileGroups).map(
      ([fileName, chunks]) =>
        this.uploadFileChunks(serverUrl, fileName, chunks, db, apiKey)
    );

    const results = await Promise.all(uploadPromises);

    // Combine results
    const uploadResults = {};
    results.forEach((result) => {
      uploadResults[result.fileName] = result.serverFilename;
    });

    return uploadResults; // Return mapping of client filenames to server filenames
  }

  /**
   * Upload a single file's chunks in order
   * @private
   */
  async uploadFileChunks(serverUrl, fileName, chunks, db, apiKey) {
    this.logger.info(`Uploading ${fileName} with ${chunks.length} chunks...`);

    // Sort chunks by index
    chunks.sort((a, b) => a.chunkIndex - b.chunkIndex);

    let serverFilename = null;

    // Upload chunks sequentially to preserve order
    for (const chunk of chunks) {
      this.logger.info(`Uploading chunk ${chunk.chunkIndex} for ${fileName}`);
      const response = await this.uploadChunk(
        serverUrl,
        chunk.data,
        chunk.chunkIndex,
        fileName,
        apiKey
      );

      // Capture server-determined filename from first chunk response
      if (response.data && response.data.actualFilename && !serverFilename) {
        serverFilename = response.data.actualFilename;
      }

      await db.delete(this.storeName, chunk.id);
    }

    // Store the mapping of client filename to server filename
    serverFilename = serverFilename || require("path").basename(fileName);

    if (serverFilename !== require("path").basename(fileName)) {
      this.logger.info(
        `Upload complete for ${fileName} -> Server saved as: ${serverFilename}`
      );
    } else {
      this.logger.info(`Upload complete for ${fileName}`);
    }

    return { fileName, serverFilename };
  }

  /**
   * Upload encrypted files (encryption mode)
   * @private
   */
  async uploadEncryptedFiles(serverUrl) {
    const apiKey = await this.getApiKey();
    const db = await this.initDB();

    // Get all pending packets grouped by session
    const packets = await db.getAll("packets");
    const pendingPackets = packets.filter((p) => p.status === "pending");

    this.logger.info(
      `Found ${pendingPackets.length} encrypted packets to upload`
    );

    if (pendingPackets.length === 0) {
      this.logger.info("No buffered files to upload");
      return {};
    }

    // Group by sessionId
    const sessionGroups = {};
    pendingPackets.forEach((packet) => {
      if (!sessionGroups[packet.sessionId]) {
        sessionGroups[packet.sessionId] = [];
      }
      sessionGroups[packet.sessionId].push(packet);
    });

    // Upload all sessions in parallel (non-blocking)
    const uploadPromises = Object.entries(sessionGroups).map(
      ([sessionId, sessionPackets]) =>
        this.uploadSession(serverUrl, sessionId, sessionPackets, db, apiKey)
    );

    const results = await Promise.all(uploadPromises);

    // Combine results
    const uploadResults = {};
    results.forEach((result) => {
      if (result) {
        uploadResults[result.fileName] = result.serverFilename;
      }
    });

    return uploadResults;
  }

  /**
   * Upload a single session's packets (preserving order, batching sequential packets)
   * @private
   */
  async uploadSession(serverUrl, sessionId, sessionPackets, db, apiKey) {
    // Get session metadata
    const session = await db.get("sessions", sessionId);
    if (!session) {
      this.logger.warn(`⚠ Session ${sessionId} not found, skipping`);
      return null;
    }

    this.logger.info(
      `Uploading ${session.fileName} (${sessionPackets.length} encrypted packets)...`
    );

    // Sort packets by sequence number
    sessionPackets.sort((a, b) => a.seq - b.seq);

    // Batch sequential packets together
    const batches = this.batchSequentialPackets(sessionPackets);

    let serverFilename = null;

    // Upload batches sequentially (to preserve order within file)
    for (const batch of batches) {
      const result = await this.uploadPacketBatch(
        serverUrl,
        session,
        batch,
        apiKey
      );

      if (result.actualFilename && !serverFilename) {
        serverFilename = result.actualFilename;
      }

      // Mark packets as uploaded
      const tx = db.transaction("packets", "readwrite");
      for (const packet of batch) {
        packet.status = "uploaded";
        await tx.objectStore("packets").put(packet);
      }
      await tx.done;
    }

    this.logger.info(`✓ Upload complete: ${session.fileName}`);

    // Clean up session state
    this.sessionKeys.delete(sessionId);
    this.sessionSeqCounters.delete(sessionId);

    return {
      fileName: session.fileName,
      serverFilename: serverFilename || session.fileName,
    };
  }

  /**
   * Batch sequential packets together for combined upload
   * @private
   */
  batchSequentialPackets(packets) {
    if (packets.length === 0) return [];

    const batches = [];
    let currentBatch = [packets[0]];

    for (let i = 1; i < packets.length; i++) {
      const prevPacket = packets[i - 1];
      const currentPacket = packets[i];

      // Check if sequential
      if (currentPacket.seq === prevPacket.seq + 1) {
        currentBatch.push(currentPacket);
      } else {
        // Start new batch
        batches.push(currentBatch);
        currentBatch = [currentPacket];
      }
    }

    // Add final batch
    batches.push(currentBatch);

    return batches;
  }

  /**
   * Upload a batch of packets (single or multiple sequential packets)
   * @private
   */
  async uploadPacketBatch(serverUrl, session, packets, apiKey) {
    if (packets.length === 1) {
      // Single packet upload
      const packet = packets[0];
      const payload = {
        sessionId: packet.sessionId,
        kid: session.kid,
        wrappedKey: Buffer.from(session.wrappedKey).toString("base64"),
        ciphertext: Buffer.from(packet.ciphertext).toString("base64"),
        iv: Buffer.from(packet.iv).toString("base64"),
        authTag: Buffer.from(packet.authTag).toString("base64"),
        aad: Buffer.from(packet.aad).toString("base64"),
        seq: packet.seq,
        fileName: session.fileName,
      };

      const response = await fetch(`${serverUrl}/upload-encrypted`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          Authorization: `Bearer ${apiKey}`,
        },
        body: JSON.stringify(payload),
      });

      if (!response.ok) {
        throw new Error(`Upload failed: ${response.statusText}`);
      }

      return await response.json();
    } else {
      // Batched packet upload
      const payload = {
        sessionId: packets[0].sessionId,
        kid: session.kid,
        wrappedKey: Buffer.from(session.wrappedKey).toString("base64"),
        fileName: session.fileName,
        packets: packets.map((packet) => ({
          ciphertext: Buffer.from(packet.ciphertext).toString("base64"),
          iv: Buffer.from(packet.iv).toString("base64"),
          authTag: Buffer.from(packet.authTag).toString("base64"),
          aad: Buffer.from(packet.aad).toString("base64"),
          seq: packet.seq,
        })),
      };

      const response = await fetch(`${serverUrl}/upload-encrypted-batch`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          Authorization: `Bearer ${apiKey}`,
        },
        body: JSON.stringify(payload),
      });

      if (!response.ok) {
        throw new Error(`Batch upload failed: ${response.statusText}`);
      }

      return await response.json();
    }
  }

  async uploadChunk(serverUrl, chunk, index, fileName, apiKey) {
    if (!apiKey) {
      apiKey = await this.getApiKey();
    }

    const response = await fetch(serverUrl, {
      method: "POST",
      headers: {
        "Content-Type": "application/octet-stream",
        "X-Chunk-Index": index.toString(),
        "X-File-Name": fileName,
        Authorization: `Bearer ${apiKey}`,
      },
      body: chunk,
    });

    if (!response.ok) {
      if (response.status === 401) {
        throw new Error("Authentication failed: Invalid API key");
      }
      throw new Error(`Upload failed: ${response.statusText}`);
    }

    // Try to parse response as JSON (new format) or fall back to text (backward compatibility)
    let responseData = null;
    const contentType = response.headers.get("content-type");

    try {
      if (contentType && contentType.includes("application/json")) {
        responseData = await response.json();

        // Log server-determined filename if it differs from client filename
        if (
          responseData.actualFilename &&
          responseData.actualFilename !== fileName &&
          responseData.actualFilename !== require("path").basename(fileName)
        ) {
          this.logger.info(
            `Server used filename: ${responseData.actualFilename} (client sent: ${fileName})`
          );
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
      const readStream = fs.createReadStream(filePath, {
        highWaterMark: 1024 * 1024,
      }); // 1MB chunks
      let chunkIndex = 0;

      readStream.on("data", async (chunk) => {
        try {
          await db.add(this.storeName, { id: chunkIndex, data: chunk });
          chunkIndex++;
        } catch (error) {
          reject(error);
        }
      });

      readStream.on("end", async () => {
        try {
          for (let i = 0; i < chunkIndex; i++) {
            const record = await db.get(this.storeName, i);
            if (record) {
              await this.uploadChunk(
                serverUrl,
                record.data,
                i,
                filePath,
                apiKey
              );
              await db.delete(this.storeName, i);
            }
          }
          this.logger.info("Upload complete.");
          resolve();
        } catch (error) {
          reject(error);
        }
      });

      readStream.on("error", reject);
    });
  }

  // ============================================================================
  // Background Upload with Automatic Retry
  // ============================================================================

  /**
   * Start background upload process with automatic retry
   * Continuously monitors pending uploads and retries failures with exponential backoff
   * @param {string} serverUrl - Server URL for uploads
   * @param {object} options - Optional configuration
   * @param {number} options.checkInterval - How often to check for pending uploads (ms). Default: 5000
   * @returns {void}
   */
  startUploadBackground(serverUrl, options = {}) {
    const checkInterval = options.checkInterval || 5000; // Check every 5 seconds

    if (this.backgroundUploadTimer) {
      this.logger.info("Background upload already running");
      return;
    }

    this.logger.info(
      `🚀 Starting background upload (checking every ${checkInterval}ms)`
    );

    // Immediate first check
    this._processBackgroundUpload(serverUrl).catch((err) => {
      this.logger.error("Background upload error:", err);
      if (this.onUploadError) {
        this.onUploadError(err);
      }
    });

    // Set up recurring timer
    this.backgroundUploadTimer = setInterval(() => {
      if (!this.backgroundUploadRunning) {
        this._processBackgroundUpload(serverUrl).catch((err) => {
          this.logger.error("Background upload error:", err);
          if (this.onUploadError) {
            this.onUploadError(err);
          }
        });
      }
    }, checkInterval);
  }

  /**
   * Stop background upload process
   */
  stopUploadBackground() {
    if (this.backgroundUploadTimer) {
      clearInterval(this.backgroundUploadTimer);
      this.backgroundUploadTimer = null;
      this.logger.info("⏹ Stopped background upload");
    }
  }

  /**
   * Process pending uploads with retry logic (internal)
   * @private
   */
  async _processBackgroundUpload(serverUrl) {
    if (this.backgroundUploadRunning) {
      return; // Prevent concurrent runs
    }

    this.backgroundUploadRunning = true;

    try {
      const targetUrl = serverUrl || this.serverUrl;
      if (!targetUrl) {
        throw new Error("serverUrl required for background upload");
      }

      const db = await this.initDB();
      const now = Date.now();

      if (this.encryption) {
        // Encrypted mode
        await this._processEncryptedBackgroundUpload(targetUrl, db, now);
      } else {
        // Unencrypted mode
        await this._processUnencryptedBackgroundUpload(targetUrl, db, now);
      }
    } finally {
      this.backgroundUploadRunning = false;
    }
  }

  /**
   * Process unencrypted background uploads
   * @private
   */
  async _processUnencryptedBackgroundUpload(serverUrl, db, now) {
    const apiKey = await this.getApiKey();
    const allRecords = await db.getAll(this.storeName);

    if (allRecords.length === 0) {
      return; // Nothing to upload
    }

    // Group by fileName
    const fileGroups = {};
    allRecords.forEach((record) => {
      // Initialize retry metadata if not present
      if (!record.retryMetadata) {
        record.retryMetadata = {
          retryCount: 0,
          lastAttempt: null,
          nextRetry: now,
          errors: [],
        };
      }

      // Check if ready for retry
      if (record.retryMetadata.nextRetry > now) {
        return; // Not ready yet
      }

      // Check max retries
      if (record.retryMetadata.retryCount >= this.maxRetries) {
        this.logger.warn(
          `⚠ Max retries (${this.maxRetries}) reached for chunk ${record.id}`
        );
        return;
      }

      if (!fileGroups[record.fileName]) {
        fileGroups[record.fileName] = [];
      }
      fileGroups[record.fileName].push(record);
    });

    const fileCount = Object.keys(fileGroups).length;
    if (fileCount === 0) {
      return; // No files ready for retry
    }

    this.logger.info(
      `📤 Background upload: ${fileCount} file(s) with pending chunks`
    );

    // Upload files in parallel
    const uploadPromises = Object.entries(fileGroups).map(
      ([fileName, chunks]) =>
        this._uploadFileChunksWithRetry(
          serverUrl,
          fileName,
          chunks,
          db,
          apiKey,
          now
        )
    );

    const results = await Promise.allSettled(uploadPromises);

    // Report results
    const succeeded = results.filter((r) => r.status === "fulfilled").length;
    const failed = results.filter((r) => r.status === "rejected").length;

    if (succeeded > 0 && this.onUploadComplete) {
      this.onUploadComplete({ succeeded, failed, total: results.length });
    }
  }

  /**
   * Upload file chunks with retry metadata tracking
   * @private
   */
  async _uploadFileChunksWithRetry(
    serverUrl,
    fileName,
    chunks,
    db,
    apiKey,
    now
  ) {
    // Sort chunks by index
    chunks.sort((a, b) => a.chunkIndex - b.chunkIndex);

    const errors = [];
    let successCount = 0;

    for (const chunk of chunks) {
      try {
        // Update retry metadata
        chunk.retryMetadata.lastAttempt = now;
        chunk.retryMetadata.retryCount++;

        // Attempt upload
        const response = await this.uploadChunk(
          serverUrl,
          chunk.data,
          chunk.chunkIndex,
          fileName,
          apiKey
        );

        // Success - delete from DB
        await db.delete(this.storeName, chunk.id);
        successCount++;

        if (this.onUploadProgress) {
          this.onUploadProgress({
            fileName,
            chunkIndex: chunk.chunkIndex,
            status: "success",
            retryCount: chunk.retryMetadata.retryCount - 1,
          });
        }
      } catch (error) {
        // Failure - update retry metadata with exponential backoff
        const delay = Math.min(
          this.initialRetryDelay *
            Math.pow(this.retryMultiplier, chunk.retryMetadata.retryCount - 1),
          this.maxRetryDelay
        );

        chunk.retryMetadata.nextRetry = now + delay;
        chunk.retryMetadata.errors.push({
          timestamp: now,
          message: error.message,
        });

        // Keep only last 5 errors
        if (chunk.retryMetadata.errors.length > 5) {
          chunk.retryMetadata.errors.shift();
        }

        // Update chunk in DB with new retry metadata
        await db.put(this.storeName, chunk);

        errors.push(error);

        this.logger.warn(
          `⚠ Upload failed for ${fileName} chunk ${chunk.chunkIndex} (retry ${
            chunk.retryMetadata.retryCount
          }/${
            this.maxRetries === Infinity ? "∞" : this.maxRetries
          }). Next retry in ${Math.round(delay / 1000)}s`
        );

        if (this.onUploadProgress) {
          this.onUploadProgress({
            fileName,
            chunkIndex: chunk.chunkIndex,
            status: "failed",
            retryCount: chunk.retryMetadata.retryCount,
            nextRetryIn: delay,
            error: error.message,
          });
        }
      }
    }

    if (errors.length > 0) {
      throw new Error(`${errors.length} chunk(s) failed for ${fileName}`);
    }

    this.logger.info(
      `✓ Successfully uploaded ${fileName} (${successCount} chunks)`
    );
  }

  /**
   * Process encrypted background uploads
   * @private
   */
  async _processEncryptedBackgroundUpload(serverUrl, db, now) {
    const apiKey = await this.getApiKey();
    const packets = await db.getAll("packets");

    // Filter for pending packets ready for retry
    const retryablePackets = packets.filter((packet) => {
      if (packet.status !== "pending" && packet.status !== "failed") {
        return false;
      }

      // Initialize retry metadata if not present
      if (!packet.retryMetadata) {
        packet.retryMetadata = {
          retryCount: 0,
          lastAttempt: null,
          nextRetry: now,
          errors: [],
        };
      }

      // Check if ready for retry
      if (packet.retryMetadata.nextRetry > now) {
        return false;
      }

      // Check max retries
      if (packet.retryMetadata.retryCount >= this.maxRetries) {
        this.logger.warn(
          `⚠ Max retries (${this.maxRetries}) reached for packet ${packet.id}`
        );
        return false;
      }

      return true;
    });

    if (retryablePackets.length === 0) {
      return; // No packets ready for retry
    }

    // Group by sessionId
    const sessionGroups = {};
    retryablePackets.forEach((packet) => {
      if (!sessionGroups[packet.sessionId]) {
        sessionGroups[packet.sessionId] = [];
      }
      sessionGroups[packet.sessionId].push(packet);
    });

    this.logger.info(
      `📤 Background upload: ${
        Object.keys(sessionGroups).length
      } session(s) with ${retryablePackets.length} pending packets`
    );

    // Upload sessions in parallel
    const uploadPromises = Object.entries(sessionGroups).map(
      ([sessionId, sessionPackets]) =>
        this._uploadSessionWithRetry(
          serverUrl,
          sessionId,
          sessionPackets,
          db,
          apiKey,
          now
        )
    );

    const results = await Promise.allSettled(uploadPromises);

    // Report results
    const succeeded = results.filter((r) => r.status === "fulfilled").length;
    const failed = results.filter((r) => r.status === "rejected").length;

    if (succeeded > 0 && this.onUploadComplete) {
      this.onUploadComplete({ succeeded, failed, total: results.length });
    }
  }

  /**
   * Upload session with retry metadata tracking
   * @private
   */
  async _uploadSessionWithRetry(
    serverUrl,
    sessionId,
    sessionPackets,
    db,
    apiKey,
    now
  ) {
    // Get session metadata
    const session = await db.get("sessions", sessionId);
    if (!session) {
      this.logger.warn(`⚠ Session ${sessionId} not found, skipping`);
      return null;
    }

    // Sort packets by sequence number
    sessionPackets.sort((a, b) => a.seq - b.seq);

    const errors = [];
    let successCount = 0;

    for (const packet of sessionPackets) {
      try {
        // Update retry metadata
        packet.retryMetadata.lastAttempt = now;
        packet.retryMetadata.retryCount++;

        // Attempt upload
        const payload = {
          sessionId: packet.sessionId,
          kid: session.kid,
          wrappedKey: Buffer.from(session.wrappedKey).toString("base64"),
          ciphertext: Buffer.from(packet.ciphertext).toString("base64"),
          iv: Buffer.from(packet.iv).toString("base64"),
          authTag: Buffer.from(packet.authTag).toString("base64"),
          aad: Buffer.from(packet.aad).toString("base64"),
          seq: packet.seq,
          fileName: session.fileName,
        };

        const response = await fetch(`${serverUrl}/upload-encrypted`, {
          method: "POST",
          headers: {
            "Content-Type": "application/json",
            Authorization: `Bearer ${apiKey}`,
          },
          body: JSON.stringify(payload),
        });

        if (!response.ok) {
          throw new Error(`Upload failed: ${response.statusText}`);
        }

        // Success - mark as uploaded
        packet.status = "uploaded";
        delete packet.retryMetadata; // Clean up metadata
        await db.put("packets", packet);
        successCount++;

        if (this.onUploadProgress) {
          this.onUploadProgress({
            sessionId,
            fileName: session.fileName,
            seq: packet.seq,
            status: "success",
            retryCount: packet.retryMetadata.retryCount - 1,
          });
        }
      } catch (error) {
        // Failure - update retry metadata with exponential backoff
        const delay = Math.min(
          this.initialRetryDelay *
            Math.pow(this.retryMultiplier, packet.retryMetadata.retryCount - 1),
          this.maxRetryDelay
        );

        packet.retryMetadata.nextRetry = now + delay;
        packet.retryMetadata.errors.push({
          timestamp: now,
          message: error.message,
        });

        // Keep only last 5 errors
        if (packet.retryMetadata.errors.length > 5) {
          packet.retryMetadata.errors.shift();
        }

        packet.status = "failed";

        // Update packet in DB with new retry metadata
        await db.put("packets", packet);

        errors.push(error);

        this.logger.warn(
          `⚠ Upload failed for ${session.fileName} packet ${
            packet.seq
          } (retry ${packet.retryMetadata.retryCount}/${
            this.maxRetries === Infinity ? "∞" : this.maxRetries
          }). Next retry in ${Math.round(delay / 1000)}s`
        );

        if (this.onUploadProgress) {
          this.onUploadProgress({
            sessionId,
            fileName: session.fileName,
            seq: packet.seq,
            status: "failed",
            retryCount: packet.retryMetadata.retryCount,
            nextRetryIn: delay,
            error: error.message,
          });
        }
      }
    }

    // Clean up session state if all packets uploaded
    if (errors.length === 0) {
      this.sessionKeys.delete(sessionId);
      this.sessionSeqCounters.delete(sessionId);
      this.logger.info(
        `✓ Successfully uploaded ${session.fileName} (${successCount} packets)`
      );
    } else {
      throw new Error(
        `${errors.length} packet(s) failed for ${session.fileName}`
      );
    }
  }

  // ============================================================================
  // End Background Upload Methods
  // ============================================================================
}

module.exports = IndexedCPClient;
