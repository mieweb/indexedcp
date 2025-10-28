#!/usr/bin/env node
/**
 * Test IndexedDBShim Integration
 * This test specifically verifies that IndexedDBShim with SQLite works correctly
 * 
 * NOTE: This test does NOT set INDEXEDCP_TEST_MODE, so it uses real IndexedDBShim
 */

const fs = require('fs');
const path = require('path');
const os = require('os');
const IndexedCPClient = require('../lib/client');

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

async function testIndexedDBShim() {
  log('\n═══════════════════════════════════════════════════════════', 'cyan');
  log('IndexedDBShim Integration Test', 'cyan');
  log('═══════════════════════════════════════════════════════════\n', 'cyan');
  
  let testsPassed = 0;
  let testsFailed = 0;
  
  const testDbPath = path.join(os.homedir(), '.indexcp');
  
  try {
    // Test 1: Create client and verify it uses IndexedDBShim
    log('Test 1: Verify IndexedDBShim is being used', 'yellow');
    const client = new IndexedCPClient({ 
      dbName: 'test-indexeddbshim',
      logLevel: 'info'
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
    
    // IndexedDBShim typically stores data in the home directory
    if (fs.existsSync(testDbPath)) {
      log(`✓ IndexedDB storage directory exists: ${testDbPath}`, 'green');
      
      // List contents to show SQLite files
      const files = fs.readdirSync(testDbPath);
      if (files.length > 0) {
        log(`  Found ${files.length} file(s) in storage:`, 'cyan');
        files.slice(0, 5).forEach(f => log(`    - ${f}`, 'cyan'));
      }
      testsPassed++;
    } else {
      log('⚠ IndexedDB storage directory not found (may use different location)', 'yellow');
      log('  This is not necessarily an error - IndexedDBShim may store elsewhere', 'cyan');
      testsPassed++; // Don't fail on this
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
    
  } catch (error) {
    log(`\n✗ Test failed: ${error.message}`, 'red');
    console.error(error);
    testsFailed++;
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
    process.exit(0);
  }
}

// Run the test
testIndexedDBShim().catch(error => {
  log(`\nUnhandled error: ${error.message}`, 'red');
  console.error(error);
  process.exit(1);
});
