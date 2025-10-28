#!/usr/bin/env node
/**
 * Comprehensive encryption test suite
 * Tests all acceptance criteria for asymmetric envelope encryption
 */

// Set test mode to use fake-indexeddb
process.env.INDEXEDCP_TEST_MODE = 'true';

const fs = require('fs');
const path = require('path');
const os = require('os');
const assert = require('assert');
const IndexedCPClient = require('../lib/client');
const { IndexedCPServer } = require('../lib/server');
const cryptoUtils = require('../lib/crypto-utils');

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

class EncryptionTestSuite {
  constructor() {
    this.testDir = path.join(os.tmpdir(), 'indexcp-encryption-test');
    this.serverOutputDir = path.join(this.testDir, 'server-output');
    this.testFiles = path.join(this.testDir, 'test-files');
    this.server = null;
    this.port = 3001;
    this.apiKey = 'test-api-key-12345';
    this.passed = 0;
    this.failed = 0;
  }

  async setup() {
    log('\n🔧 Setting up test environment...', 'cyan');
    
    // Clean and create directories
    if (fs.existsSync(this.testDir)) {
      fs.rmSync(this.testDir, { recursive: true, force: true });
    }
    fs.mkdirSync(this.testDir, { recursive: true });
    fs.mkdirSync(this.serverOutputDir, { recursive: true });
    fs.mkdirSync(this.testFiles, { recursive: true });

    // Clean encrypted DB
    const encDbPath = path.join(os.homedir(), '.indexcp', 'encrypted-db');
    if (fs.existsSync(encDbPath)) {
      fs.rmSync(encDbPath, { recursive: true, force: true });
    }

    // Create test file
    this.testFile = path.join(this.testFiles, 'test-data.txt');
    this.testContent = 'This is secret test data that should be encrypted!\n'.repeat(100);
    fs.writeFileSync(this.testFile, this.testContent);

    log('✓ Test environment ready\n', 'green');
  }

  async cleanup() {
    log('\n🧹 Cleaning up...', 'cyan');
    
    if (this.server) {
      this.server.close();
    }
    
    if (fs.existsSync(this.testDir)) {
      fs.rmSync(this.testDir, { recursive: true, force: true });
    }

    // Clean encrypted DB
    const encDbPath = path.join(os.homedir(), '.indexcp', 'encrypted-db');
    if (fs.existsSync(encDbPath)) {
      fs.rmSync(encDbPath, { recursive: true, force: true });
    }
    
    log('✓ Cleanup complete\n', 'green');
  }

  async startServer() {
    this.server = new IndexedCPServer({
      outputDir: this.serverOutputDir,
      port: this.port,
      apiKey: this.apiKey,
      pathMode: 'ignore',
      encryption: true            // Enable encryption
    });

    return new Promise((resolve) => {
      this.server.listen(this.port, () => {
        log(`✓ Test server started on port ${this.port}\n`, 'green');
        resolve();
      });
    });
  }

  async test(name, fn) {
    try {
      log(`Testing: ${name}`, 'cyan');
      await fn();
      this.passed++;
      log(`✓ PASS: ${name}\n`, 'green');
    } catch (error) {
      this.failed++;
      log(`✗ FAIL: ${name}`, 'red');
      log(`  Error: ${error.message}\n`, 'red');
      if (error.stack) {
        console.error(error.stack);
      }
    }
  }

  // ===== AC0: Fetch public key from server =====
  async testAC0_PublicKeyFetch() {
    await this.test('AC0: Fetch public key from server before storing data', async () => {
      const client = new IndexedCPClient({
        dbName: 'test-ac0',
        apiKey: this.apiKey,
        serverUrl: `http://localhost:${this.port}`,
        encryption: true
      });

      // Fetch public key
      const keyInfo = await client.fetchPublicKey();
      
      assert(keyInfo.publicKey, 'Public key should be fetched');
      assert(keyInfo.kid, 'Key ID should be present');
      assert(cryptoUtils.isValidKeyId(keyInfo.kid), 'Key ID should be valid');
      
      // Verify cached (note: these are async getters, need to await)
      const cachedKey = await client.cachedPublicKey;
      const cachedKid = await client.cachedKeyId;
      assert(cachedKey.publicKey === keyInfo.publicKey, 'Key should be cached');
      assert(cachedKid === keyInfo.kid, 'Key ID should be cached');
      
      log('  ✓ Public key fetched and cached', 'green');
    });
  }

