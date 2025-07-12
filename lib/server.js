const http = require('http');
const fs = require('fs');
const path = require('path');
const crypto = require('crypto');

class IndexCPServer {
  constructor(options = {}) {
    this.outputDir = options.outputDir || process.cwd();
    this.port = options.port || 3000;
    this.apiKey = options.apiKey || this.generateApiKey();
    this.server = null;
  }

  generateApiKey() {
    return crypto.randomBytes(32).toString('hex');
  }

  createServer() {
    this.server = http.createServer((req, res) => {
      if (req.method === 'POST' && req.url === '/upload') {
        // Check API key authentication
        const authHeader = req.headers['authorization'];
        const providedApiKey = authHeader && authHeader.startsWith('Bearer ') 
          ? authHeader.slice(7) 
          : null;
        if (!providedApiKey || providedApiKey !== this.apiKey) {
          res.writeHead(401, { 'Content-Type': 'application/json' });
          res.end(JSON.stringify({ error: 'Invalid or missing API key' }));
          return;
        }
        
        this.handleUpload(req, res);
      } else {
        res.writeHead(404);
        res.end('Not Found');
      }
    });

    return this.server;
  }

  handleUpload(req, res) {
    const chunkIndex = req.headers['x-chunk-index'];
    const fileName = req.headers['x-file-name'] || 'uploaded_file.txt';
    
    const outputFile = path.join(this.outputDir, path.basename(fileName));
    const writeStream = fs.createWriteStream(outputFile, { flags: 'a' });
    
    req.pipe(writeStream);
    
    req.on('end', () => {
      console.log(`Chunk ${chunkIndex} received for ${fileName}`);
      res.writeHead(200);
      res.end('Chunk received\n');
    });

    req.on('error', (error) => {
      console.error('Upload error:', error);
      res.writeHead(500);
      res.end('Upload error\n');
    });

    writeStream.on('error', (error) => {
      console.error('Write error:', error);
      res.writeHead(500);
      res.end('Write error\n');
    });
  }

  listen(port, callback) {
    const serverPort = port || this.port;
    if (!this.server) {
      this.createServer();
    }
    
    this.server.listen(serverPort, () => {
      console.log(`Server listening on http://localhost:${serverPort}`);
      console.log(`API Key: ${this.apiKey}`);
      console.log('Include this API key in requests using the Authorization: Bearer <token> header');
      if (callback) callback();
    });
  }

  close() {
    if (this.server) {
      this.server.close();
    }
  }
}

// Helper function to create a simple server like in the example
function createSimpleServer(outputFile, port = 3000) {
  const OUTPUT_FILE = outputFile || path.join(process.cwd(), 'uploaded_file.txt');

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

  server.listen(port, () => {
    console.log(`Server listening on http://localhost:${port}`);
  });

  return server;
}

module.exports = {
  IndexCPServer,
  createSimpleServer
};