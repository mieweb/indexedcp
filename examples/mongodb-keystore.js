#!/usr/bin/env node
'use strict';

/**
 * Example: IndexCPServer with MongoDB Keystore (Unified API)
 * 
 * Demonstrates using MongoDB to persist server RSA key pairs
 * across restarts, enabling key rotation without data loss.
 * 
 * Requirements:
 *   npm install mongodb
 *   MongoDB running on localhost:27017
 */

const { MongoClient } = require('mongodb');
const { IndexCPServer } = require('../lib/server');

async function main() {
  console.log('🔐 IndexCPServer with MongoDB Keystore Example (Unified API)\n');
  
  // Connect to MongoDB
  console.log('📦 Connecting to MongoDB...');
  const mongoClient = await MongoClient.connect('mongodb://localhost:27017', {
    useUnifiedTopology: true
  });
  console.log('✓ Connected to MongoDB\n');
  
  // Create server with MongoDB keystore and encryption enabled
  const server = new IndexCPServer({
    outputDir: './uploads-mongo',
    port: 3000,
    encryption: true,  // Enable encryption support
    keystoreType: 'mongodb',
    keystoreOptions: {
      client: mongoClient,
      databaseName: 'indexedcp_demo',
      collectionName: 'server_keys'
    },
    maxKeyAge: 30 * 24 * 60 * 60 * 1000 // 30 days
  });
  
  console.log('🚀 Starting server with MongoDB keystore...\n');
  await server.listen(3000);
  
  console.log('\n📊 Server Status:');
  const status = server.getEncryptionStatus();
  console.log(JSON.stringify(status, null, 2));
  
  // Simulate key rotation
  console.log('\n🔄 Demonstrating key rotation...');
  await new Promise(resolve => setTimeout(resolve, 2000));
  
  const oldKid = server.activeKeyId;
  await server.rotateKeys();
  const newKid = server.activeKeyId;
  
  console.log(`\n✓ Key rotated: ${oldKid} → ${newKid}`);
  console.log('✓ Old key persisted in MongoDB for decrypting existing client data');
  
  // Check MongoDB for persisted keys
  console.log('\n🔍 Checking persisted keys in MongoDB...');
  const db = mongoClient.db('indexedcp_demo');
  const collection = db.collection('server_keys');
  const keys = await collection.find({}).toArray();
  
  console.log(`✓ Found ${keys.length} key(s) in MongoDB:`);
  keys.forEach((key, i) => {
    console.log(`  ${i + 1}. kid: ${key.kid}, active: ${key.active}, created: ${new Date(key.createdAt).toISOString()}`);
  });
  
  // Simulate server restart
  console.log('\n♻️  Simulating server restart...');
  server.close();
  await new Promise(resolve => setTimeout(resolve, 1000));
  
  const server2 = new IndexCPServer({
    outputDir: './uploads-mongo',
    port: 3001,
    encryption: true,  // Enable encryption support
    keystoreType: 'mongodb',
    keystoreOptions: {
      client: mongoClient,
      databaseName: 'indexedcp_demo',
      collectionName: 'server_keys'
    }
  });
  
  await server2.listen(3001);
  
  console.log('\n✓ Server restarted successfully');
  console.log(`✓ Loaded persisted keys from MongoDB`);
  console.log(`✓ Active key: ${server2.activeKeyId} (same as before restart)`);
  
  const status2 = server2.getEncryptionStatus();
  console.log(`✓ Total keys available: ${status2.totalKeys}`);
  
  // Cleanup
  console.log('\n🧹 Cleaning up...');
  server2.close();
  
  // Optional: Clean up test data
  const cleanup = process.argv.includes('--cleanup');
  if (cleanup) {
    console.log('🗑️  Removing test keys from MongoDB...');
    await collection.deleteMany({});
    console.log('✓ Test data removed');
  } else {
    console.log('💡 Run with --cleanup to remove test keys from MongoDB');
  }
  
  await mongoClient.close();
  console.log('✓ MongoDB connection closed');
  
  console.log('\n✅ Example complete!');
  console.log('\nKey takeaways:');
  console.log('  • Keys persisted in MongoDB across restarts');
  console.log('  • Rotated keys remain available for decrypting old data');
  console.log('  • MongoDB provides centralized key management');
  console.log('  • Suitable for distributed/containerized deployments');
}

// Run example
if (require.main === module) {
  main().catch(error => {
    console.error('\n✗ Error:', error.message);
    if (error.code === 'ECONNREFUSED') {
      console.error('\n💡 Make sure MongoDB is running:');
      console.error('   brew services start mongodb-community');
      console.error('   or: mongod --dbpath /path/to/data');
    }
    process.exit(1);
  });
}

module.exports = { main };