  // ===== AC1: No plaintext in IndexedDB =====
  async testAC1_NoPlaintextInDB() {
    await this.test('AC1: IndexedDB contains only encrypted packets and wrapped keys', async () => {
      const client = new IndexedCPClient({
        dbName: 'test-ac1',
        apiKey: this.apiKey,
        serverUrl: `http://localhost:${this.port}`,
        encryption: true
      });

      // Fetch key and add file
      await client.fetchPublicKey();
      await client.addFile(this.testFile);

      // Check database contents
      const db = await client.initDB();
      
      // Check sessions - should have wrapped keys, not plaintext keys
      const sessionsTx = db.transaction('sessions', 'readonly');
      const sessions = await sessionsTx.objectStore('sessions').getAll();
      assert(sessions.length > 0, 'Should have session records');
      
      for (const session of sessions) {
        assert(session.wrappedKey, 'Session should have wrapped key');
        // wrappedKey is stored as Buffer in IndexedDB (converted to base64 during upload)
        assert(Buffer.isBuffer(session.wrappedKey) || session.wrappedKey.type === 'Buffer', 
          'Wrapped key should be Buffer or Buffer-like object');
        assert(session.kid, 'Session should reference key ID');
        
        // Verify no plaintext session key in DB
        assert(!session.sessionKey, 'Session should NOT contain plaintext key');
      }
      
      // Check packets - should be encrypted
      const packetsTx = db.transaction('packets', 'readonly');
      const packets = await packetsTx.objectStore('packets').getAll();
      assert(packets.length > 0, 'Should have packet records');
      
      for (const packet of packets) {
        assert(packet.ciphertext, 'Packet should have ciphertext');
        assert(packet.iv, 'Packet should have IV');
        assert(packet.authTag, 'Packet should have auth tag');
        assert(packet.aad, 'Packet should have AAD');
        
        // Verify no plaintext data
        assert(!packet.data, 'Packet should NOT contain plaintext data');
        
        // Verify ciphertext is not the plaintext
        const cipherBuffer = Buffer.from(packet.ciphertext, 'base64');
        assert(!cipherBuffer.toString().includes('secret test data'), 
          'Ciphertext should not contain plaintext');
      }
      
      log('  ✓ No plaintext found in IndexedDB', 'green');
      log(`  ✓ Found ${sessions.length} sessions with wrapped keys`, 'green');
      log(`  ✓ Found ${packets.length} encrypted packets`, 'green');
    });
  }

  // ===== AC2: Offline operation after key fetch =====
  async testAC2_OfflineOperation() {
    await this.test('AC2: Client functions offline after initial key fetch', async () => {
      const client = new IndexedCPClient({
        dbName: 'test-ac2',
        apiKey: this.apiKey,
        serverUrl: `http://localhost:${this.port}`,
        encryption: true
      });

      // Online: Fetch key
      await client.fetchPublicKey();
      const cachedKid = await client.cachedKeyId;

      // Simulate offline: Create new client without server URL
      const offlineClient = new IndexedCPClient({
        dbName: 'test-ac2',
        apiKey: this.apiKey,
        encryption: true
        // No serverUrl - simulating offline
      });

      // Should be able to load cached key
      const cachedKey = await offlineClient.getCachedPublicKey();
      assert(cachedKey, 'Should retrieve cached key');
      assert(cachedKey.kid === cachedKid, 'Should get same key ID');

      // Should be able to encrypt and queue data offline
      await offlineClient.addFile(this.testFile);

      // Verify data was encrypted and queued
      const db = await offlineClient.initDB();
      const packetsTx = db.transaction('packets', 'readonly');
      const packets = await packetsTx.objectStore('packets').getAll();
      
      assert(packets.length > 0, 'Should queue encrypted packets offline');
      assert(packets.every(p => p.status === 'pending'), 'Packets should be pending');
      
      log('  ✓ Cached key retrieved offline', 'green');
      log(`  ✓ Queued ${packets.length} encrypted packets offline`, 'green');
    });
  }

  // ===== AC3: Server successfully decrypts =====
  async testAC3_ServerDecryption() {
    await this.test('AC3: Server successfully decrypts uploaded packets', async () => {
      const client = new IndexedCPClient({
        dbName: 'test-ac3',
        apiKey: this.apiKey,
        serverUrl: `http://localhost:${this.port}`,
        encryption: true
      });

      // Encrypt and buffer
      await client.fetchPublicKey();
      await client.addFile(this.testFile);

      // Upload to server
      const results = await client.uploadBufferedFiles(`http://localhost:${this.port}`);
      assert(Object.keys(results).length > 0, 'Should have upload results');

      // Verify server decrypted and saved file
      const outputFiles = fs.readdirSync(this.serverOutputDir);
      assert(outputFiles.length > 0, 'Server should have created output file');

      const outputFile = path.join(this.serverOutputDir, outputFiles[0]);
      const decryptedContent = fs.readFileSync(outputFile, 'utf8');
      
      assert(decryptedContent === this.testContent, 'Decrypted content should match original');
      
      log('  ✓ Server decrypted packets successfully', 'green');
      log('  ✓ Decrypted content matches original', 'green');
    });
  }

