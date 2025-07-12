// examples/client-stream.js
const fs = require('fs');
const fetch = require('node-fetch');

// Set up IndexedDB for Node.js environment
require('fake-indexeddb/auto');
const { openDB } = require('idb'); // IndexedDB wrapper

async function bufferAndUpload(filePath, serverUrl) {
  const db = await openDB('indexcp', 1, {
    upgrade(db) {
      db.createObjectStore('chunks', { keyPath: 'id', autoIncrement: true });
    }
  });

  return new Promise((resolve, reject) => {
    const readStream = fs.createReadStream(filePath, { highWaterMark: 1024 * 1024 }); // 1MB chunks
    let chunkIndex = 0;
    const chunks = [];

    readStream.on('data', (chunk) => {
      chunks.push({ id: chunkIndex, data: chunk });
      chunkIndex++;
    });

    readStream.on('end', async () => {
      try {
        // Add chunks to IndexedDB
        for (const chunk of chunks) {
          await db.add('chunks', chunk);
        }
        
        // Upload chunks
        for (let i = 0; i < chunkIndex; i++) {
          const record = await db.get('chunks', i);
          if (record) {
            await uploadChunk(serverUrl, record.data, i);
            await db.delete('chunks', i);
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

async function uploadChunk(serverUrl, chunk, index) {
  const apiKey = process.env.INDEXCP_API_KEY || 'your-api-key-here';
  
  await fetch(serverUrl, {
    method: 'POST',
    headers: { 
      'Content-Type': 'application/octet-stream', 
      'X-Chunk-Index': index,
      'Authorization': `Bearer ${apiKey}`
    },
    body: chunk
  });
}

// Usage
bufferAndUpload('./myfile.txt', 'http://localhost:3000/upload').catch(console.error);