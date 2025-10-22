#!/usr/bin/env node

/**
 * Test: CLI ls command
 * Tests the indexcp ls command for listing buffered files
 */

const { execSync } = require('child_process');
const fs = require('fs');
const path = require('path');
const os = require('os');

// Remove test mode to force IndexedDBShim usage for persistence
// This affects: 1) The IndexedCPClient require below, 2) Child processes via runCommand()
delete process.env.NODE_ENV;
delete process.env.INDEXEDCP_TEST_MODE;

const IndexedCPClient = require('../lib/client');

const DB_DIR = path.join(os.homedir(), '.indexcp', 'db');

console.log('\n=== Testing CLI ls Command ===\n');

// Helper to run commands without test mode
// Note: We clean the env again here because child processes get a fresh copy
function runCommand(cmd) {
  const cleanEnv = { ...process.env };
  delete cleanEnv.NODE_ENV;
  delete cleanEnv.INDEXEDCP_TEST_MODE;
  return execSync(cmd, { encoding: 'utf-8', env: cleanEnv });
}

async function runTest() {
  let testsPassed = 0;
  let testsFailed = 0;

  // Clean up any existing test files and database
  async function cleanup() {
    try {
      const client = new IndexedCPClient();
      const db = await client.initDB();
      const tx = db.transaction(client.storeName, 'readwrite');
      const store = tx.objectStore(client.storeName);
      const chunks = await store.getAll();
      for (const chunk of chunks) {
        await store.delete(chunk.id);
      }
      if (tx.done) await tx.done;
      console.log('✓ Cleaned up IndexedDB');
    } catch (error) {
      console.log('Note: IndexedDB cleanup skipped (may not exist yet)');
    }

    // Clean up database directory (IndexedDBShim SQLite files)
    if (fs.existsSync(DB_DIR)) {
      fs.rmSync(DB_DIR, { recursive: true, force: true });
    }

    // Clean up test files
    ['test-file-1.txt', 'test-file-2.txt', 'test-large.bin'].forEach(file => {
      if (fs.existsSync(file)) {
        fs.unlinkSync(file);
      }
    });
  }

  // Test 1: Empty buffer
  console.log('Test 1: List empty buffer');
  try {
    await cleanup();
    const output = runCommand('node bin/indexcp ls');
    if (output.includes('No files in buffer')) {
      console.log('✓ Test 1 passed: Empty buffer message displayed\n');
      testsPassed++;
    } else {
      console.error('✗ Test 1 failed: Expected empty buffer message');
      console.error('Output:', output);
      testsFailed++;
    }
  } catch (error) {
    console.error('✗ Test 1 failed:', error.message);
    testsFailed++;
  }

  // Test 2: Single file
  console.log('Test 2: List single file');
  try {
    // Create a test file
    fs.writeFileSync('test-file-1.txt', 'Hello, World!');

    // Add it to buffer
    runCommand('node bin/indexcp add test-file-1.txt');

    // List it
    const output = runCommand('node bin/indexcp ls');

    if (output.includes('Total files: 1') && 
      output.includes('test-file-1.txt') &&
        output.includes('1 chunk(s)')) {
      console.log('✓ Test 2 passed: Single file listed correctly\n');
      testsPassed++;
    } else {
      console.error('✗ Test 2 failed: Expected single file details');
      console.error('Output:', output);
      testsFailed++;
    }
  } catch (error) {
    console.error('✗ Test 2 failed:', error.message);
    testsFailed++;
  }

  // Test 3: Multiple files
  console.log('Test 3: List multiple files');
  try {
    // Create another test file
    fs.writeFileSync('test-file-2.txt', 'Another test file');

    // Add it to buffer
    runCommand('node bin/indexcp add test-file-2.txt');

    // List all files
    const output = runCommand('node bin/indexcp ls');

    if (output.includes('Total files: 2') && 
      output.includes('test-file-1.txt') &&
        output.includes('test-file-2.txt')) {
      console.log('✓ Test 3 passed: Multiple files listed correctly\n');
      testsPassed++;
    } else {
      console.error('✗ Test 3 failed: Expected two files');
      console.error('Output:', output);
      testsFailed++;
    }
  } catch (error) {
    console.error('✗ Test 3 failed:', error.message);
    testsFailed++;
  }

  // Test 4: Large file with multiple chunks
  console.log('Test 4: List file with multiple chunks');
  try {
    // Create a 3MB file (will be split into 3 chunks)
    const largeBuffer = Buffer.alloc(3 * 1024 * 1024, 'X');
    fs.writeFileSync('test-large.bin', largeBuffer);

    // Add it to buffer
    runCommand('node bin/indexcp add test-large.bin');

    // List all files
    const output = runCommand('node bin/indexcp ls');

    if (output.includes('Total files: 3') && 
      output.includes('test-large.bin') &&
        output.includes('3 chunk(s)')) {
      console.log('✓ Test 4 passed: Multi-chunk file listed correctly\n');
      testsPassed++;
    } else {
      console.error('✗ Test 4 failed: Expected three chunks for large file');
      console.error('Output:', output);
      testsFailed++;
    }
  } catch (error) {
    console.error('✗ Test 4 failed:', error.message);
    testsFailed++;
  }

  // Test 5: Verbose mode
  console.log('Test 5: Verbose mode shows chunk details');
  try {
    const output = runCommand('node bin/indexcp ls -v');

    if (output.includes('Chunk 0:') && 
      output.includes('Chunk 1:') &&
        output.includes('Chunk 2:')) {
      console.log('✓ Test 5 passed: Verbose mode shows chunk details\n');
      testsPassed++;
    } else {
      console.error('✗ Test 5 failed: Expected chunk details in verbose mode');
      console.error('Output:', output);
      testsFailed++;
    }
  } catch (error) {
    console.error('✗ Test 5 failed:', error.message);
    testsFailed++;
  }

  // Test 6: --verbose flag (long form)
  console.log('Test 6: --verbose flag works');
  try {
    const output = runCommand('node bin/indexcp ls --verbose');

    if (output.includes('Chunk 0:')) {
      console.log('✓ Test 6 passed: --verbose flag works\n');
      testsPassed++;
    } else {
      console.error('✗ Test 6 failed: --verbose flag did not show chunk details');
      console.error('Output:', output);
      testsFailed++;
    }
  } catch (error) {
    console.error('✗ Test 6 failed:', error.message);
    testsFailed++;
  }

  // Test 7: list alias
  console.log('Test 7: "list" alias works');
  try {
    const output = runCommand('node bin/indexcp list');

    if (output.includes('Total files:')) {
      console.log('✓ Test 7 passed: "list" alias works\n');
      testsPassed++;
    } else {
      console.error('✗ Test 7 failed: "list" command did not work');
      console.error('Output:', output);
      testsFailed++;
    }
  } catch (error) {
    console.error('✗ Test 7 failed:', error.message);
    testsFailed++;
  }

  // Test 8: Size calculations
  console.log('Test 8: Size calculations are correct');
  try {
    const output = runCommand('node bin/indexcp ls');

    // test-large.bin should show 3072.00 KB (3MB)
    if (output.includes('3072.00 KB')) {
      console.log('✓ Test 8 passed: Size calculations are correct\n');
      testsPassed++;
    } else {
      console.error('✗ Test 8 failed: Size calculation incorrect');
      console.error('Output:', output);
      testsFailed++;
    }
  } catch (error) {
    console.error('✗ Test 8 failed:', error.message);
    testsFailed++;
  }

  // Test 9: Files are sorted alphabetically
  console.log('Test 9: Files are sorted alphabetically');
  try {
    const output = runCommand('node bin/indexcp ls');

    // Extract file names from output
    const lines = output.split('\n');
    const fileLines = lines.filter(line => line.includes('.txt') || line.includes('.bin'));

    // Check order: test-file-1.txt, test-file-2.txt, test-large.bin
    const firstIndex = output.indexOf('test-file-1.txt');
    const secondIndex = output.indexOf('test-file-2.txt');
    const thirdIndex = output.indexOf('test-large.bin');

    if (firstIndex < secondIndex && secondIndex < thirdIndex) {
      console.log('✓ Test 9 passed: Files are sorted alphabetically\n');
      testsPassed++;
    } else {
      console.error('✗ Test 9 failed: Files not sorted correctly');
      console.error('Order:', firstIndex, secondIndex, thirdIndex);
      testsFailed++;
    }
  } catch (error) {
    console.error('✗ Test 9 failed:', error.message);
    testsFailed++;
  }

  // Cleanup
  await cleanup();

  // Summary
  console.log('=================================');
  console.log(`Tests Passed: ${testsPassed}`);
  console.log(`Tests Failed: ${testsFailed}`);
  console.log('=================================\n');

  if (testsFailed === 0) {
    console.log('All CLI ls Tests Passed! 🎉\n');
    process.exit(0);
  } else {
    console.error(`${testsFailed} test(s) failed\n`);
    process.exit(1);
  }
}

// Run tests
runTest().catch(error => {
  console.error('Test suite error:', error);
  process.exit(1);
});