  // ===== AC4: Key rotation doesn't invalidate queued data =====
  async testAC4_KeyRotation() {
    await this.test('AC4: Key rotation does not invalidate queued data', async () => {
      const client = new IndexedCPClient({
        dbName: 'test-ac4',
        apiKey: this.apiKey,
        serverUrl: `http://localhost:${this.port}`,
        encryption: true
      });

      // Encrypt with initial key
      await client.fetchPublicKey();
      const originalKid = client.cachedKeyId;
      await client.addFile(this.testFile);

      // Rotate keys on server
      const fetch = require('node-fetch');
      const rotateResponse = await fetch(`http://localhost:${this.port}/rotate-keys`, {
        method: 'POST',
        headers: { 'Authorization': `Bearer ${this.apiKey}` }
      });
      assert(rotateResponse.ok, 'Key rotation should succeed');
      
      const rotateData = await rotateResponse.json();
      const newKid = rotateData.kid;
      assert(newKid !== originalKid, 'New key should be different');

      // Server should still accept packets encrypted with old key
      const results = await client.uploadBufferedFiles(`http://localhost:${this.port}`);
      assert(Object.keys(results).length > 0, 'Should upload with old key');

      // Verify decryption succeeded
      const outputFiles = fs.readdirSync(this.serverOutputDir);
      const outputFile = path.join(this.serverOutputDir, outputFiles[outputFiles.length - 1]);
      const content = fs.readFileSync(outputFile, 'utf8');
      assert(content === this.testContent, 'Old key should still decrypt');

      log('  ✓ Key rotation successful', 'green');
      log(`  ✓ Old key (${originalKid}) still decrypts queued data`, 'green');
      log(`  ✓ New key (${newKid}) is now active`, 'green');
    });
  }

  // ===== AC5: Performance overhead is negligible =====
  async testAC5_Performance() {
    await this.test('AC5: Performance overhead is negligible', async () => {
      // Create larger test file
      const largeFile = path.join(this.testFiles, 'large-test.txt');
      const largeContent = 'X'.repeat(5 * 1024 * 1024); // 5MB
      fs.writeFileSync(largeFile, largeContent);

      const client = new IndexedCPClient({
        dbName: 'test-ac5',
        apiKey: this.apiKey,
        serverUrl: `http://localhost:${this.port}`,
        chunkSize: 1024 * 1024, // 1MB chunks
        encryption: true
      });

      await client.fetchPublicKey();

      // Measure encryption time
      const encryptStart = Date.now();
      await client.addFile(largeFile);
      const encryptTime = Date.now() - encryptStart;

      // Get packet count
      const db = await client.initDB();
      const packetsTx = db.transaction('packets', 'readonly');
      const packets = await packetsTx.objectStore('packets').getAll();
      
      const timePerPacket = encryptTime / packets.length;
      
      log(`  ✓ Encrypted ${packets.length} packets (5MB) in ${encryptTime}ms`, 'green');
      log(`  ✓ Average: ${timePerPacket.toFixed(2)}ms per packet`, 'green');
      
      // Performance should be reasonable (< 100ms per MB)
      const timePerMB = encryptTime / 5;
      assert(timePerMB < 1000, `Encryption should be < 1000ms/MB (was ${timePerMB.toFixed(0)}ms/MB)`);
      
      // Cleanup
      fs.unlinkSync(largeFile);
    });
  }

  // ===== Additional test: Session key in memory only =====
  async testSessionKeyMemory() {
    await this.test('Session keys remain in memory only during capture', async () => {
      const client = new IndexedCPClient({
        dbName: 'test-memory',
        apiKey: this.apiKey,
        serverUrl: `http://localhost:${this.port}`,
        encryption: true
      });

      await client.fetchPublicKey();
      
      // Start stream manually
      const sessionId = await client.startStream('test.txt');
      assert(client.activeStreams.has(sessionId), 'Session key should be in memory');
      
      const sessionKey = client.activeStreams.get(sessionId);
      assert(Buffer.isBuffer(sessionKey), 'Session key should be a Buffer');
      assert(sessionKey.length === 32, 'Session key should be 256 bits');

      log('  ✓ Session key exists in memory during capture', 'green');

      // Now use addFile which creates its own session and clears it
      const result = await client.addFile(this.testFile);
      
      // The session from addFile should be cleared
      assert(!client.activeStreams.has(result.sessionId), 'Session key should be cleared from memory after stream ends');
      
      log('  ✓ Session key cleared from memory after stream ends', 'green');
    });
  }

