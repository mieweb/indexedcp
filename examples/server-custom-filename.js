// Example: Server with custom filename generation
const { IndexedCPServer } = require('indexedcp/server');
const crypto = require('crypto');
const path = require('path');

// Create server that generates UUID filenames
const server = new IndexedCPServer({
  port: 3000,
  outputDir: './uploads',
  apiKey: 'your-secure-api-key',
  filenameGenerator: (clientFilename, chunkIndex, req) => {
    // Generate UUID filename but preserve original extension
    const ext = path.extname(clientFilename);
    return crypto.randomUUID() + ext;
  }
});

server.listen(3000, () => {
  console.log('Server with custom filename generation ready!');
  console.log('Files will be saved with UUID names instead of client names');
});

// The server will now:
// 1. Accept client filename via X-File-Name header
// 2. Generate its own UUID-based filename
// 3. Return the actual filename used in JSON response
// 4. Client will receive and display the server-determined filename