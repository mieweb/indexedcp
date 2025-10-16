#!/usr/bin/env node
'use strict';

const fs = require('fs').promises;
const path = require('path');
const { createKeyStore } = require('../lib/keystores');
const cryptoUtils = require('../lib/crypto-utils');

// Test utilities
let testsPassed = 0;
let testsFailed = 0;

function assert(condition, message) {
  if (!condition) {
    console.error(`✗ ${message}`);
    testsFailed++;
    throw new Error(`Assertion failed: ${message}`);
  }
  testsPassed++;
}

async function cleanup(testDir) {
  try {
    await fs.rm(testDir, { recursive: true, force: true });
  } catch (error) {
    // Ignore cleanup errors
  }
}

// Test FileSystemKeyStore
async function testFileSystemKeyStore() {
  console.log('\n📁 Testing FileSystemKeyStore...');
  const testDir = path.join(__dirname, '.test-keystore');
  
  try {
    await cleanup(testDir);
    
    const keystore = createKeyStore('filesystem', {
      keyStorePath: testDir
    });
    
    await keystore.initialize();
    
    // Test save and load
    const keyPair = await cryptoUtils.generateServerKeyPair();
    const keyData = {
      kid: keyPair.kid,
      publicKey: keyPair.publicKey,
      privateKey: keyPair.privateKey,
      createdAt: Date.now(),
      active: true
    };
    
    await keystore.save(keyData.kid, keyData);
    console.log(`  ✓ Saved key ${keyData.kid}`);
    
    const loaded = await keystore.load(keyData.kid);
    assert(loaded.kid === keyData.kid, 'Loaded key has correct kid');
    assert(loaded.publicKey === keyData.publicKey, 'Loaded key has correct publicKey');
    assert(loaded.privateKey === keyData.privateKey, 'Loaded key has correct privateKey');
    console.log(`  ✓ Loaded key ${keyData.kid}`);
    
    // Test exists
    const exists = await keystore.exists(keyData.kid);
    assert(exists === true, 'Key exists check returns true');
    console.log(`  ✓ Exists check works`);
    
    // Test list
    const list = await keystore.list();
    assert(list.length === 1, 'List returns one key');
    assert(list[0] === keyData.kid, 'List contains correct kid');
    console.log(`  ✓ List returns correct keys`);
    
    // Test loadAll
    const allKeys = await keystore.loadAll();
    assert(allKeys.length === 1, 'LoadAll returns one key');
    assert(allKeys[0].kid === keyData.kid, 'LoadAll contains correct key');
    console.log(`  ✓ LoadAll works`);
    
    // Test delete
    await keystore.delete(keyData.kid);
    const existsAfterDelete = await keystore.exists(keyData.kid);
    assert(existsAfterDelete === false, 'Key deleted successfully');
    console.log(`  ✓ Delete works`);
    
    // Test load non-existent key
    const nonExistent = await keystore.load('non-existent-kid');
    assert(nonExistent === null, 'Load returns null for non-existent key');
    console.log(`  ✓ Load non-existent returns null`);
    
    await keystore.close();
    console.log('✅ FileSystemKeyStore tests passed');
    
  } finally {
    await cleanup(testDir);
  }
}

// Test MemoryKeyStore
async function testMemoryKeyStore() {
  console.log('\n💾 Testing MemoryKeyStore...');
  
  const keystore = createKeyStore('memory');
  await keystore.initialize();
  
  // Test save and load
  const keyPair = await cryptoUtils.generateServerKeyPair();
  const keyData = {
    kid: keyPair.kid,
    publicKey: keyPair.publicKey,
    privateKey: keyPair.privateKey,
    createdAt: Date.now(),
    active: true
  };
  
  await keystore.save(keyData.kid, keyData);
  console.log(`  ✓ Saved key ${keyData.kid}`);
  
  const loaded = await keystore.load(keyData.kid);
  assert(loaded.kid === keyData.kid, 'Loaded key has correct kid');
  console.log(`  ✓ Loaded key ${keyData.kid}`);
  
  // Test getStats
  const stats = keystore.getStats();
  assert(stats.totalKeys === 1, 'Stats shows 1 key');
  console.log(`  ✓ Stats: ${JSON.stringify(stats)}`);
  
  // Test delete
  await keystore.delete(keyData.kid);
  const existsAfterDelete = await keystore.exists(keyData.kid);
  assert(existsAfterDelete === false, 'Key deleted successfully');
  console.log(`  ✓ Delete works`);
  
  await keystore.close();
  console.log('✅ MemoryKeyStore tests passed');
}