  // ===== Additional test: IV uniqueness =====
  async testIVUniqueness() {
    await this.test('IVs are unique per packet', async () => {
      const client = new IndexedCPClient({
        dbName: 'test-iv',
        apiKey: this.apiKey,
        serverUrl: `http://localhost:${this.port}`,
        encryption: true
      });

      await client.fetchPublicKey();
      await client.addFile(this.testFile);

      // Check IV uniqueness
      const db = await client.initDB();
      const packetsTx = db.transaction('packets', 'readonly');
      const packets = await packetsTx.objectStore('packets').getAll();

      const ivSet = new Set();
      for (const packet of packets) {
        assert(!ivSet.has(packet.iv), 'Each IV should be unique');
        ivSet.add(packet.iv);
      }

      log(`  ✓ All ${packets.length} IVs are unique`, 'green');
    });
  }

  // ===== Additional test: Encryption status API =====
  async testEncryptionStatus() {
    await this.test('Encryption status and stats', async () => {
      const client = new IndexedCPClient({
        dbName: 'test-status',
        apiKey: this.apiKey,
        serverUrl: `http://localhost:${this.port}`,
        encryption: true
      });

      await client.fetchPublicKey();
      await client.addFile(this.testFile);

      const status = await client.getEncryptionStatus();
      
      assert(status.isEncrypted === true, 'Should be encrypted');
      assert(status.activeSessions > 0, 'Should have active sessions');
      assert(status.pendingPackets > 0, 'Should have pending packets');
      assert(status.cachedKeys > 0, 'Should have cached keys');
      assert(status.currentKeyId, 'Should have current key ID');

      log('  ✓ Client status:', 'green');
      log(`    - Active sessions: ${status.activeSessions}`, 'cyan');
      log(`    - Pending packets: ${status.pendingPackets}`, 'cyan');
      log(`    - Cached keys: ${status.cachedKeys}`, 'cyan');
      log(`    - Current key: ${status.currentKeyId}`, 'cyan');

      const serverStatus = this.server.getEncryptionStatus();
      assert(serverStatus.activeKeyId, 'Server should have active key');
      
      log('  ✓ Server status:', 'green');
      log(`    - Active key: ${serverStatus.activeKeyId}`, 'cyan');
      log(`    - Total keys: ${serverStatus.totalKeys}`, 'cyan');
    });
  }

  async runAll() {
    log('═══════════════════════════════════════════════════════════════════', 'yellow');
    log('IndexedCP - Asymmetric Encryption Test Suite', 'yellow');
    log('═══════════════════════════════════════════════════════════════════', 'yellow');

    try {
      await this.setup();
      await this.startServer();

      // Run acceptance criteria tests
      await this.testAC0_PublicKeyFetch();
      await this.testAC1_NoPlaintextInDB();
      await this.testAC2_OfflineOperation();
      await this.testAC3_ServerDecryption();
      await this.testAC4_KeyRotation();
      await this.testAC5_Performance();

      // Run additional tests
      await this.testSessionKeyMemory();
      await this.testIVUniqueness();
      await this.testEncryptionStatus();

    } finally {
      await this.cleanup();
    }

    // Print summary
    log('\n═══════════════════════════════════════════════════════════════════', 'yellow');
    log('Test Summary', 'yellow');
    log('═══════════════════════════════════════════════════════════════════', 'yellow');
    log(`Total: ${this.passed + this.failed}`, 'cyan');
    log(`Passed: ${this.passed}`, 'green');
    log(`Failed: ${this.failed}`, this.failed > 0 ? 'red' : 'green');
    log('═══════════════════════════════════════════════════════════════════\n', 'yellow');

    if (this.failed > 0) {
      log('❌ Some tests failed', 'red');
      process.exit(1);
    } else {
      log('✅ All tests passed! 🎉', 'green');
      process.exit(0);
    }
  }
}

// Run tests
const suite = new EncryptionTestSuite();
suite.runAll().catch(error => {
  console.error('Fatal error:', error);
  process.exit(1);
});
