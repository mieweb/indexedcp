const BaseKeyStore = require('./base-keystore');

/**
 * In-Memory KeyStore implementation
 * 
 * Stores keys in memory only - useful for testing or ephemeral deployments.
 * WARNING: All keys are lost on server restart!
 */
class MemoryKeyStore extends BaseKeyStore {
  constructor(options = {}) {
    super(options);
    this.keys = new Map();
    this.ephemeral = options.ephemeral !== false; // Default true
  }

  async initialize() {
    if (this.ephemeral) {
      this.logger.info('⚠️  Memory keystore initialized (EPHEMERAL - keys lost on restart!)');
    } else {
      this.logger.info('✓ Memory keystore initialized');
    }
  }

  async save(kid, keyData) {
    this.keys.set(kid, { ...keyData });
    this.logger.info(`🔑 Saved key to memory: ${kid}`);
  }

  async load(kid) {
    const keyData = this.keys.get(kid);
    return keyData ? { ...keyData } : null;
  }

  async loadAll() {
    return Array.from(this.keys.values()).map(k => ({ ...k }));
  }

  async delete(kid) {
    const existed = this.keys.has(kid);
    this.keys.delete(kid);
    
    if (existed) {
      this.logger.info(`🗑️  Deleted key from memory: ${kid}`);
    }
    
    return existed;
  }

  async exists(kid) {
    return this.keys.has(kid);
  }

  async list() {
    return Array.from(this.keys.keys());
  }

  async close() {
    if (this.ephemeral) {
      this.keys.clear();
      this.logger.info('✓ Memory keystore cleared');
    }
  }

  /**
   * Get current memory usage stats
   * @returns {Object} Stats about stored keys
   */
  getStats() {
    return {
      totalKeys: this.keys.size,
      keys: Array.from(this.keys.keys()),
      ephemeral: this.ephemeral
    };
  }
}

module.exports = MemoryKeyStore;
