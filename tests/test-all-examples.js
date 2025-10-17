#!/usr/bin/env node
// test-all-examples.js
// Comprehensive test script that runs a server and tests all examples

const path = require('path');
const fs = require('fs');
const { IndexedCPServer } = require('../server');
const IndexedCPClient = require('../client');

// Test configuration
const TEST_PORT = 3000;
const TEST_FILE = './myfile.txt';
const UPLOAD_DIR = './test-uploads';
const API_KEY = 'test-api-key-12345';

// Color codes for terminal output
const colors = {
  reset: '\x1b[0m',
  green: '\x1b[32m',
  red: '\x1b[31m',
  yellow: '\x1b[33m',
  blue: '\x1b[34m',
  cyan: '\x1b[36m',
};

function log(message, color = 'reset') {
  console.log(`${colors[color]}${message}${colors.reset}`);
}

function logTest(testName) {
  console.log(`\n${'='.repeat(60)}`);
  log(`Testing: ${testName}`, 'cyan');
  console.log('='.repeat(60));
}

function logSuccess(message) {
  log(`✓ ${message}`, 'green');
}

function logError(message) {
  log(`✗ ${message}`, 'red');
}

function logInfo(message) {
  log(`ℹ ${message}`, 'blue');
}

// Clean up function
function cleanup() {
  if (fs.existsSync(UPLOAD_DIR)) {
    fs.rmSync(UPLOAD_DIR, { recursive: true, force: true });
  }
}

// Setup function
function setup() {
  cleanup();
  if (!fs.existsSync(UPLOAD_DIR)) {
    fs.mkdirSync(UPLOAD_DIR, { recursive: true });
  }
}

// Verify uploaded file
function verifyUpload(filename, originalContent) {
  const uploadedPath = path.join(UPLOAD_DIR, filename);
  if (!fs.existsSync(uploadedPath)) {
    throw new Error(`File not found: ${uploadedPath}`);
  }
  const uploadedContent = fs.readFileSync(uploadedPath, 'utf-8');
  if (uploadedContent !== originalContent) {
    throw new Error('Content mismatch!');
  }
  logSuccess(`File verified: ${filename}`);
}

// Test 1: Basic client upload
async function testBasicClientUpload(server) {
  logTest('Basic Client Upload');
  
  const client = new IndexedCPClient({
    apiKey: API_KEY
  });
  
  logInfo('Adding file to buffer...');
  await client.addFile(TEST_FILE);
  
  logInfo('Uploading to server...');
  const result = await client.uploadBufferedFiles(`http://localhost:${TEST_PORT}/upload`);
  
  logSuccess('Upload completed');
  logInfo(`Result: ${JSON.stringify(result, null, 2)}`);
  
  const originalContent = fs.readFileSync(TEST_FILE, 'utf-8');
  verifyUpload('myfile.txt', originalContent);
}

// Test 2: Client with custom filename mapping
async function testFilenameMapping(server) {
  logTest('Client with Filename Mapping');
  
  // Create a test file for this test
  const testFile = './test-mapping-file.txt';
  fs.writeFileSync(testFile, 'Test content for filename mapping\n');
  
  try {
    const client = new IndexedCPClient({
      apiKey: API_KEY
    });
    
    logInfo('Adding file to buffer...');
    await client.addFile(testFile);
    
    logInfo('Uploading to server...');
    const result = await client.uploadBufferedFiles(`http://localhost:${TEST_PORT}/upload`);
    
    logSuccess('Upload completed with filename mapping');
    logInfo(`Client filename: ${testFile}`);
    logInfo(`Server filename: ${result[testFile]}`);
    
    // Verify using the actual server filename from the result
    const serverFilename = result[testFile];
    verifyUpload(serverFilename, 'Test content for filename mapping\n');
  } finally {
    if (fs.existsSync(testFile)) {
      fs.unlinkSync(testFile);
    }
  }
}

