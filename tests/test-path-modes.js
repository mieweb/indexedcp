#!/usr/bin/env node

// Set test mode to use fake-indexeddb
process.env.INDEXEDCP_TEST_MODE = 'true';

// Test different path handling modes
const { IndexedCPServer } = require('../lib/server');
const { spawn } = require('child_process');
const http = require('http');
const fs = require('fs');
const path = require('path');

// Color codes for output
const COLORS = {
  reset: '\x1b[0m',
  bright: '\x1b[1m',
  red: '\x1b[31m',
  green: '\x1b[32m',
  yellow: '\x1b[33m',
  blue: '\x1b[34m',
  cyan: '\x1b[36m'
};

const TEST_PORT = 3400;
const API_KEY = 'test-api-key-path-modes';

// Helper to upload a file chunk
async function uploadFile(port, filename, content, apiKey) {
  return new Promise((resolve, reject) => {
    const data = Buffer.from(content);
    const options = {
      hostname: 'localhost',
      port: port,
      path: '/upload',
      method: 'POST',
      headers: {
        'Content-Type': 'application/octet-stream',
        'Content-Length': data.length,
        'X-File-Name': filename,
        'X-Chunk-Index': 0,
        'Authorization': `Bearer ${apiKey}`
      }
    };

    const req = http.request(options, (res) => {
      let body = '';
      res.on('data', (chunk) => body += chunk);
      res.on('end', () => {
        try {
          const result = JSON.parse(body);
          resolve({ statusCode: res.statusCode, body: result });
        } catch (e) {
          resolve({ statusCode: res.statusCode, body: body });
        }
      });
    });

    req.on('error', reject);
    req.write(data);
    req.end();
  });
}

// Test suite
const tests = [
  {
    name: 'Mode: sanitize - Simple filename',
    mode: 'sanitize',
    filename: 'test.txt',
    content: 'test content',
    shouldSucceed: true,
    checkFile: 'test.txt'
  },
  {
    name: 'Mode: sanitize - Path separator rejected',
    mode: 'sanitize',
    filename: 'dir/test.txt',
    content: 'test content',
    shouldSucceed: false
  },
  {
    name: 'Mode: sanitize - Prevent overwrite (different files)',
    mode: 'sanitize',
    filename: 'duplicate.txt',
    content: 'first upload',
    shouldSucceed: true,
    secondUpload: {
      filename: 'duplicate2.txt', // Different file
      content: 'second upload',
      shouldSucceed: true
    }
  },
  {
    name: 'Mode: allow-paths - Subdirectory allowed',
    mode: 'allow-paths',
    filename: 'subdir/test.txt',
    content: 'test content',
    shouldSucceed: true,
    checkFile: 'subdir/test.txt'
  },
  {
    name: 'Mode: allow-paths - Deep nested path',
    mode: 'allow-paths',
    filename: 'a/b/c/test.txt',
    content: 'test content',
    shouldSucceed: true,
    checkFile: 'a/b/c/test.txt'
  },
  {
    name: 'Mode: allow-paths - Traversal rejected',
    mode: 'allow-paths',
    filename: '../etc/passwd',
    content: 'malicious',
    shouldSucceed: false
  },
  {
    name: 'Mode: allow-paths - Absolute path rejected',
    mode: 'allow-paths',
    filename: '/etc/passwd',
    content: 'malicious',
    shouldSucceed: false
  },
  {
    name: 'Mode: ignore - Client filename ignored',
    mode: 'ignore',
    filename: 'original.txt',
    content: 'test content',
    shouldSucceed: true,
    checkGenerated: true // Should generate unique name
  },
  {
    name: 'Mode: ignore - Path ignored',
    mode: 'ignore',
    filename: 'dir/original.txt',
    content: 'test content',
    shouldSucceed: true,
    checkGenerated: true
  }
];

let passed = 0;
let failed = 0;

