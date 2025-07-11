
# IndexCP

**IndexCP** is a Node.js library and CLI toolset for secure, efficient, and resumable file transfer. It uses IndexedDB on the client side as a buffer for streaming data, enabling robust uploads with offline and resumable support. The server receives file chunks and appends them directly to disk—no IndexedDB required on the server.

---

## Features

- Stream files as chunks, buffered in IndexedDB
- Resumable and offline-friendly uploads
- Minimal, embeddable client library
- Simple CLI tools for both client and server
- Secure, chunked transfer protocol

---

## Installation

```bash
npm install -g indexcp
```

Or as a library:

```bash
npm install indexcp
```

---

## Usage

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
  await fetch(serverUrl, {
    method: 'POST',
    headers: { 'Content-Type': 'application/octet-stream', 'X-Chunk-Index': index },
    body: chunk
  });
}

// Usage
bufferAndUpload('./myfile.txt', 'http://localhost:3000/upload');
```

---

### Server: Minimal CLI Example

This example shows a simple Node.js server that receives file chunks and appends them to a file.

```javascript
// examples/server.js
const http = require('http');
const fs = require('fs');
const path = require('path');

const OUTPUT_FILE = path.join(__dirname, 'uploaded_file.txt');

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

server.listen(3000, () => {
  console.log('Server listening on http://localhost:3000');
});
```

---

## CLI Usage

Add a file to the buffer:

```bash
indexcp add ./myfile.txt
```

Upload buffered files to a server:

```bash
indexcp upload http://localhost:3000/upload
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
