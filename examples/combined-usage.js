// examples/combined-usage.js
// Example showing backward-compatible usage with both client and server
// This demonstrates the original way of importing everything

// Import both client and server (traditional way - still works)
const { client: IndexedCPClient, server } = require('../index');
const { IndexedCPServer } = server;

async function combinedExample() {
  console.log('Combined usage example...');
  
  // Start server
  const serverInstance = new IndexedCPServer({
    port: 3000,
    outputDir: './uploads'
  });
  
  serverInstance.listen(3000, async () => {
    console.log('Server started on port 3000');
    
    // Use client to upload to the server
    const clientInstance = new IndexedCPClient();
    
    try {
      // In a real scenario, you might wait a bit or have the file ready
      console.log('Client and server both available in the same process');
      console.log('This demonstrates backward compatibility');
      
      // Close server after demo
      setTimeout(() => {
        serverInstance.close();
        console.log('Demo completed - server closed');
      }, 1000);
      
    } catch (error) {
      console.error('Error in combined example:', error);
      serverInstance.close();
    }
  });
}

// Usage
if (require.main === module) {
  combinedExample().catch(console.error);
}

module.exports = combinedExample;