const http = require('http');
const fs = require('fs');
const path = require('path');
const crypto = require('crypto');

class IndexCPServer {
  constructor(options = {}) {
    this.outputDir = options.outputDir || process.cwd();
    this.port = options.port || 3000;
    this.apiKey = options.apiKey || this.generateApiKey();
    this.filenameGenerator = options.filenameGenerator || null; // Optional custom filename generator
    
    // Path handling mode:
    // 'ignore' (default) - Generate unique filenames with original name appended
    // 'sanitize' - Strip all paths, prevent overwrites with unique suffix
    // 'allow-paths' - Allow client to create subdirectories
    this.pathMode = options.pathMode || 'ignore';
    
    // Track filenames across chunks for the same upload session
    this.uploadSessions = new Map(); // clientFileName -> actualFileName
    
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
    const clientFileName = req.headers['x-file-name'] || 'uploaded_file.txt';
    
    let outputFile;
    let actualFileName;
    
    // Handle different path modes
    if (this.pathMode === 'ignore') {
      // Mode: 'ignore' - Generate unique filename with full path preserved
      const timestamp = Date.now();
      const random = crypto.randomBytes(4).toString('hex');
      
      // Preserve full path by replacing separators with single underscore
      // Strip leading ./ or .\
      let fullPath = clientFileName.replace(/^\.\//, '').replace(/^\.\\/, '');
      
      // Replace path separators with single underscore
      fullPath = fullPath.replace(/[/\\]+/g, '_');
      
      // Extract extension
      const ext = path.extname(fullPath);
      const nameWithoutExt = fullPath.slice(0, fullPath.length - ext.length);
      
      // Sanitize to be filesystem-safe:
      // - Keep letters, numbers, underscores (path markers), dots, and existing dashes
      // - Replace all other characters with dash
      const safeName = nameWithoutExt.replace(/[^a-zA-Z0-9._-]/g, '-');
      
      // Format: <timestamp>_<random>_<full-path-with-underscores>.<ext>
      let proposedName = `${timestamp}_${random}_${safeName}${ext}`;
      
      // Check filename length (most filesystems support 255 chars)
      const MAX_FILENAME_LENGTH = 255;
      if (proposedName.length > MAX_FILENAME_LENGTH) {
        // Truncate the safe name part to fit
        const prefixLength = `${timestamp}_${random}_`.length;
        const maxSafeNameLength = MAX_FILENAME_LENGTH - prefixLength - ext.length;
        const truncatedName = safeName.slice(0, maxSafeNameLength);
        proposedName = `${timestamp}_${random}_${truncatedName}${ext}`;
      }
      
      actualFileName = proposedName;
      outputFile = path.join(this.outputDir, actualFileName);
      
    } else if (this.pathMode === 'allow-paths') {
      // Mode: 'allow-paths' - Allow subdirectories from client
      // Still protect against traversal attacks
      const cleanedFileName = clientFileName.replace(/^\.\//, '').replace(/^\.\\/, '');
      
      // Reject traversal attempts and absolute paths
      const hasTraversal = cleanedFileName.includes('..');
      const hasAbsolutePath = cleanedFileName.startsWith('/') || 
                             /^[A-Za-z]:/.test(cleanedFileName) ||
                             cleanedFileName.startsWith('\\\\');
      
      if (hasTraversal || hasAbsolutePath) {
        console.error(`Security: Rejected filename with traversal/absolute path: ${clientFileName}`);
        res.writeHead(400, { 'Content-Type': 'application/json' });
        res.end(JSON.stringify({ 
          error: 'Invalid filename',
          message: 'Filename must not contain traversal sequences or absolute paths'
        }));
        return;
      }
      
      // Allow paths but normalize separators
      actualFileName = cleanedFileName.split(/[/\\]+/).join(path.sep);
      outputFile = path.join(this.outputDir, actualFileName);
      
      // Security: Verify the resolved path is inside outputDir
      const resolvedOutputFile = path.resolve(outputFile);
      const resolvedOutputDir = path.resolve(this.outputDir);
      if (!resolvedOutputFile.startsWith(resolvedOutputDir + path.sep) && 
          resolvedOutputFile !== resolvedOutputDir) {
        console.error(`Security: Path traversal attempt blocked: ${clientFileName}`);
        res.writeHead(403, { 'Content-Type': 'application/json' });
        res.end(JSON.stringify({ error: 'Access denied: invalid path' }));
        return;
      }
      
      // Create subdirectories if needed
      const outputFileDir = path.dirname(outputFile);
      if (!fs.existsSync(outputFileDir)) {
        fs.mkdirSync(outputFileDir, { recursive: true });
      }
      
    } else {
      // Mode: 'sanitize' (default) - Strip paths, prevent overwrites
      
      // Use custom generator if provided
      if (this.filenameGenerator && typeof this.filenameGenerator === 'function') {
        actualFileName = this.filenameGenerator(clientFileName, chunkIndex, req);
      } else {
        actualFileName = path.basename(clientFileName);
      }
      
      // Strip common relative path prefixes
      const cleanedFileName = clientFileName.replace(/^\.\//, '').replace(/^\.\\/, '');
      
      // Reject if filename contains path separators or traversal attempts  
      const hasPathSeparators = cleanedFileName.includes('/') || 
                                cleanedFileName.includes('\\');
      const hasTraversal = clientFileName.includes('..');
      const hasAbsolutePath = clientFileName.startsWith('/') || 
                             /^[A-Za-z]:/.test(clientFileName) ||
                             clientFileName.startsWith('\\\\');
      
      if (hasPathSeparators || hasTraversal || hasAbsolutePath) {
        console.error(`Security: Rejected filename with path components: ${clientFileName}`);
        res.writeHead(400, { 'Content-Type': 'application/json' });
        res.end(JSON.stringify({ 
          error: 'Invalid filename',
          message: 'Filename must not contain path separators or traversal sequences'
        }));
        return;
      }
      
      // Use only the basename to ensure we stay in outputDir
      const safeName = path.basename(actualFileName);
      
      // Validate that we have a valid filename after sanitization
      if (!safeName || safeName === '.' || safeName === '..' || safeName.length === 0) {
        res.writeHead(400, { 'Content-Type': 'application/json' });
        res.end(JSON.stringify({ error: 'Invalid filename' }));
        return;
      }
      
      actualFileName = safeName;
      
      // Check if we have a session for this file
      const isFirstChunk = !chunkIndex || chunkIndex === '0' || parseInt(chunkIndex) === 0;
      
      if (this.uploadSessions.has(clientFileName)) {
        // Use the same filename from the first chunk
        actualFileName = this.uploadSessions.get(clientFileName);
      } else {
        // First chunk - check for overwrites and create session
        outputFile = path.join(this.outputDir, actualFileName);
        
        if (fs.existsSync(outputFile)) {
          const ext = path.extname(actualFileName);
          const base = path.basename(actualFileName, ext);
          const timestamp = Date.now();
          actualFileName = `${base}_${timestamp}${ext}`;
        }
        
        // Store the filename for subsequent chunks
        this.uploadSessions.set(clientFileName, actualFileName);
      }
      
      outputFile = path.join(this.outputDir, actualFileName);
      
      // Security: Verify the resolved path is inside outputDir
      const resolvedOutputFile = path.resolve(outputFile);
      const resolvedOutputDir = path.resolve(this.outputDir);
      if (!resolvedOutputFile.startsWith(resolvedOutputDir + path.sep) && 
          resolvedOutputFile !== resolvedOutputDir) {
        console.error(`Security: Path traversal attempt blocked: ${clientFileName}`);
        res.writeHead(403, { 'Content-Type': 'application/json' });
        res.end(JSON.stringify({ error: 'Access denied: invalid path' }));
        return;
      }
    }
    
    // Ensure output directory exists
    if (!fs.existsSync(this.outputDir)) {
      fs.mkdirSync(this.outputDir, { recursive: true });
    }
    
    const writeStream = fs.createWriteStream(outputFile, { flags: 'a' });
    
    req.pipe(writeStream);
    
    req.on('end', () => {
      console.log(`Chunk ${chunkIndex} received for ${clientFileName} -> ${actualFileName}`);
      
      // Return response with actual filename used
      res.writeHead(200, { 'Content-Type': 'application/json' });
      res.end(JSON.stringify({
        message: 'Chunk received',
        actualFilename: actualFileName,
        chunkIndex: parseInt(chunkIndex),
        clientFilename: clientFileName
      }));
    });

    req.on('error', (error) => {
      console.error('Upload error:', error);
      if (!res.headersSent) {
        res.writeHead(500, { 'Content-Type': 'application/json' });
        res.end(JSON.stringify({ error: 'Upload error', message: error.message }));
      }
    });

    writeStream.on('error', (error) => {
      console.error('Write error:', error);
      if (!res.headersSent) {
        res.writeHead(500, { 'Content-Type': 'application/json' });
        res.end(JSON.stringify({ error: 'Write error', message: error.message }));
      }
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