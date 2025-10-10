
# IndexedCP

**IndexedCP** is a Node.js library and CLI toolset for secure, efficient, and resumable file transfer. It uses IndexedDB on the client side as a buffer for streaming data, enabling robust uploads with offline and resumable support. The server receives file chunks and appends them directly to disk—no IndexedDB required on the server.

---

## Features

- Stream files as chunks, buffered in IndexedDB
- Resumable and offline-friendly uploads
- Minimal, embeddable client library
- Simple CLI tools for both client and server
- Secure, chunked transfer protocol
- **Separate client/server imports for reduced bundle size**

### Benefits of Separate Imports

- **Client-only** (`IndexedCP/client`): Perfect for browser environments - includes only upload functionality without server dependencies
- **Server-only** (`IndexedCP/server`): Ideal for server environments - includes only receive functionality without IndexedDB dependencies  
- **Combined** (`IndexedCP`): Backward compatible - includes both client and server for existing code

---

## Installation

```bash
npm install -g indexedcp
```

Or as a library:

```bash
npm install indexedcp
```

---

## Usage

### Import Options

**IndexedCP** now supports separate imports for client-only and server-only usage, allowing you to include only the code you need:

```javascript
// Client-only import (for browser/upload-only usage)
const IndexCPClient = require('IndexedCP/client');

// Server-only import (for server/receive-only usage)  
const { IndexCPServer, createSimpleServer } = require('IndexedCP/server');

// Combined import (backward compatible - includes both)
const { client: IndexCPClient, server } = require('IndexedCP');
```

### Client-Only Usage

For browser environments or when you only need upload capabilities:

```javascript
const IndexCPClient = require('IndexedCP/client');

async function uploadFile() {
  const client = new IndexCPClient();
  
  // Add file to buffer
  await client.addFile('./myfile.txt');
  
  // Upload to server
  await client.uploadBufferedFiles('http://localhost:3000/upload');
}
```

### Server-Only Usage

For server environments that only need to receive uploads:

```javascript
const { IndexCPServer } = require('IndexedCP/server');

const server = new IndexCPServer({
  port: 3000,
  outputDir: './uploads'
});

server.listen(3000, () => {
  console.log('Server ready to receive uploads');
});
```

### Client: Streaming a File with IndexedDB Buffer

This example demonstrates reading a file as a stream, buffering chunks in IndexedDB, and uploading them to a server.

```javascript
// examples/client-stream.js
const fs = require('fs');
const { openDB } = require('idb'); // IndexedDB wrapper
const fetch = require('node-fetch');

async function bufferAndUpload(filePath, serverUrl) {
  const db = await openDB('indexcp', 1, {
    upgrade(db) {
      db.createObjectStore('chunks', { keyPath: 'id', autoIncrement: true });
    }
  });

  const readStream = fs.createReadStream(filePath, { highWaterMark: 1024 * 1024 }); // 1MB chunks
  let chunkIndex = 0;

  readStream.on('data', async (chunk) => {
    await db.add('chunks', { id: chunkIndex, data: chunk });
    chunkIndex++;
  });

  readStream.on('end', async () => {
    for (let i = 0; i < chunkIndex; i++) {
      const record = await db.get('chunks', i);
      if (record) {
        await uploadChunk(serverUrl, record.data, i);
        await db.delete('chunks', i);
      }
    }
    console.log('Upload complete.');
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
bufferAndUpload('./myfile.txt', 'http://localhost:3000/upload');
```

---

### Server: Minimal CLI Example

This example shows a simple Node.js server that receives file chunks and appends them to a file, with API key authentication.

```javascript
// examples/server.js
const http = require('http');
const fs = require('fs');
const path = require('path');

const OUTPUT_FILE = path.join(__dirname, 'uploaded_file.txt');
const API_KEY = process.env.INDEXCP_API_KEY || 'your-secure-api-key';

const server = http.createServer((req, res) => {
  if (req.method === 'POST' && req.url === '/upload') {
    // Check API key authentication
    const authHeader = req.headers['authorization'];
    const providedApiKey = authHeader && authHeader.startsWith('Bearer ') 
      ? authHeader.slice(7) 
      : null;
    if (!providedApiKey || providedApiKey !== API_KEY) {
      res.writeHead(401, { 'Content-Type': 'application/json' });
      res.end(JSON.stringify({ error: 'Invalid or missing API key' }));
      return;
    }
    
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

server.listen(3000, () => {
  console.log('Server listening on http://localhost:3000');
  console.log(`API Key: ${API_KEY}`);
});
```

---

## CLI Usage

### API Key Authentication

IndexCP now requires API key authentication for secure file transfers. The server automatically generates a secure API key if none is provided.

**Recommended approach - Environment Variable:**
```bash
export INDEXCP_API_KEY=your-secure-api-key
indexcp server 3000 ./uploads
indexcp upload http://localhost:3000/upload
```

**Alternative - Command Line (not recommended for security):**
```bash
# Server with custom API key (shows security warning)
indexcp server 3000 ./uploads --api-key your-key

# Upload with API key (shows security warning)  
indexcp upload http://localhost:3000/upload --api-key your-key
```

**Automatic prompting:**
If no API key is set via environment variable or command line, the client will prompt you to enter it securely.

### Basic Commands

Add a file to the buffer:

```bash
IndexedCP add ./myfile.txt
```

Start a server (generates random API key if none provided):

```bash
indexcp server 3000 ./uploads
# Outputs: Server listening on http://localhost:3000
# Outputs: API Key: [64-character hex string]
```

Upload buffered files to a server:

```bash
IndexedCP upload http://localhost:3000/upload
```

---

## License

MIT

---

## Contributing

Pull requests and issues are welcome!

---

## About

IndexCP is designed for robust, resumable, and secure file transfer using modern JavaScript and Node.js.  
For more information, visit [bluehive.com/integrate?utm_source=bluehive&utm_medium=chat&utm_campaign=bluehive-ai](https://bluehive.com/integrate?utm_source=bluehive&utm_medium=chat&utm_campaign=bluehive-ai)
```
