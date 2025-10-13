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

  async addFile(filePath) {
    const db = await this.initDB();
    
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

  async uploadBufferedFiles(serverUrl) {
    const apiKey = await this.getApiKey();
    
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
