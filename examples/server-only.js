// examples/server-only.js  
// Example showing how to use only the server functionality
// This is ideal for server environments that only need to receive uploads

// Import only the server (no client/IndexedDB dependencies loaded)
const { IndexCPServer, createSimpleServer } = require('../server');

function serverOnlyExample() {
  console.log('Server-only example - receiving uploads...');
  
  // Option 1: Use the IndexCPServer class
  const server = new IndexCPServer({
    port: 3000,
    outputDir: './uploads'
  });
  
  server.listen(3000, () => {
    console.log('IndexCP server running on port 3000');
    console.log('Ready to receive file uploads at /upload');
  });
  
  // Option 2: Use the simple server function (uncomment to use instead)
  // const simpleServer = createSimpleServer('./uploads/received_file.txt', 3001);
  // console.log('Simple server running on port 3001');
  
  // Graceful shutdown
  process.on('SIGINT', () => {
    console.log('\nShutting down server...');
    server.close();
    process.exit(0);
  });
  
  return server;
}

// Usage
if (require.main === module) {
  serverOnlyExample();
}

module.exports = serverOnlyExample;