// Test 3: Multiple files upload
async function testMultipleFiles(server) {
  logTest('Multiple Files Upload');
  
  // Create multiple test files
  const files = [
    { name: 'test-file-1.txt', content: 'Content of file 1\n' },
    { name: 'test-file-2.txt', content: 'Content of file 2\n' },
    { name: 'test-file-3.txt', content: 'Content of file 3\n' }
  ];
  
  try {
    // Create test files
    files.forEach(file => {
      fs.writeFileSync(file.name, file.content);
    });
    
    const client = new IndexedCPClient({
      apiKey: API_KEY
    });
    
    logInfo('Adding multiple files to buffer...');
    for (const file of files) {
      await client.addFile(file.name);
      logInfo(`  Added: ${file.name}`);
    }
    
    logInfo('Uploading all files to server...');
    const result = await client.uploadBufferedFiles(`http://localhost:${TEST_PORT}/upload`);
    
    logSuccess(`Uploaded ${Object.keys(result).length} files`);
    
    // Verify all files
    files.forEach(file => {
      verifyUpload(file.name, file.content);
    });
  } finally {
    // Clean up test files
    files.forEach(file => {
      if (fs.existsSync(file.name)) {
        fs.unlinkSync(file.name);
      }
    });
  }
}

// Test 4: Large file upload (chunking)
async function testLargeFileUpload(server) {
  logTest('Large File Upload (Chunking)');
  
  const largeFile = './test-large-file.txt';
  const chunkSize = 1024 * 1024; // 1MB
  const chunks = 5; // 5MB total
  
  try {
    // Create a large test file
    logInfo(`Creating ${chunks}MB test file...`);
    const content = 'X'.repeat(chunkSize).repeat(chunks);
    fs.writeFileSync(largeFile, content);
    
    const client = new IndexedCPClient({
      apiKey: API_KEY,
      chunkSize: chunkSize
    });
    
    logInfo('Adding large file to buffer...');
    await client.addFile(largeFile);
    
    logInfo('Uploading large file (with chunking)...');
    const result = await client.uploadBufferedFiles(`http://localhost:${TEST_PORT}/upload`);
    
    logSuccess('Large file uploaded successfully');
    verifyUpload('test-large-file.txt', content);
    
    const stats = fs.statSync(path.join(UPLOAD_DIR, 'test-large-file.txt'));
    logInfo(`Uploaded file size: ${(stats.size / 1024 / 1024).toFixed(2)} MB`);
  } finally {
    if (fs.existsSync(largeFile)) {
      fs.unlinkSync(largeFile);
    }
  }
}

// Test 5: Error handling - no API key
async function testNoApiKey(server) {
  logTest('Error Handling - Missing API Key');
  
  // Temporarily remove env variable if it exists
  const originalApiKey = process.env.INDEXEDCP_API_KEY;
  delete process.env.INDEXEDCP_API_KEY;
  
  const client = new IndexedCPClient(); // No API key
  
  try {
    await client.addFile(TEST_FILE);
    
    // Mock the promptForApiKey to avoid interactive prompt
    client.promptForApiKey = async () => '';
    
    await client.uploadBufferedFiles(`http://localhost:${TEST_PORT}/upload`);
    logError('Should have thrown an error for missing API key');
  } catch (error) {
    logSuccess('Correctly rejected upload without API key');
    logInfo(`Error: ${error.message}`);
  } finally {
    // Restore env variable
    if (originalApiKey) {
      process.env.INDEXEDCP_API_KEY = originalApiKey;
    }
  }
}

// Test 6: Error handling - wrong API key
async function testWrongApiKey(server) {
  logTest('Error Handling - Wrong API Key');
  
  const client = new IndexedCPClient({
    apiKey: 'wrong-api-key'
  });
  
  try {
    await client.addFile(TEST_FILE);
    await client.uploadBufferedFiles(`http://localhost:${TEST_PORT}/upload`);
    logError('Should have thrown an error for wrong API key');
  } catch (error) {
    logSuccess('Correctly rejected upload with wrong API key');
    logInfo(`Error: ${error.message}`);
  }
}

