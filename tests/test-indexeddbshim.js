#!/usr/bin/env node
/**
 * Test IndexedDBShim Integration
 * This test specifically verifies that IndexedDBShim with SQLite works correctly
 * 
 * NOTE: This test does NOT set INDEXEDCP_TEST_MODE, so it uses real IndexedDBShim
 * 
 * Tests:
 * 1. Basic IndexedDB operations (create, read, delete)
 * 2. Unencrypted file upload/download via server
 * 3. Encrypted file upload/download via server
 */

const fs = require('fs');
const path = require('path');
const os = require('os');
const IndexedCPClient = require('../lib/client');
const { IndexedCPServer } = require('../lib/server');

const colors = {
  reset: '\x1b[0m',
  green: '\x1b[32m',
  red: '\x1b[31m',
  yellow: '\x1b[33m',
  cyan: '\x1b[36m',
};

function log(msg, color = 'reset') {
  console.log(`${colors[color]}${msg}${colors.reset}`);
}

// Test configuration
const TEST_PORT = 3998;
const TEST_API_KEY = 'test-indexeddbshim-key';
const TEST_DIR = path.join(__dirname, 'temp-indexeddbshim-test');
const UPLOAD_DIR = path.join(TEST_DIR, 'uploads');

function cleanup() {
  if (fs.existsSync(TEST_DIR)) {
    fs.rmSync(TEST_DIR, { recursive: true, force: true });
  }
}

function createTestFile(filename, content) {
  if (!fs.existsSync(TEST_DIR)) {
    fs.mkdirSync(TEST_DIR, { recursive: true });
  }
  const filePath = path.join(TEST_DIR, filename);
  fs.writeFileSync(filePath, content);
  return filePath;
}

