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