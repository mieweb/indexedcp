#!/usr/bin/env node
// security-test.js
// Test path traversal and other security vulnerabilities

const { IndexCPServer } = require('../lib/server');
const http = require('http');
const fs = require('fs');
const path = require('path');

const TEST_DIR = './test-security-uploads';
const API_KEY = 'test-security-key';
const PORT = 3335;

// Color output
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

// Clean up and setup
function setup() {
  if (fs.existsSync(TEST_DIR)) {
    fs.rmSync(TEST_DIR, { recursive: true });
  }
  fs.mkdirSync(TEST_DIR, { recursive: true });
}

function cleanup() {
  if (fs.existsSync(TEST_DIR)) {
    fs.rmSync(TEST_DIR, { recursive: true });
  }
}

// Make a test upload request
async function testUpload(filename, shouldSucceed = true) {
  return new Promise((resolve) => {
    const data = 'malicious content';
    const options = {
      hostname: 'localhost',
      port: PORT,
      path: '/upload',
      method: 'POST',
      headers: {
        'Authorization': `Bearer ${API_KEY}`,
        'X-File-Name': filename,
        'X-Chunk-Index': '0',
        'Content-Length': data.length
      }
    };

    const req = http.request(options, (res) => {
      let body = '';
      res.on('data', chunk => body += chunk);
      res.on('end', () => {
        resolve({
          statusCode: res.statusCode,
          body: body,
          success: res.statusCode === 200 || res.statusCode === 201
        });
      });
    });

    req.on('error', (e) => {
      resolve({ statusCode: 0, error: e.message, success: false });
    });

    req.write(data);
    req.end();
  });
}

async function runSecurityTests() {
  log('\n' + '═'.repeat(60), 'yellow');
  log('IndexedCP - Security Tests', 'yellow');
  log('═'.repeat(60) + '\n', 'yellow');

  setup();

  const server = new IndexCPServer({
    port: PORT,
    outputDir: TEST_DIR,
    apiKey: API_KEY,
    pathMode: 'sanitize' // Use sanitize mode for security tests
  });

  await new Promise(resolve => {
    server.listen(PORT, resolve);
  });

  const tests = [
    // Valid filenames
    { name: 'Valid filename', filename: 'test.txt', shouldBlock: false },
    { name: 'Valid filename with extension', filename: 'document.pdf', shouldBlock: false },
    
    // Path traversal attempts
    { name: 'Parent directory traversal (..)', filename: '../etc/passwd', shouldBlock: true },
    { name: 'Multiple parent traversal', filename: '../../etc/passwd', shouldBlock: true },
    { name: 'Parent in middle', filename: 'foo/../../../etc/passwd', shouldBlock: true },
    { name: 'Encoded parent directory', filename: '..%2F..%2Fetc%2Fpasswd', shouldBlock: true },
    
    // Absolute paths
    { name: 'Absolute Unix path', filename: '/etc/passwd', shouldBlock: true },
    { name: 'Absolute Windows path', filename: 'C:\\Windows\\System32\\config\\sam', shouldBlock: true },
    { name: 'Windows UNC path', filename: '\\\\server\\share\\file.txt', shouldBlock: true },
    
    // Subdirectory attempts (should be blocked - only basename allowed)
    { name: 'Subdirectory', filename: 'subdir/file.txt', shouldBlock: true },
    { name: 'Deep subdirectory', filename: 'a/b/c/file.txt', shouldBlock: true },
    
    // Empty/invalid names
    { name: 'Empty filename (defaults to safe name)', filename: '', shouldBlock: false }, // Falls back to default
    { name: 'Just dot', filename: '.', shouldBlock: true },
    { name: 'Just double dot', filename: '..', shouldBlock: true },
    { name: 'Just slash', filename: '/', shouldBlock: true },
    
    // Special characters
    { name: 'Filename with spaces', filename: 'my file.txt', shouldBlock: false },
  ];

  let passed = 0;
  let failed = 0;

  for (const test of tests) {
    process.stdout.write(`Testing: ${test.name.padEnd(40)} `);
    
    const result = await testUpload(test.filename, !test.shouldBlock);
    
    const wasBlocked = result.statusCode === 400 || result.statusCode === 403;
    const testPassed = test.shouldBlock ? wasBlocked : result.success;
    
    if (testPassed) {
      log('✓ PASS', 'green');
      passed++;
    } else {
      log('✗ FAIL', 'red');
      log(`  Expected: ${test.shouldBlock ? 'blocked' : 'allowed'}`, 'red');
      log(`  Got: ${result.statusCode} ${wasBlocked ? 'blocked' : 'allowed'}`, 'red');
      failed++;
    }
  }

  // Check that no files were written outside TEST_DIR
  log('\nChecking filesystem security...', 'cyan');
  const filesInTestDir = fs.readdirSync(TEST_DIR);
  const expectedFiles = ['test.txt', 'document.pdf', 'my file.txt', 'uploaded_file.txt'];
  const unexpectedFiles = filesInTestDir.filter(f => !expectedFiles.includes(f));
  
  if (unexpectedFiles.length === 0) {
    log('✓ Only expected files in upload directory', 'green');
    passed++;
  } else {
    log('✗ Unexpected files in upload directory:', 'red');
    log(`  Unexpected: ${unexpectedFiles.join(', ')}`, 'red');
    failed++;
  }

  // Verify no files in parent directory or system directories
  const parentDir = path.resolve(TEST_DIR, '..');
  const parentFiles = fs.readdirSync(parentDir);
  const suspiciousFiles = parentFiles.filter(f => 
    f.includes('passwd') || f.includes('malicious') || f.includes('etc')
  );
  
  if (suspiciousFiles.length === 0) {
    log('✓ No files written to parent directory', 'green');
    passed++;
  } else {
    log('✗ CRITICAL: Files written outside upload directory!', 'red');
    log(`  Suspicious files: ${suspiciousFiles.join(', ')}`, 'red');
    failed++;
  }

  server.close();
  cleanup();

  log('\n' + '═'.repeat(60), 'yellow');
  log('Security Test Summary', 'yellow');
  log('═'.repeat(60), 'yellow');
  log(`Total Tests: ${passed + failed}`, 'cyan');
  log(`Passed: ${passed}`, 'green');
  log(`Failed: ${failed}`, failed > 0 ? 'red' : 'green');
  log('═'.repeat(60) + '\n', 'yellow');

  process.exit(failed > 0 ? 1 : 0);
}

runSecurityTests().catch(err => {
  log('Test error: ' + err.message, 'red');
  cleanup();
  process.exit(1);
});