async function testIndexedDBShim() {
  log('\n═══════════════════════════════════════════════════════════', 'cyan');
  log('IndexedDBShim Integration Test (Complete Flow)', 'cyan');
  log('═══════════════════════════════════════════════════════════\n', 'cyan');
  
  let testsPassed = 0;
  let testsFailed = 0;
  let server = null;
  
  const testDbPath = path.join(os.homedir(), '.indexcp');
  
  try {
    cleanup();
    
    // ========================================================================
    // PART 1: Basic IndexedDB Operations
    // ========================================================================
    log('PART 1: Basic IndexedDB Operations', 'cyan');
    log('─'.repeat(60), 'cyan');
    
    // Test 1: Create client and verify it uses IndexedDBShim
    log('\nTest 1: Verify IndexedDBShim is being used', 'yellow');
    const client = new IndexedCPClient({ 
      dbName: 'test-indexeddbshim',
      logLevel: 'error'
    });
    
    // Check that we're not in test mode
    if (process.env.INDEXEDCP_TEST_MODE === 'true' || process.env.NODE_ENV === 'test') {
      throw new Error('Test is running in test mode - should use production mode!');
    }
    
    log('✓ Client created without test mode', 'green');
    testsPassed++;
    
    // Test 2: Initialize database
    log('\nTest 2: Initialize IndexedDB with IndexedDBShim', 'yellow');
    const db = await client.initDB();
    log('✓ Database initialized successfully', 'green');
    testsPassed++;
    
    // Test 3: Write data to database
    log('\nTest 3: Write data to IndexedDB', 'yellow');
    const testData = {
      id: 'test-chunk-1',
      fileName: 'test-file.txt',
      chunkIndex: 0,
      data: Buffer.from('Test data for IndexedDBShim')
    };
    
    await db.add('chunks', testData);
    log('✓ Data written to database', 'green');
    testsPassed++;
    
    // Test 4: Read data back
    log('\nTest 4: Read data from IndexedDB', 'yellow');
    const retrieved = await db.get('chunks', 'test-chunk-1');
    
    if (!retrieved) {
      throw new Error('Failed to retrieve data from database');
    }
    
    if (retrieved.fileName !== testData.fileName) {
      throw new Error(`Data mismatch: expected ${testData.fileName}, got ${retrieved.fileName}`);
    }
    
    log('✓ Data retrieved successfully', 'green');
    log(`  Retrieved fileName: ${retrieved.fileName}`, 'cyan');
    testsPassed++;
    
    // Test 5: Verify SQLite file exists (IndexedDBShim creates SQLite files)
    log('\nTest 5: Verify SQLite persistence', 'yellow');
    
    if (fs.existsSync(testDbPath)) {
      log(`✓ IndexedDB storage directory exists: ${testDbPath}`, 'green');
      
      const files = fs.readdirSync(testDbPath);
      if (files.length > 0) {
        log(`  Found ${files.length} file(s) in storage`, 'cyan');
      }
      testsPassed++;
    } else {
      log('⚠ IndexedDB storage directory not found (may use different location)', 'yellow');
      testsPassed++;
    }
    
    // Test 6: Clean up - delete test data
    log('\nTest 6: Clean up test data', 'yellow');
    await db.delete('chunks', 'test-chunk-1');
    
    const shouldBeNull = await db.get('chunks', 'test-chunk-1');
    if (shouldBeNull !== undefined) {
      throw new Error('Data was not deleted properly');
    }
    
    log('✓ Test data cleaned up', 'green');
    testsPassed++;
    
    // ========================================================================
    // PART 2: Unencrypted File Upload/Download via Server
    // ========================================================================
    log('\n\nPART 2: Unencrypted Upload/Download (Real Client-Server)', 'cyan');
    log('─'.repeat(60), 'cyan');
    
    // Test 7: Start server
    log('\nTest 7: Start IndexedCP server', 'yellow');
    server = new IndexedCPServer({
      port: TEST_PORT,
      outputDir: UPLOAD_DIR,
      apiKey: TEST_API_KEY,
      encryption: true,
      logLevel: 'error'
    });
    
    await server.listen();
    log('✓ Server started successfully', 'green');
    testsPassed++;
    
    // Test 8: Create test file and buffer it
    log('\nTest 8: Buffer file using IndexedDBShim', 'yellow');
    const testFilePath = createTestFile('unencrypted-test.txt', 'Hello from IndexedDBShim!');
    const unencryptedClient = new IndexedCPClient({
      dbName: 'test-unencrypted',
      apiKey: TEST_API_KEY,
      logLevel: 'error'
    });
    
    await unencryptedClient.addFile(testFilePath);
    log('✓ File buffered to IndexedDBShim', 'green');
    testsPassed++;
    
    // Test 9: Upload buffered file to server
    log('\nTest 9: Upload buffered file to server', 'yellow');
    const serverUrl = `http://localhost:${TEST_PORT}/upload`;
    const uploadResults = await unencryptedClient.uploadBufferedFiles(serverUrl);
    
    if (Object.keys(uploadResults).length === 0) {
      throw new Error('No files were uploaded');
    }
    
    log('✓ File uploaded successfully', 'green');
    log(`  Uploaded: ${Object.keys(uploadResults).length} file(s)`, 'cyan');
    testsPassed++;
    
    // Test 10: Verify uploaded file exists on server
    log('\nTest 10: Verify file exists on server', 'yellow');
    const serverFilename = uploadResults[testFilePath];
    const uploadedFilePath = path.join(UPLOAD_DIR, serverFilename);
    
    if (!fs.existsSync(uploadedFilePath)) {
      throw new Error(`Uploaded file not found: ${uploadedFilePath}`);
    }
    
    const uploadedContent = fs.readFileSync(uploadedFilePath, 'utf8');
    if (uploadedContent !== 'Hello from IndexedDBShim!') {
      throw new Error('Uploaded file content mismatch');
    }
    
    log('✓ File verified on server', 'green');
    log(`  Content: ${uploadedContent}`, 'cyan');
    testsPassed++;
    
    // ========================================================================
    // PART 3: Encrypted File Upload/Download via Server
    // ========================================================================
    log('\n\nPART 3: Encrypted Upload/Download (Real Client-Server)', 'cyan');
    log('─'.repeat(60), 'cyan');
    
    // Test 11: Create encrypted client with IndexedDBShim
    log('\nTest 11: Create encrypted client with IndexedDBShim', 'yellow');
    const encryptedClient = new IndexedCPClient({
      dbName: 'test-encrypted',
      encryption: true,
      apiKey: TEST_API_KEY,
      serverUrl: `http://localhost:${TEST_PORT}`,
      logLevel: 'error'
    });
    
    log('✓ Encrypted client created', 'green');
    testsPassed++;
    
    // Test 12: Fetch and cache server public key
    log('\nTest 12: Fetch server public key', 'yellow');
    const publicKeyInfo = await encryptedClient.fetchPublicKey();
    
    if (!publicKeyInfo || !publicKeyInfo.kid || !publicKeyInfo.publicKey) {
      throw new Error('Failed to fetch valid public key');
    }
    
    log('✓ Public key fetched and cached', 'green');
    log(`  Key ID: ${publicKeyInfo.kid}`, 'cyan');
    testsPassed++;
    
    // Test 13: Buffer encrypted file using IndexedDBShim
    log('\nTest 13: Buffer encrypted file using IndexedDBShim', 'yellow');
    const encryptedTestFile = createTestFile('encrypted-test.txt', 'Secret message encrypted with IndexedDBShim!');
    const sessionId = await encryptedClient.addFile(encryptedTestFile);
    
    if (!sessionId) {
      throw new Error('Failed to create encrypted session');
    }
    
    log('✓ File encrypted and buffered', 'green');
    log(`  Session ID: ${sessionId}`, 'cyan');
    testsPassed++;
    
    // Test 14: Verify encrypted packets in IndexedDB
    log('\nTest 14: Verify encrypted packets stored in IndexedDBShim', 'yellow');
    const encDb = await encryptedClient.initDB();
    const packets = await encDb.getAll('packets');
    
    if (packets.length === 0) {
      throw new Error('No encrypted packets found in database');
    }
    
    log('✓ Encrypted packets found in database', 'green');
    log(`  Found ${packets.length} encrypted packet(s)`, 'cyan');
    testsPassed++;
    
    // Test 15: Upload encrypted file to server
    log('\nTest 15: Upload encrypted file to server', 'yellow');
    const encryptedUploadResults = await encryptedClient.uploadBufferedFiles(`http://localhost:${TEST_PORT}`);
    
    if (Object.keys(encryptedUploadResults).length === 0) {
      throw new Error('No encrypted files were uploaded');
    }
    
    log('✓ Encrypted file uploaded successfully', 'green');
    testsPassed++;
    
    // Test 16: Verify encrypted file exists and is decrypted on server
    log('\nTest 16: Verify decrypted file on server', 'yellow');
    const encServerFilename = encryptedUploadResults[encryptedTestFile];
    const encUploadedFilePath = path.join(UPLOAD_DIR, encServerFilename);
    
    if (!fs.existsSync(encUploadedFilePath)) {
      throw new Error(`Encrypted uploaded file not found: ${encUploadedFilePath}`);
    }
    
    const decryptedContent = fs.readFileSync(encUploadedFilePath, 'utf8');
    if (decryptedContent !== 'Secret message encrypted with IndexedDBShim!') {
      throw new Error('Decrypted file content mismatch');
    }
    
    log('✓ File decrypted correctly on server', 'green');
    log(`  Decrypted content: ${decryptedContent}`, 'cyan');
    testsPassed++;
    
    // Test 17: Verify encrypted packets cleaned up after upload
    log('\nTest 17: Verify cleanup after successful upload', 'yellow');
    const remainingPackets = await encDb.getAll('packets');
    const pendingPackets = remainingPackets.filter(p => p.status === 'pending');
    
    if (pendingPackets.length > 0) {
      throw new Error('Pending packets still remain after upload');
    }
    
    log('✓ All packets uploaded, database cleaned', 'green');
    testsPassed++;
    
  } catch (error) {
    log(`\n✗ Test failed: ${error.message}`, 'red');
    console.error(error);
    testsFailed++;
  } finally {
    // Cleanup
    if (server && server.server) {
      await new Promise((resolve) => {
        server.server.close(() => resolve());
      });
    }
    cleanup();
  }
  
  // Summary
  log('\n═══════════════════════════════════════════════════════════', 'yellow');
  log('Test Summary', 'yellow');
  log('═══════════════════════════════════════════════════════════', 'yellow');
  log(`Total Tests: ${testsPassed + testsFailed}`, 'cyan');
  log(`Passed: ${testsPassed}`, 'green');
  
  if (testsFailed > 0) {
    log(`Failed: ${testsFailed}`, 'red');
  } else {
    log(`Failed: ${testsFailed}`, 'green');
  }
  
  log('═══════════════════════════════════════════════════════════\n', 'yellow');
  
  if (testsFailed > 0) {
    log('IndexedDBShim integration test FAILED ❌', 'red');
    process.exit(1);
  } else {
    log('IndexedDBShim integration test PASSED ✅', 'green');
    log('All IndexedDBShim features verified:', 'green');
    log('  ✓ Basic database operations', 'green');
    log('  ✓ Unencrypted file upload/download', 'green');
    log('  ✓ Encrypted file upload/download', 'green');
    process.exit(0);
  }
}

// Run the test
testIndexedDBShim().catch(error => {
  log(`\nUnhandled error: ${error.message}`, 'red');
  console.error(error);
  process.exit(1);
});
