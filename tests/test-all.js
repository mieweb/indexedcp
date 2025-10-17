#!/usr/bin/env node
// test-all.js
// Comprehensive test runner that executes all test suites

const { spawn } = require('child_process');
const path = require('path');

const colors = {
  reset: '\x1b[0m',
  green: '\x1b[32m',
  red: '\x1b[31m',
  yellow: '\x1b[33m',
  cyan: '\x1b[36m',
  bold: '\x1b[1m',
};

function log(msg, color = 'reset') {
  console.log(`${colors[color]}${msg}${colors.reset}`);
}

function runTest(script, name) {
  return new Promise((resolve) => {
    log(`\n${'═'.repeat(70)}`, 'cyan');
    log(`Running: ${name}`, 'bold');
    log('═'.repeat(70) + '\n', 'cyan');

    const proc = spawn('node', [path.join(__dirname, script)], {
      cwd: path.dirname(__dirname),
      stdio: 'inherit'
    });

    proc.on('close', (code) => {
      resolve({ name, script, exitCode: code, passed: code === 0 });
    });

    proc.on('error', (err) => {
      log(`Error running ${name}: ${err.message}`, 'red');
      resolve({ name, script, exitCode: 1, passed: false, error: err.message });
    });
  });
}

async function runAllTests() {
  log('\n' + '═'.repeat(70), 'yellow');
  log('IndexedCP - Complete Test Suite', 'yellow');
  log('═'.repeat(70) + '\n', 'yellow');

  const tests = [
    { script: './test-all-examples.js', name: 'Functional Tests' },
    { script: './security-test.js', name: 'Security Tests' },
    { script: './test-restart-persistence.js', name: 'Restart Persistence Tests' },
    { script: './test-encryption.js', name: 'Encryption Tests' },
    { script: './test-cli-ls.js', name: 'CLI ls Command Tests' }
  ];

  const results = [];

  for (const test of tests) {
    const result = await runTest(test.script, test.name);
    results.push(result);
  }

  // Print summary
  log('\n' + '═'.repeat(70), 'yellow');
  log('Complete Test Summary', 'yellow');
  log('═'.repeat(70), 'yellow');

  let totalPassed = 0;
  let totalFailed = 0;

  for (const result of results) {
    const status = result.passed ? '✓ PASS' : '✗ FAIL';
    const color = result.passed ? 'green' : 'red';
    log(`${result.name.padEnd(40)} ${status}`, color);
    
    if (result.passed) {
      totalPassed++;
    } else {
      totalFailed++;
      if (result.error) {
        log(`  Error: ${result.error}`, 'red');
      }
    }
  }

  log('\n' + '─'.repeat(70), 'cyan');
  log(`Total Test Suites: ${results.length}`, 'cyan');
  log(`Passed: ${totalPassed}`, 'green');
  log(`Failed: ${totalFailed}`, totalFailed > 0 ? 'red' : 'green');
  log('═'.repeat(70) + '\n', 'yellow');

  if (totalFailed > 0) {
    log('Some tests failed. Review the output above for details.', 'red');
    process.exit(1);
  } else {
    log('All tests passed! 🎉', 'green');
    process.exit(0);
  }
}

// Handle errors
process.on('unhandledRejection', (error) => {
  log('Unhandled error: ' + error.message, 'red');
  process.exit(1);
});

// Run all tests
if (require.main === module) {
  runAllTests().catch((error) => {
    log('Test runner error: ' + error.message, 'red');
    process.exit(1);
  });
}

module.exports = { runAllTests };
