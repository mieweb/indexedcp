// examples/client-only.js
// Example showing how to use only the client functionality
// This is ideal for browser environments or when you only need upload capabilities

// Import only the client (no server dependencies loaded)
const IndexCPClient = require('../client')

async function clientOnlyExample() {
  console.log('Client-only example - uploading files and relaying chunks...');
  const client = new IndexCPClient({ relayMaxRetries: 3, relayRetryDelay: 1000 });

  // Add a file to the buffer
  await client.addFile('../myfile.txt');
  console.log('File added to buffer');

  // Example relay callback: simulate external app
  async function relayCallback(chunkData, meta) {
    // Simulate sending chunk to external app (e.g., HTTP, WebSocket, etc.)
    console.log(`[example relay] Got chunk ${meta.chunkIndex} (${meta.fileName}), id=${meta.id}`);
    // Simulate confirmation (always true)
    await new Promise(res => setTimeout(res, 100));
    return true;
  }

  // Start relay loop (in background)
  client.relayChunksInOrder({
    fileName: '../myfile.txt',
    onChunk: relayCallback,
    maxRetries: 3,
    retryDelay: 1000
  });

  // Let relay run for a few seconds, then stop
  setTimeout(() => {
    client.stopRelay();
  }, 5000);
}

// Usage
if (require.main === module) {
  clientOnlyExample().catch(console.error);
}

module.exports = clientOnlyExample;