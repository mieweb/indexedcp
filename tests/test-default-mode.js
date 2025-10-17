#!/usr/bin/env node

// Quick test to verify the default path mode is 'ignore'
const { IndexedCPServer } = require('../lib/server');

console.log('Testing default path mode...\n');

// Create server without specifying pathMode
const server = new IndexedCPServer({
  port: 3999,
  outputDir: './test-default-mode'
});

if (server.pathMode === 'ignore') {
  console.log('✅ PASS: Default path mode is "ignore"');
  console.log(`   Server pathMode: ${server.pathMode}`);
  process.exit(0);
} else {
  console.error('❌ FAIL: Default path mode is not "ignore"');
  console.error(`   Expected: ignore`);
  console.error(`   Got: ${server.pathMode}`);
  process.exit(1);
}
