#!/usr/bin/env node
'use strict';

/**
 * Test unified server with encryption enabled
 */

// Set test mode to use fake-indexeddb
process.env.INDEXEDCP_TEST_MODE = 'true';

const { IndexedCPServer } = require('../lib/server');

async function testEncryptionIntegration() {
  console.log('🧪 Testing unified server with encryption...\n');
  
  // Test 1: Server without encryption (backward compatible)
  console.log('Test 1: Server without encryption');
  const plainServer = new IndexedCPServer({
    port: 3001,
    outputDir: './test-output-plain'
  });
  
  await plainServer.listen(3001);
  const plainStatus = plainServer.getEncryptionStatus();
  console.log('Status:', plainStatus);
  console.assert(plainStatus.encryption === false, 'Encryption should be disabled');
  plainServer.close();
  console.log('✓ Plain server works\n');
  
  // Test 2: Server with encryption enabled
  console.log('Test 2: Server with encryption enabled');
  const encryptedServer = new IndexedCPServer({
    port: 3002,
    outputDir: './test-output-encrypted',
    encryption: true,
    keystoreType: 'memory'
  });
  
  await encryptedServer.listen(3002);
  const encryptedStatus = encryptedServer.getEncryptionStatus();
  console.log('Status:', encryptedStatus);
  console.assert(encryptedStatus.encryption === true, 'Encryption should be enabled');
  console.assert(encryptedStatus.activeKeyId !== null, 'Should have active key');
  console.assert(encryptedStatus.totalKeys === 1, 'Should have 1 key');
  
  // Test public key fetch
  const publicKey = encryptedServer.getActivePublicKey();
  console.assert(publicKey.publicKey, 'Should have public key');
  console.assert(publicKey.kid, 'Should have key ID');
  console.log('✓ Public key:', publicKey.kid);
  
  encryptedServer.close();
  console.log('✓ Encrypted server works\n');
  
  console.log('✅ All tests passed!');
}

testEncryptionIntegration().catch(error => {
  console.error('✗ Test failed:', error);
  process.exit(1);
});
