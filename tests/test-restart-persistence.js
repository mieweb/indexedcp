#!/usr/bin/env node

/**
 * Test: Restart Persistence
 * 
 * Verifies that buffered chunks persist across process restarts when using
 * filesystem storage (the default for Node.js environments).
 * 
 * Test flow:
 * 1. Add files to buffer in one p    const verifyScript = `
      const IndexedCPClient = require('${path.join(__dirname, '..', 'lib', 'client.js')}');
      
      async function verifyCleared() {
        const client = new IndexedCPClient();
        const db = await client.initDB();
        const tx = db.transaction('chunks', 'readonly');
        const store = tx.objectStore('chunks');
        const chunks = await store.getAll();
        if (tx.done) await tx.done;
        
        console.log('Chunks remaining: ' + chunks.length);
        if (chunks.length > 0) {
          chunks.forEach((chunk, i) => {
            console.log('  Remaining chunk ' + i + ': id=' + chunk.id + ', filename=' + chunk.filename);
          });
        }
      }
      
      verifyCleared().catch(err => {
        console.error('Error:', err.message);
        process.exit(1);
      });
    `;minate the process
 * 3. Start a new process and verify buffered files are still present
 * 4. Upload the persisted files successfully
 */

const { spawn } = require('child_process');
const path = require('path');
const fs = require('fs');
const os = require('os');

const TEST_DIR = path.join(__dirname, 'temp-restart-test');
const DB_PATH = path.join(os.homedir(), '.indexcp', 'db', 'chunks.json');

// Colors for output
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

