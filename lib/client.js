const fs = require('fs');
const fetch = require('node-fetch');

// Set up IndexedDB for Node.js environment
let openDB;
if (typeof window === 'undefined') {
  // Node.js environment - use fake-indexeddb
  require('fake-indexeddb/auto');
  const { openDB: idbOpenDB } = require('idb');
  openDB = idbOpenDB;
} else {
  // Browser environment
  const { openDB: idbOpenDB } = require('idb');
  openDB = idbOpenDB;
}

class IndexCPClient {
  constructor() {
    this.db = null;
    this.dbName = 'indexcp';
    this.storeName = 'chunks';
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

  async uploadBufferedFiles(serverUrl) {
    const db = await this.initDB();
    const transaction = db.transaction(this.storeName, 'readonly');
    const store = transaction.objectStore(this.storeName);
    const allRecords = await store.getAll();
    
    console.log(`Found ${allRecords.length} buffered chunks`);
    
    if (allRecords.length === 0) {
      console.log('No buffered files to upload');
      return;
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

    // Upload each file's chunks in order
    for (const [fileName, chunks] of Object.entries(fileGroups)) {
      console.log(`Uploading ${fileName} with ${chunks.length} chunks...`);
      
      // Sort chunks by index
      chunks.sort((a, b) => a.chunkIndex - b.chunkIndex);
      
      for (const chunk of chunks) {
        console.log(`Uploading chunk ${chunk.chunkIndex} for ${fileName}`);
        await this.uploadChunk(serverUrl, chunk.data, chunk.chunkIndex, fileName);
        await db.delete(this.storeName, chunk.id);
      }
      
      console.log(`Upload complete for ${fileName}`);
    }
  }

  async uploadChunk(serverUrl, chunk, index, fileName) {
    const response = await fetch(serverUrl, {
      method: 'POST',
      headers: { 
        'Content-Type': 'application/octet-stream', 
        'X-Chunk-Index': index.toString(),
        'X-File-Name': fileName
      },
      body: chunk
    });
    
    if (!response.ok) {
      throw new Error(`Upload failed: ${response.statusText}`);
    }
    
    return response;
  }

  async bufferAndUpload(filePath, serverUrl) {
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
              await this.uploadChunk(serverUrl, record.data, i, filePath);
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