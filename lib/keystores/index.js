/**
 * KeyStore Factory and Exports
 * 
 * Provides easy access to all keystore implementations
 */

const BaseKeyStore = require('./base-keystore');
const FileSystemKeyStore = require('./filesystem-keystore');
const MemoryKeyStore = require('./memory-keystore');
const MongoDBKeyStore = require('./mongodb-keystore');

/**
 * Create a keystore instance based on type
 * @param {string} type - Type of keystore: 'filesystem', 'mongodb', 'memory'
 * @param {Object} options - Options for the keystore
 * @returns {BaseKeyStore} Keystore instance
 */
function createKeyStore(type, options = {}) {
  switch (type.toLowerCase()) {
    case 'filesystem':
    case 'file':
    case 'fs':
      return new FileSystemKeyStore(options);
      
    case 'mongodb':
    case 'mongo':
      return new MongoDBKeyStore(options);
      
    case 'memory':
    case 'mem':
      return new MemoryKeyStore(options);
      
    default:
      throw new Error(`Unknown keystore type: ${type}. Valid types: filesystem, mongodb, memory`);
  }
}

module.exports = {
  BaseKeyStore,
  FileSystemKeyStore,
  MemoryKeyStore,
  MongoDBKeyStore,
  createKeyStore
};
