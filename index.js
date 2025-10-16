const client = require('./lib/client');
const server = require('./lib/server');
const cryptoUtils = require('./lib/crypto-utils');
const keystores = require('./lib/keystores');

// Backward compatibility: export the main classes
// Encryption is now integrated via { encryption: true } option
module.exports = {
  client,
  server,
  cryptoUtils,
  keystores,
  
  // Deprecated: Use client/server with { encryption: true } instead
  encryptedClient: client,
  encryptedServer: server
};