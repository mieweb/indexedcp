#!/usr/bin/env node

// Test full path preservation in ignore mode
const { IndexCPServer } = require('../lib/server');
const http = require('http');

const PORT = 3998;
const API_KEY = 'test-path-preservation';

// Color codes for output
const COLORS = {
  reset: '\x1b[0m',
  bright: '\x1b[1m',
  cyan: '\x1b[36m',
  green: '\x1b[32m',
  red: '\x1b[31m'
};

console.log(`${COLORS.cyan}${COLORS.bright}════════════════════════════════════════════════════════════`);
console.log(`IndexedCP - Path Preservation Tests (ignore mode)`);
console.log(`Testing: Path separators → '_', Special chars → '-'`);
console.log(`═══════════════════════════════════════════════════════════=${COLORS.reset}\n`);

const tests = [
  {
    name: 'Simple filename (no path)',
    filename: 'file.txt',
    expectedPattern: /^\d+_[a-f0-9]+_file\.txt$/
  },
  {
    name: 'Single directory path',
    filename: 'reports/data.csv',
    expectedPattern: /^\d+_[a-f0-9]+_reports_data\.csv$/
  },
  {
    name: 'Deep nested path',
    filename: 'reports/2024/Q1/sales.pdf',
    expectedPattern: /^\d+_[a-f0-9]+_reports_2024_Q1_sales\.pdf$/
  },
  {
    name: 'Windows-style path',
    filename: 'docs\\windows\\path.docx',
    expectedPattern: /^\d+_[a-f0-9]+_docs_windows_path\.docx$/
  },
  {
    name: 'Filename with spaces',
    filename: 'my document.txt',
    expectedPattern: /^\d+_[a-f0-9]+_my-document\.txt$/
  },
  {
    name: 'Path with special characters',
    filename: 'folder/file (copy) [2].txt',
    expectedPattern: /^\d+_[a-f0-9]+_folder_file--copy---2-\.txt$/
  }
];

async function uploadFile(filename) {
  return new Promise((resolve, reject) => {
    const data = Buffer.from('test content');
    const options = {
      hostname: 'localhost',
      port: PORT,
      path: '/upload',
      method: 'POST',
      headers: {
        'Content-Type': 'application/octet-stream',
        'Content-Length': data.length,
        'X-File-Name': filename,
        'X-Chunk-Index': 0,
        'Authorization': `Bearer ${API_KEY}`
      }
    };

    const req = http.request(options, (res) => {
      let body = '';
      res.on('data', (chunk) => body += chunk);
      res.on('end', () => {
        try {
          const result = JSON.parse(body);
          resolve(result.actualFilename);
        } catch (e) {
          reject(e);
        }
      });
    });

    req.on('error', reject);
    req.write(data);
    req.end();
  });
}

async function runTests() {
  const server = new IndexCPServer({
    port: PORT,
    outputDir: './test-path-preservation',
    apiKey: API_KEY
    // pathMode defaults to 'ignore'
  });

  await new Promise((resolve) => {
    server.listen(PORT, resolve);
  });

  let passed = 0;
  let failed = 0;

  for (const test of tests) {
    try {
      const actualFilename = await uploadFile(test.filename);
      
      // Check if filename matches the expected pattern
      if (test.expectedPattern.test(actualFilename)) {
        console.log(`${COLORS.green}✓ PASS${COLORS.reset}: ${test.name}`);
        console.log(`  ${test.filename} → ${actualFilename}\n`);
        passed++;
      } else {
        console.log(`${COLORS.red}✗ FAIL${COLORS.reset}: ${test.name}`);
        console.log(`  Expected pattern: ${test.expectedPattern}`);
        console.log(`  Got: ${actualFilename}\n`);
        failed++;
      }
    } catch (error) {
      console.log(`${COLORS.red}✗ ERROR${COLORS.reset}: ${test.name}`);
      console.log(`  ${error.message}\n`);
      failed++;
    }
  }

  server.close();

  // Cleanup
  const fs = require('fs');
  if (fs.existsSync('./test-path-preservation')) {
    fs.rmSync('./test-path-preservation', { recursive: true, force: true });
  }

  console.log(`${COLORS.cyan}${'─'.repeat(60)}`);
  console.log(`Total: ${tests.length}, Passed: ${passed}, Failed: ${failed}`);
  console.log(`${'─'.repeat(60)}${COLORS.reset}`);

  process.exit(failed > 0 ? 1 : 0);
}

runTests().catch(error => {
  console.error('Test runner error:', error);
  process.exit(1);
});