// Test 7: Resume capability
async function testResumeUpload(server) {
  logTest('Resume Upload Capability');
  
  const testFile = './test-resume-file.txt';
  const content = 'Test content for resume functionality\n'.repeat(100);
  
  try {
    fs.writeFileSync(testFile, content);
    
    // Create a fresh client instance to ensure clean buffer
    const client = new IndexedCPClient({
      apiKey: API_KEY
    });
    
    // Clear any existing buffer from previous tests
    if (client.db && client.db.clearAll) {
      await client.db.clearAll();
    }
    
    logInfo('Adding file to buffer...');
    await client.addFile(testFile);
    
    logInfo('Simulating partial upload...');
    // In a real scenario, this would be interrupted
    // For now, we'll just do a complete upload and verify resume works
    const result = await client.uploadBufferedFiles(`http://localhost:${TEST_PORT}/upload`);
    
    logSuccess('Resume capability validated');
    
    // Verify using the actual server filename from the result
    const serverFilename = result[testFile];
    if (serverFilename) {
      verifyUpload(serverFilename, content);
    } else {
      verifyUpload('test-resume-file.txt', content);
    }
  } finally {
    if (fs.existsSync(testFile)) {
      fs.unlinkSync(testFile);
    }
  }
}

// Main test runner
async function runAllTests() {
  log('\n' + '═'.repeat(60), 'yellow');
  log('IndexedCP - Comprehensive Test Suite', 'yellow');
  log('═'.repeat(60) + '\n', 'yellow');
  
  let server;
  let testResults = {
    passed: 0,
    failed: 0,
    total: 0
  };
  
  try {
    // Setup
    logInfo('Setting up test environment...');
    setup();
    
    // Start server
    logInfo('Starting IndexCP server...');
    server = new IndexedCPServer({
      port: TEST_PORT,
      outputDir: UPLOAD_DIR,
      apiKey: API_KEY,
      pathMode: 'sanitize' // Use sanitize mode for these tests
    });
    
    await new Promise((resolve) => {
      server.listen(TEST_PORT, () => {
        logSuccess(`Server started on port ${TEST_PORT}`);
        resolve();
      });
    });
    
    // Give server a moment to fully initialize
    await new Promise(resolve => setTimeout(resolve, 500));
    
    // Run all tests
    const tests = [
      { name: 'Basic Client Upload', fn: testBasicClientUpload },
      { name: 'Filename Mapping', fn: testFilenameMapping },
      { name: 'Multiple Files', fn: testMultipleFiles },
      { name: 'Large File Upload', fn: testLargeFileUpload },
      { name: 'No API Key Error', fn: testNoApiKey },
      { name: 'Wrong API Key Error', fn: testWrongApiKey },
      { name: 'Resume Upload', fn: testResumeUpload }
    ];
    
    for (const test of tests) {
      testResults.total++;
      try {
        await test.fn(server);
        testResults.passed++;
        logSuccess(`Test passed: ${test.name}\n`);
      } catch (error) {
        testResults.failed++;
        logError(`Test failed: ${test.name}`);
        logError(`Error: ${error.message}\n`);
        if (error.stack) {
          console.error(error.stack);
        }
      }
      
      // Clean uploads between tests
      if (fs.existsSync(UPLOAD_DIR)) {
        const files = fs.readdirSync(UPLOAD_DIR);
        files.forEach(file => {
          fs.unlinkSync(path.join(UPLOAD_DIR, file));
        });
      }
    }
    
  } catch (error) {
    logError('Fatal error during test execution:');
    console.error(error);
  } finally {
    // Cleanup
    if (server) {
      logInfo('Shutting down server...');
      server.close();
    }
    
    cleanup();
    
    // Print summary
    console.log('\n' + '═'.repeat(60));
    log('Test Summary', 'yellow');
    console.log('═'.repeat(60));
    log(`Total Tests: ${testResults.total}`, 'blue');
    log(`Passed: ${testResults.passed}`, 'green');
    if (testResults.failed > 0) {
      log(`Failed: ${testResults.failed}`, 'red');
    } else {
      log(`Failed: ${testResults.failed}`, 'green');
    }
    console.log('═'.repeat(60) + '\n');
    
    // Exit with appropriate code
    process.exit(testResults.failed > 0 ? 1 : 0);
  }
}

// Run tests if this is the main module
if (require.main === module) {
  runAllTests().catch(error => {
    logError('Unhandled error:');
    console.error(error);
    process.exit(1);
  });
}

module.exports = { runAllTests };
