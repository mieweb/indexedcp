const fs = require('fs');
const fetch = require('node-fetch');
const readline = require('readline');

// Set up database for different environments
let openDB;
let isFileSystem = false;

if (typeof window === 'undefined') {
  // Node.js environment - check if we should use filesystem or IndexedDB
  if (process.env.INDEXCP_CLI_MODE === 'true') {
    // CLI mode - use filesystem storage
    const { openFileSystemDB } = require('./filesystem-db');
    openDB = openFileSystemDB;
    isFileSystem = true;
  } else {
    // Library mode - use fake-indexeddb
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
    this.dbName = 'indexcp';
    this.storeName = 'chunks';
    this.apiKey = null;

    // Configurable options
    this.uploadInterval = options.uploadInterval || parseInt(process.env.INDEXCP_UPLOAD_INTERVAL) || 10000; // ms
    this.maxRetries = options.maxRetries || parseInt(process.env.INDEXCP_MAX_RETRIES) || 5;
    this.baseRetryDelay = options.baseRetryDelay || parseInt(process.env.INDEXCP_BASE_RETRY_DELAY) || 1000; // ms
    // Local DB chunk storage retry options
    this.chunkStoreRetries = options.chunkStoreRetries || parseInt(process.env.INDEXCP_CHUNK_STORE_RETRIES) || 2;
    this.chunkStoreRetryDelay = options.chunkStoreRetryDelay || parseInt(process.env.INDEXCP_CHUNK_STORE_RETRY_DELAY) || 200; // ms

    // Timer state
    this.uploadTimer = null;
    this.isUploading = false;

    // Relay state
    this._relayActive = false;
    this._relayPromise = null;
    this._relayStopRequested = false;
    this.relayMaxRetries = options.relayMaxRetries || 5;
    this.relayRetryDelay = options.relayRetryDelay || 1000; // ms
  }
  /**
   * Relay chunks in order to an external callback, deleting only after confirmation.
   * Detects and relays a special end-of-stream marker chunk, notifying the external app.
   * After relaying the end marker, the relay loop exits gracefully.
   * @param {Object} options
   *   - fileName: string (optional, relay only this file/stream)
   *   - sessionId: string (optional, relay only this session)
   *   - onChunk: async function(chunk, meta): must resolve true to confirm deletion
   *   - maxRetries: number (optional)
   *   - retryDelay: number (optional, ms)
   */
  async relayChunksInOrder({ fileName, sessionId, onChunk, maxRetries, retryDelay }) {
    if (this._relayActive) throw new Error('Relay already running');
    this._relayActive = true;
    this._relayStopRequested = false;
    maxRetries = maxRetries ?? this.relayMaxRetries;
    retryDelay = retryDelay ?? this.relayRetryDelay;
    const db = await this.initDB();
    let relayCompleted = false;
    while (!this._relayStopRequested && !relayCompleted) {
      // Get all chunks, filter and sort
      let allChunks = await db.getAll(this.storeName);
      if (fileName) allChunks = allChunks.filter(c => c.fileName === fileName);
      if (sessionId) allChunks = allChunks.filter(c => c.sessionId === sessionId);
      if (allChunks.length === 0) {
        await new Promise(res => setTimeout(res, 300));
        continue;
      }
      // Sort: end marker always last (chunkIndex ascending, then isEndMarker)
      allChunks.sort((a, b) => {
        if (a.isEndMarker && !b.isEndMarker) return 1;
        if (!a.isEndMarker && b.isEndMarker) return -1;
        return a.chunkIndex - b.chunkIndex;
      });
      let chunk = allChunks[0];
      if (!chunk) {
        await new Promise(res => setTimeout(res, 300));
        continue;
      }
      let attempt = 0;
      let confirmed = false;
      // If this is the end marker, notify external app and exit after relay
      if (chunk.isEndMarker) {
        while (attempt < maxRetries && !confirmed && !this._relayStopRequested) {
          try {
            console.log(`[relay] Relaying END MARKER for ${chunk.fileName} (session: ${chunk.sessionId}) attempt ${attempt+1}`);
            confirmed = await onChunk(null, {
              id: chunk.id,
              fileName: chunk.fileName,
              chunkIndex: chunk.chunkIndex,
              sessionId: chunk.sessionId,
              isEndMarker: true
            });
            if (confirmed) {
              await this.deleteChunkById(chunk.id);
              console.log(`[relay] Confirmed and deleted END MARKER for ${chunk.fileName} (session: ${chunk.sessionId})`);
              relayCompleted = true;
              break;
            } else {
              throw new Error('External callback did not confirm end marker');
            }
          } catch (err) {
            attempt++;
            console.warn(`[relay] Relay failed for END MARKER (${chunk.fileName}), retry ${attempt}/${maxRetries} in ${retryDelay}ms: ${err.message}`);
            await new Promise(res => setTimeout(res, retryDelay));
          }
        }
        if (!confirmed) {
          console.error(`[relay] Giving up on END MARKER for ${chunk.fileName} after ${maxRetries} attempts.`);
          await new Promise(res => setTimeout(res, 500));
        }
        // After end marker, exit relay loop
        break;
      }
      // Normal chunk relay
      while (attempt < maxRetries && !confirmed && !this._relayStopRequested) {
        try {
          console.log(`[relay] Relaying chunk ${chunk.chunkIndex} (${chunk.fileName}) attempt ${attempt+1}`);
          confirmed = await onChunk(chunk.data, {
            id: chunk.id,
            fileName: chunk.fileName,
            chunkIndex: chunk.chunkIndex,
            sessionId: chunk.sessionId,
            isEndMarker: false
          });
          if (confirmed) {
            await this.deleteChunkById(chunk.id);
            console.log(`[relay] Confirmed and deleted chunk ${chunk.chunkIndex} (${chunk.fileName})`);
          } else {
            throw new Error('External callback did not confirm');
          }
        } catch (err) {
          attempt++;
          console.warn(`[relay] Relay failed for chunk ${chunk.chunkIndex} (${chunk.fileName}), retry ${attempt}/${maxRetries} in ${retryDelay}ms: ${err.message}`);
          await new Promise(res => setTimeout(res, retryDelay));
        }
      }
      if (!confirmed) {
        console.error(`[relay] Giving up on chunk ${chunk.chunkIndex} (${chunk.fileName}) after ${maxRetries} attempts.`);
        await new Promise(res => setTimeout(res, 500));
      }
    }
    this._relayActive = false;
    this._relayStopRequested = false;
    console.log('[relay] Relay loop stopped.');
  }

  /**
   * Stop the relay loop gracefully.
   */
  stopRelay() {
    this._relayStopRequested = true;
  }

  /**
   * Delete a single chunk by its ID.
   */
  async deleteChunkById(id) {
    const db = await this.initDB();
    await db.delete(this.storeName, id);
    console.log(`[delete] Deleted chunk with id ${id}`);
  }
  /**
   * Buffer an arbitrary readable stream (Node.js or browser) into the DB with sessionId.
   * @param {ReadableStream|NodeJS.ReadableStream} stream - The readable stream to buffer.
   * @param {string} streamName - Name/ID for the stream (used as fileName).
   * @param {string} sessionId - Session identifier for grouping chunks.
   * @returns {Promise<number>} - Resolves with the number of chunks buffered.
   */
  /**
   * Buffer an arbitrary readable stream (Node.js or browser) into the DB with sessionId.
   * Adds logging and retry for local DB chunk storage errors.
   * Appends a special end-of-stream marker chunk to signal stream completion.
   * The end marker chunk has { isEndMarker: true } and data: null.
   */
  async addStream(stream, streamName, sessionId) {
    const db = await this.initDB();
    let chunkIndex = 0;
    let isNodeStream = false;
    // Detect Node.js stream
    if (typeof window === 'undefined' && stream && typeof stream.on === 'function') {
      isNodeStream = true;
    }
    // Helper for retrying chunk storage
    const storeChunkWithRetry = async (chunk, id, fileName, chunkIndex, sessionId, isEndMarker = false) => {
      let attempt = 0;
      let lastError = null;
      while (attempt <= this.chunkStoreRetries) {
        try {
          await db.add(this.storeName, {
            id,
            fileName,
            chunkIndex,
            data: chunk,
            sessionId,
            isEndMarker: !!isEndMarker
          });
          return;
        } catch (err) {
          lastError = err;
          console.error(`[addStream] Error storing chunk ${chunkIndex} for ${fileName} (session: ${sessionId}), attempt ${attempt + 1}/${this.chunkStoreRetries + 1}: ${err.message}`);
          if (attempt < this.chunkStoreRetries) {
            await new Promise(res => setTimeout(res, this.chunkStoreRetryDelay));
          }
        }
        attempt++;
      }
      // All retries failed
      throw new Error(`[addStream] Failed to store chunk ${chunkIndex} for ${fileName} (session: ${sessionId}) after ${this.chunkStoreRetries + 1} attempts: ${lastError && lastError.message}`);
    };
    return new Promise((resolve, reject) => {
      // onChunk now uses retry logic
      const onChunk = async (chunk) => {
        const id = `${streamName}-${sessionId}-${chunkIndex}`;
        try {
          // Retry logic for chunk storage
          await storeChunkWithRetry(chunk, id, streamName, chunkIndex, sessionId);
          if (chunkIndex % 10 === 0) {
            console.log(`[addStream] Buffered chunk ${chunkIndex} for ${streamName} (session: ${sessionId})`);
          }
          chunkIndex++;
        } catch (err) {
          // Log and reject if all retries fail
          console.error(`[addStream] Giving up on chunk ${chunkIndex} for ${streamName} (session: ${sessionId}): ${err.message}`);
          reject(err);
        }
      };
      const addEndMarker = async () => {
        // Add a special end marker chunk to the DB
        const endMarkerId = `${streamName}-${sessionId}-endmarker`;
        try {
          await storeChunkWithRetry(null, endMarkerId, streamName, chunkIndex, sessionId, true);
          console.log(`[addStream] End marker chunk added for ${streamName} (session: ${sessionId}) at chunkIndex ${chunkIndex}`);
        } catch (err) {
          console.error(`[addStream] Failed to add end marker for ${streamName} (session: ${sessionId}): ${err.message}`);
          reject(err);
        }
      };
      if (isNodeStream) {
        stream.on('data', onChunk);
        stream.on('end', async () => {
          await addEndMarker();
          console.log(`[addStream] Stream ${streamName} (session: ${sessionId}) ended after ${chunkIndex} chunks.`);
          resolve(chunkIndex);
        });
        stream.on('error', reject);
      } else if (stream && typeof stream.getReader === 'function') {
        // Browser ReadableStream
        const reader = stream.getReader();
        const read = async () => {
          try {
            const { value, done } = await reader.read();
            if (done) {
              await addEndMarker();
              console.log(`[addStream] Stream ${streamName} (session: ${sessionId}) ended after ${chunkIndex} chunks.`);
              resolve(chunkIndex);
              return;
            }
            await onChunk(value);
            read();
          } catch (err) {
            reject(err);
          }
        };
        read();
      } else {
        reject(new Error('Unsupported stream type for addStream'));
      }
    });
  }
  // Timer-based periodic upload
  startUploadTimer(serverUrl) {
    if (this.uploadTimer) return;
    this.uploadTimer = setInterval(() => {
      if (!this.isUploading) {
        this.uploadBufferedFiles(serverUrl).catch(err => {
          console.error('Periodic upload error:', err);
        });
      }
    }, this.uploadInterval);
    console.log('Upload timer started.');
  }

  stopUploadTimer() {
    if (this.uploadTimer) {
      clearInterval(this.uploadTimer);
      this.uploadTimer = null;
      console.log('Upload timer stopped.');
    }
  }

  // View upload queue
  async viewUploadQueue() {
    const db = await this.initDB();
    const transaction = db.transaction(this.storeName, 'readonly');
    const store = transaction.objectStore(this.storeName);
    const allRecords = await store.getAll();
    // Group by fileName
    const fileGroups = {};
    allRecords.forEach(record => {
      if (!fileGroups[record.fileName]) fileGroups[record.fileName] = [];
      fileGroups[record.fileName].push(record.chunkIndex);
    });
    return fileGroups;
  }

  // Clear upload queue
  async clearUploadQueue() {
    const db = await this.initDB();
    const transaction = db.transaction(this.storeName, 'readwrite');
    const store = transaction.objectStore(this.storeName);
    await store.clear();
    console.log('Upload queue cleared.');
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
      this.db = await openDB(this.dbName, 1, {
        upgrade(db) {
          if (!db.objectStoreNames.contains('chunks')) {
            db.createObjectStore('chunks', { keyPath: 'id', autoIncrement: true });
          }
        }
      });
    }
    return this.db;
  }

  /**
   * Buffer a file into the DB with retry and logging for chunk storage errors.
   */
  async addFile(filePath) {
    const db = await this.initDB();
    return new Promise((resolve, reject) => {
      const readStream = fs.createReadStream(filePath, { highWaterMark: 1024 * 1024 }); // 1MB chunks
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
        // Helper for retrying chunk storage
        const storeChunkWithRetry = async (chunk, fileName, chunkIndex) => {
          let attempt = 0;
          let lastError = null;
          while (attempt <= this.chunkStoreRetries) {
            try {
              await db.add(this.storeName, chunk);
              return;
            } catch (err) {
              lastError = err;
              console.error(`[addFile] Error storing chunk ${chunkIndex} for ${fileName}, attempt ${attempt + 1}/${this.chunkStoreRetries + 1}: ${err.message}`);
              if (attempt < this.chunkStoreRetries) {
                await new Promise(res => setTimeout(res, this.chunkStoreRetryDelay));
              }
            }
            attempt++;
          }
          // All retries failed
          throw new Error(`[addFile] Failed to store chunk ${chunkIndex} for ${fileName} after ${this.chunkStoreRetries + 1} attempts: ${lastError && lastError.message}`);
        };
        try {
          // Add all chunks to IndexedDB with retry logic
          for (const chunk of chunks) {
            await storeChunkWithRetry(chunk, fileName, chunk.chunkIndex);
          }
          console.log(`File ${fileName} added to buffer with ${chunkIndex} chunks`);
          resolve(chunkIndex);
        } catch (error) {
          // Log and reject if all retries fail
          console.error(`[addFile] Giving up on file ${fileName}: ${error.message}`);
          reject(error);
        }
      });

      readStream.on('error', reject);
    });
  }

  async uploadBufferedFiles(serverUrl) {
    if (this.isUploading) return;
    this.isUploading = true;
    const apiKey = await this.getApiKey();
    const db = await this.initDB();
    const transaction = db.transaction(this.storeName, 'readonly');
    const store = transaction.objectStore(this.storeName);
    const allRecords = await store.getAll();
    console.log(`Found ${allRecords.length} buffered chunks`);
    if (allRecords.length === 0) {
      console.log('No buffered files or streams to upload');
      this.isUploading = false;
      return;
    }
    // Group records by fileName
    const fileGroups = {};
    allRecords.forEach(record => {
      if (!fileGroups[record.fileName]) fileGroups[record.fileName] = [];
      fileGroups[record.fileName].push(record);
    });
    console.log(`Grouped into ${Object.keys(fileGroups).length} files/streams:`, Object.keys(fileGroups));
    // Upload each file/stream's chunks in order
    for (const [fileName, chunks] of Object.entries(fileGroups)) {
      console.log(`Uploading ${fileName} with ${chunks.length} chunks...`);
      chunks.sort((a, b) => a.chunkIndex - b.chunkIndex);
      for (const chunk of chunks) {
        let attempt = 0;
        let success = false;
        let lastError = null;
        while (attempt < this.maxRetries && !success) {
          try {
            await this.uploadChunk(serverUrl, chunk.data, chunk.chunkIndex, fileName, apiKey);
            await db.delete(this.storeName, chunk.id);
            if (attempt > 0) {
              console.log(`[Retry] Chunk ${chunk.chunkIndex} for ${fileName} uploaded after ${attempt} retries.`);
            }
            success = true;
          } catch (err) {
            lastError = err;
            attempt++;
            if (attempt < this.maxRetries) {
              const delay = this.baseRetryDelay * Math.pow(2, attempt - 1);
              console.warn(`[Retry] Upload failed for chunk ${chunk.chunkIndex} (${fileName}), retry ${attempt}/${this.maxRetries} in ${delay}ms:`, err.message);
              await new Promise(res => setTimeout(res, delay));
            } else {
              console.error(`[Retry] Chunk ${chunk.chunkIndex} for ${fileName} failed after ${this.maxRetries} attempts:`, err.message);
            }
          }
        }
      }
      console.log(`Upload complete for ${fileName}`);
    }
    this.isUploading = false;
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