// Test keystore factory
async function testKeystoreFactory() {
  console.log('\n🏭 Testing Keystore Factory...');
  
  // Test filesystem creation
  const fsStore = createKeyStore('filesystem', { keyStorePath: '.test-factory-fs' });
  assert(fsStore.constructor.name === 'FileSystemKeyStore', 'Factory creates FileSystemKeyStore');
  console.log('  ✓ Factory creates FileSystemKeyStore');
  
  // Test memory creation
  const memStore = createKeyStore('memory');
  assert(memStore.constructor.name === 'MemoryKeyStore', 'Factory creates MemoryKeyStore');
  console.log('  ✓ Factory creates MemoryKeyStore');
  
  // Test mongodb creation (without actual client - just verify class instantiation)
  try {
    createKeyStore('mongodb', { connectionString: 'mongodb://localhost:27017' });
    assert(false, 'Factory should throw without MongoDB client');
  } catch (error) {
    assert(error.message.includes('MongoDB client is required'), 'Factory requires MongoDB client');
    console.log('  ✓ Factory validates MongoDB client requirement');
  }
  
  // Test invalid type
  try {
    createKeyStore('invalid-type');
    assert(false, 'Factory should throw for invalid type');
  } catch (error) {
    assert(error.message.includes('Unknown keystore type'), 'Factory throws for invalid type');
    console.log('  ✓ Factory throws for invalid type');
  }
  
  console.log('✅ Keystore Factory tests passed');
  
  // Cleanup
  await cleanup('.test-factory-fs');
}

// Test EncryptedServer with keystore persistence
async function testServerPersistence() {
  console.log('\n🔐 Testing EncryptedServer Key Persistence...');
  const testDir = path.join(__dirname, '.test-server-keystore');
  
  try {
    await cleanup(testDir);
    
    const EncryptedServer = require('../lib/encrypted-server');
    
    // Create server with filesystem keystore
    const server1 = new EncryptedServer({
      port: 3001,
      saveDirectory: path.join(testDir, 'uploads'),
      keystoreType: 'filesystem',
      keystoreOptions: {
        keyStorePath: path.join(testDir, 'keys')
      }
    });
    
    await server1.listen(3001);
    const kid1 = server1.activeKeyId;
    console.log(`  ✓ Server 1 started with key ${kid1}`);
    
    // Close and restart
    server1.close();
    console.log(`  ✓ Server 1 closed`);
    
    // Create new server instance (simulating restart)
    const server2 = new EncryptedServer({
      port: 3002,
      saveDirectory: path.join(testDir, 'uploads'),
      keystoreType: 'filesystem',
      keystoreOptions: {
        keyStorePath: path.join(testDir, 'keys')
      }
    });
    
    await server2.listen(3002);
    const kid2 = server2.activeKeyId;
    console.log(`  ✓ Server 2 started with key ${kid2}`);
    
    // Verify key persistence
    assert(kid2 === kid1, 'Server loaded same key after restart');
    console.log(`  ✓ Key persisted across restart`);
    
    // Verify old key can still decrypt
    const privateKey = server2.getPrivateKey(kid1);
    assert(privateKey !== null, 'Old key still available for decryption');
    console.log(`  ✓ Old key still available for decryption`);
    
    server2.close();
    console.log('✅ Server persistence tests passed');
    
  } finally {
    await cleanup(testDir);
  }
}

// Main test runner
async function runTests() {
  console.log('🧪 Keystore Integration Tests\n');
  console.log('='.repeat(50));
  
  try {
    await testFileSystemKeyStore();
    await testMemoryKeyStore();
    await testKeystoreFactory();
    await testServerPersistence();
    
    console.log('\n' + '='.repeat(50));
    console.log(`\n✅ All tests passed! (${testsPassed} assertions)`);
    console.log(`   Tests passed: ${testsPassed}`);
    console.log(`   Tests failed: ${testsFailed}`);
    process.exit(0);
  } catch (error) {
    console.error('\n' + '='.repeat(50));
    console.error(`\n✗ Tests failed: ${error.message}`);
    console.error(`   Tests passed: ${testsPassed}`);
    console.error(`   Tests failed: ${testsFailed}`);
    process.exit(1);
  }
}

// Run if called directly
if (require.main === module) {
  runTests().catch(error => {
    console.error('Fatal error:', error);
    process.exit(1);
  });
}

module.exports = { runTests };
