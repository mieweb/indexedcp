#!/usr/bin/env node
'use strict';

/**
 * Test unified client with encryption
 */

const IndexCPClient = require('../lib/client');
const fs = require('fs');
const path = require('path');

async function testClientIntegration() {
  console.log('🧪 Testing unified client with encryption...\n');
  
  const testDir = path.join(__dirname, '.test-client');
  const testFile = path.join(testDir, 'test.txt');
  
  // Setup
  if (!fs.existsSync(testDir)) {
    fs.mkdirSync(testDir, { recursive: true });
  }
  fs.writeFileSync(testFile, 'Hello, encrypted world!');
  
  try {
    // Test 1: Client without encryption
    console.log('Test 1: Client without encryption');
    const plainClient = new IndexCPClient({
      dbName: 'test-plain-client',
      apiKey: 'test-key'
    });
    
    const status1 = await plainClient.getEncryptionStatus();
    console.log('Status:', status1);
    console.assert(status1.encryption === false, 'Encryption should be disabled');
    console.log('✓ Plain client works\n');
    
    // Test 2: Client with encryption
    console.log('Test 2: Client with encryption enabled');
    const encryptedClient = new IndexCPClient({
      dbName: 'test-encrypted-client',
      apiKey: 'test-key',
      serverUrl: 'http://localhost:3000',
      encryption: true
    });
    
    const status2 = await encryptedClient.getEncryptionStatus();
    console.log('Status:', status2);
    console.assert(status2.encryption === true, 'Encryption should be enabled');
    console.assert(status2.activeSessions === 0, 'Should have no sessions initially');
    console.log('✓ Encrypted client initialized\n');
    
    console.log('✅ All tests passed!');
  } finally {
    // Cleanup
    fs.rmSync(testDir, { recursive: true, force: true });
  }
}

testClientIntegration().catch(error => {
  console.error('✗ Test failed:', error);
  process.exit(1);
});
