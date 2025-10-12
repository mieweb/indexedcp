// Example: Client getting server-determined filenames
const IndexCPClient = require('indexedcp/client');

async function uploadWithFilenameMapping() {
  const client = new IndexCPClient();
  
  // Add files to buffer
  await client.addFile('./document.pdf');
  await client.addFile('./image.jpg');
  
  // Upload files and get server filename mappings
  const uploadResults = await client.uploadBufferedFiles('http://localhost:3000/upload');
  
  console.log('Upload complete! Server filename mappings:');
  
  // uploadResults maps client filenames to server filenames
  Object.entries(uploadResults).forEach(([clientPath, serverFilename]) => {
    const clientFilename = require('path').basename(clientPath);
    if (serverFilename !== clientFilename) {
      console.log(`${clientFilename} → ${serverFilename}`);
    } else {
      console.log(`${clientFilename} (no change)`);
    }
  });
  
  return uploadResults;
}

uploadWithFilenameMapping().catch(console.error);