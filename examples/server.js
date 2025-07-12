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