function cleanup() {
  // Clean up test directory
  if (fs.existsSync(TEST_DIR)) {
    fs.rmSync(TEST_DIR, { recursive: true, force: true });
  }
  
  // Clean up database
  if (fs.existsSync(DB_PATH)) {
    fs.unlinkSync(DB_PATH);
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

function runNodeScript(code) {
  return new Promise((resolve, reject) => {
    const child = spawn('node', ['-e', code], {
      env: { ...process.env, INDEXEDCP_CLI_MODE: 'true' },
      cwd: __dirname
    });
    
    let stdout = '';
    let stderr = '';
    
    child.stdout.on('data', (data) => {
      stdout += data.toString();
    });
    
    child.stderr.on('data', (data) => {
      stderr += data.toString();
    });
    
    child.on('close', (code) => {
      if (code !== 0) {
        reject(new Error(`Process exited with code ${code}\n${stderr}`));
      } else {
        resolve({ stdout, stderr });
      }
    });
  });
}

async function testRestartPersistence() {
  log('\n════════════════════════════════════════════════════════════', 'cyan');
  log('IndexedCP - Restart Persistence Test', 'cyan');
  log('════════════════════════════════════════════════════════════\n', 'cyan');
  
  let testsPassed = 0;
  let testsFailed = 0;
  
  try {
    // Setup
    log('ℹ Setting up test environment...', 'blue');
    cleanup();
    
    const file1 = createTestFile('restart-test-1.txt', 'Content for file 1 - should persist!');
    const file2 = createTestFile('restart-test-2.txt', 'Content for file 2 - should also persist!');
    const file3 = createTestFile('restart-test-3.txt', 'Content for file 3 - you guessed it, persists!');
    
    log('✓ Test files created', 'green');
    
    // Step 1: Add files to buffer in first process
    log('\n============================================================', 'yellow');
    log('Step 1: Adding files to buffer (Process #1)', 'yellow');
    log('============================================================', 'yellow');
    
    const addScript = `
      const IndexedCPClient = require('${path.join(__dirname, '..', 'lib', 'client.js')}');
      
      async function addFiles() {
        const client = new IndexedCPClient();
        await client.addFile('${file1}');
        console.log('Added file 1');
        await client.addFile('${file2}');
        console.log('Added file 2');
        await client.addFile('${file3}');
        console.log('Added file 3');
      }
      
      addFiles().catch(console.error);
    `;
    
    const result1 = await runNodeScript(addScript);
    log(result1.stdout.trim(), 'blue');
    log('✓ Files added to buffer', 'green');
    
    // Verify database file exists
    if (!fs.existsSync(DB_PATH)) {
      throw new Error('Database file was not created');
    }
    log(`✓ Database persisted at ${DB_PATH}`, 'green');
    testsPassed++;
    
    // Read the database to verify content
    const dbContent = JSON.parse(fs.readFileSync(DB_PATH, 'utf8'));
    const chunkCount = Array.isArray(dbContent) ? dbContent.length : 0;
    log(`✓ Database contains ${chunkCount} chunk(s)`, 'green');
    
    if (chunkCount !== 3) {
      throw new Error(`Expected 3 chunks, found ${chunkCount}`);
    }
    testsPassed++;
    
    // Step 2: Simulate restart - read from database in new process
    log('\n============================================================', 'yellow');
    log('Step 2: Simulating restart (Process #2)', 'yellow');
    log('============================================================', 'yellow');
    
    const readScript = `
      const IndexedCPClient = require('${path.join(__dirname, '..', 'lib', 'client.js')}');
      
      async function readBuffer() {
        const client = new IndexedCPClient();
        // Initialize DB by calling initDB
        const db = await client.initDB();
        const tx = db.transaction('chunks', 'readonly');
        const store = tx.objectStore('chunks');
        const chunks = await store.getAll();
        if (tx.done) await tx.done;
        
        console.log('Chunks found in buffer: ' + chunks.length);
        for (let i = 0; i < chunks.length; i++) {
          console.log('  Chunk ' + i + ': ' + chunks[i].filename);
        }
      }
      
      readBuffer().catch(err => {
        console.error('Error:', err.message);
        process.exit(1);
      });
    `;
    
    const result2 = await runNodeScript(readScript);
    log(result2.stdout.trim(), 'blue');
    
    if (!result2.stdout.includes('Chunks found in buffer: 3')) {
      throw new Error('Chunks were not persisted across restart');
    }
    log('✓ All chunks persisted across restart', 'green');
    testsPassed++;
    
    // Step 3: Upload the persisted files
    log('\n============================================================', 'yellow');
    log('Step 3: Uploading persisted files (Process #3)', 'yellow');
    log('============================================================', 'yellow');
    
    // Start a test server
    const { IndexedCPServer } = require('../lib/server');
    const uploadDir = path.join(TEST_DIR, 'uploads');
    fs.mkdirSync(uploadDir, { recursive: true });
    
    const server = new IndexedCPServer({ 
      port: 3456, 
      outputDir: uploadDir,
      apiKey: 'test-restart-key'
    });
    
    await new Promise((resolve) => {
      server.listen(3456);
      setTimeout(resolve, 500); // Give server time to start
    });
    
    log('✓ Test server started on port 3456', 'green');
    
    const uploadScript = `
      const IndexedCPClient = require('${path.join(__dirname, '..', 'lib', 'client.js')}');
      
      async function uploadBuffered() {
        const client = new IndexedCPClient({ apiKey: 'test-restart-key' });
        const results = await client.uploadBufferedFiles('http://localhost:3456/upload');
        console.log('Upload results:', JSON.stringify(results));
      }
      
      uploadBuffered().catch(console.error);
    `;
    
    const result3 = await runNodeScript(uploadScript);
    log(result3.stdout.trim(), 'blue');
    
    // Verify files were uploaded
    const uploadedFiles = fs.readdirSync(uploadDir);
    log(`✓ Files uploaded: ${uploadedFiles.join(', ')}`, 'green');
    
    if (uploadedFiles.length !== 3) {
      throw new Error(`Expected 3 uploaded files, found ${uploadedFiles.length}`);
    }
    testsPassed++;
    
    // Verify file contents
    for (const filename of uploadedFiles) {
      const uploadedPath = path.join(uploadDir, filename);
      const content = fs.readFileSync(uploadedPath, 'utf8');
      if (!content.includes('should persist') && !content.includes('should also persist') && !content.includes('you guessed it')) {
        throw new Error(`File ${filename} has incorrect content`);
      }
    }
    log('✓ All uploaded files have correct content', 'green');
    testsPassed++;
    
    // Verify buffer is cleared after successful upload
    log('\n============================================================', 'yellow');
    log('Step 4: Verifying buffer cleared after upload', 'yellow');
    log('============================================================', 'yellow');
    
    const verifyScript = `
      const IndexedCPClient = require('${path.join(__dirname, '..', 'lib', 'client.js')}');
      
      async function verifyCleared() {
        const client = new IndexedCPClient();
        const db = await client.db;
        const tx = db.transaction('chunks', 'readonly');
        const store = tx.objectStore('chunks');
        const chunks = await store.getAll();
        await tx.done;
        
        console.log('Chunks remaining: ' + chunks.length);
      }
      
      verifyCleared().catch(console.error);
    `;
    
    const result4 = await runNodeScript(verifyScript);
    log(result4.stdout.trim(), 'blue');
    
    // Check if buffer is empty (either "Chunks remaining: 0" or no database file)
    const bufferCleared = result4.stdout.includes('Chunks remaining: 0') || 
                          !fs.existsSync(DB_PATH) ||
                          JSON.parse(fs.readFileSync(DB_PATH, 'utf8') || '[]').length === 0;
    
    if (!bufferCleared) {
      throw new Error('Buffer was not cleared after successful upload');
    }
    log('✓ Buffer cleared after successful upload', 'green');
    testsPassed++;
    
    // Cleanup
    server.close();
    cleanup();
    
    log('\n════════════════════════════════════════════════════════════', 'cyan');
    log('Test Summary', 'cyan');
    log('════════════════════════════════════════════════════════════', 'cyan');
    log(`Total Tests: ${testsPassed + testsFailed}`, 'blue');
    log(`Passed: ${testsPassed}`, 'green');
    log(`Failed: ${testsFailed}`, testsFailed > 0 ? 'red' : 'green');
    log('════════════════════════════════════════════════════════════\n', 'cyan');
    
    if (testsFailed === 0) {
      log('All restart persistence tests passed! 🎉\n', 'green');
      process.exit(0);
    } else {
      process.exit(1);
    }
    
  } catch (error) {
    testsFailed++;
    log(`\n✗ Test failed: ${error.message}`, 'red');
    log(error.stack, 'red');
    
    cleanup();
    
    log('\n════════════════════════════════════════════════════════════', 'cyan');
    log('Test Summary', 'cyan');
    log('════════════════════════════════════════════════════════════', 'cyan');
    log(`Total Tests: ${testsPassed + testsFailed}`, 'blue');
    log(`Passed: ${testsPassed}`, 'green');
    log(`Failed: ${testsFailed}`, 'red');
    log('════════════════════════════════════════════════════════════\n', 'cyan');
    
    process.exit(1);
  }
}

// Run the test
if (require.main === module) {
  testRestartPersistence();
}

module.exports = { testRestartPersistence };