async function runTests() {
  console.log(`${COLORS.cyan}${COLORS.bright}════════════════════════════════════════════════════════════`);
  console.log(`IndexedCP - Path Mode Tests`);
  console.log(`═══════════════════════════════════════════════════════════=${COLORS.reset}\n`);

  for (const test of tests) {
    const testDir = path.join(__dirname, `test-path-mode-${test.mode}-${Date.now()}`);
    let server = null;
    
    try {
      // Create test directory
      if (!fs.existsSync(testDir)) {
        fs.mkdirSync(testDir, { recursive: true });
      }

      // Start server with specific mode
      server = new IndexedCPServer({
        port: TEST_PORT,
        outputDir: testDir,
        apiKey: API_KEY,
        pathMode: test.mode
      });
      
      await new Promise((resolve, reject) => {
        server.listen(TEST_PORT, (err) => {
          if (err) reject(err);
          else resolve();
        });
      });

      // Wait for server to be ready
      await new Promise(resolve => setTimeout(resolve, 200));

      // Upload file
      const result = await uploadFile(TEST_PORT, test.filename, test.content, API_KEY);
      
      const success = test.shouldSucceed ? (result.statusCode === 200) : (result.statusCode !== 200);
      
      if (success) {
        // Additional checks for successful uploads
        if (test.shouldSucceed) {
          if (test.checkFile) {
            const filePath = path.join(testDir, test.checkFile);
            if (!fs.existsSync(filePath)) {
              throw new Error(`Expected file not found: ${test.checkFile}`);
            }
            const content = fs.readFileSync(filePath, 'utf8');
            if (content !== test.content) {
              throw new Error(`Content mismatch`);
            }
          }
          
          if (test.checkGenerated && result.body.actualFilename) {
            if (result.body.actualFilename === test.filename) {
              throw new Error(`Expected generated filename, got original: ${result.body.actualFilename}`);
            }
            // Verify format: <timestamp>_<random>_<full-path-with-underscores>.<ext>
            // Path separators (/ and \) should be replaced with single underscore
            // Other special chars should be replaced with dash
            const expectedPath = test.filename.replace(/^\.\//, '').replace(/^\.\\/, '').replace(/[/\\]+/g, '_');
            const expectedBase = expectedPath.replace(/\.[^.]*$/, ''); // Remove extension
            
            if (!result.body.actualFilename.includes(expectedBase)) {
              throw new Error(`Generated filename should contain full path: ${expectedBase}, got: ${result.body.actualFilename}`);
            }
            
            // Check file exists with generated name
            const filePath = path.join(testDir, result.body.actualFilename);
            if (!fs.existsSync(filePath)) {
              throw new Error(`Generated file not found: ${result.body.actualFilename}`);
            }
          }
        }
        
        // Handle second upload if specified
        if (test.secondUpload) {
          const result2 = await uploadFile(TEST_PORT, test.secondUpload.filename, test.secondUpload.content, API_KEY);
          const success2 = test.secondUpload.shouldSucceed ? (result2.statusCode === 200) : (result2.statusCode !== 200);
          
          if (!success2) {
            throw new Error(`Second upload failed unexpectedly`);
          }
          
          if (test.secondUpload.checkDifferent) {
            // Verify two different files exist
            const files = fs.readdirSync(testDir);
            if (files.length < 2) {
              throw new Error(`Expected 2 files (overwrite prevention failed), found ${files.length}`);
            }
          }
        }
        
        console.log(`${COLORS.green}✓ PASS${COLORS.reset} - ${test.name}`);
        passed++;
      } else {
        console.log(`${COLORS.red}✗ FAIL${COLORS.reset} - ${test.name}`);
        console.log(`  Expected: ${test.shouldSucceed ? 'success' : 'failure'}, Got: ${result.statusCode}`);
        failed++;
      }

      // Cleanup
      if (server) {
        server.close();
        await new Promise(resolve => setTimeout(resolve, 200));
      }
      if (fs.existsSync(testDir)) {
        fs.rmSync(testDir, { recursive: true, force: true });
      }
      
      // Wait between tests
      await new Promise(resolve => setTimeout(resolve, 200));
      
    } catch (error) {
      console.log(`${COLORS.red}✗ FAIL${COLORS.reset} - ${test.name}`);
      console.log(`  Error: ${error.message}`);
      failed++;
      
      // Cleanup on error
      if (server) {
        server.close();
        await new Promise(resolve => setTimeout(resolve, 200));
      }
      if (fs.existsSync(testDir)) {
        fs.rmSync(testDir, { recursive: true, force: true });
      }
    }
  }

  // Summary
  console.log(`\n${COLORS.cyan}${COLORS.bright}════════════════════════════════════════════════════════════${COLORS.reset}`);
  console.log(`Total Tests: ${tests.length}`);
  console.log(`${COLORS.green}Passed: ${passed}${COLORS.reset}`);
  console.log(`${COLORS.red}Failed: ${failed}${COLORS.reset}`);
  console.log(`${COLORS.cyan}${COLORS.bright}═══════════════════════════════════════════════════════════=${COLORS.reset}`);

  if (failed > 0) {
    process.exit(1);
  }
}

runTests().catch(error => {
  console.error('Test runner error:', error);
  process.exit(1);
});
