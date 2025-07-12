// examples/client-only.js
// Example showing how to use only the client functionality
// This is ideal for browser environments or when you only need upload capabilities

// Import only the client (no server dependencies loaded)
const IndexCPClient = require('../client');

async function clientOnlyExample() {
  console.log('Client-only example - uploading files...');
  
  const client = new IndexCPClient();
  
  // Add a file to the buffer
  await client.addFile('./myfile.txt');
  console.log('File added to buffer');
  
  // Upload buffered files to a remote server
  await client.uploadBufferedFiles('http://localhost:3000/upload');
  console.log('Files uploaded successfully');
}

// Usage
if (require.main === module) {
  clientOnlyExample().catch(console.error);
}

module.exports = clientOnlyExample;