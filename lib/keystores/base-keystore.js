const { createLogger } = require('../logger');

/**
 * Base KeyStore interface
 * 
 * All keystore implementations must extend this class and implement:
 * - save(kid, keyData)
 * - load(kid)
 * - loadAll()
 * - delete(kid)
 * - exists(kid)
 */

class BaseKeyStore {
  constructor(options = {}) {
    this.logger = createLogger({
      level: options.logLevel,
      prefix: `[${this.constructor.name}]`
    });
  }

  /**
   * Save a key pair to storage
   * @param {string} kid - Key ID
   * @param {Object} keyData - Key data to store
   * @param {string} keyData.kid - Key ID
   * @param {Object} keyData.privateKey - Private key (JWK format)
   * @param {string} keyData.publicKey - Public key (PEM or base64 SPKI)
   * @param {number} keyData.createdAt - Timestamp
   * @param {number} keyData.expiresAt - Expiration timestamp
   * @param {boolean} keyData.active - Whether this is the active key
   * @returns {Promise<void>}
   */
  async save(kid, keyData) {
    throw new Error('save() must be implemented by subclass');
  }

  /**
   * Load a specific key by ID
   * @param {string} kid - Key ID
   * @returns {Promise<Object|null>} Key data or null if not found
   */
  async load(kid) {
    throw new Error('load() must be implemented by subclass');
  }

  /**
   * Load all keys from storage
   * @returns {Promise<Object[]>} Array of key data objects
   */
  async loadAll() {
    throw new Error('loadAll() must be implemented by subclass');
  }

  /**
   * Delete a key from storage
   * @param {string} kid - Key ID
   * @returns {Promise<boolean>} True if deleted, false if not found
   */
  async delete(kid) {
    throw new Error('delete() must be implemented by subclass');
  }

  /**
   * Check if a key exists
   * @param {string} kid - Key ID
   * @returns {Promise<boolean>}
   */
  async exists(kid) {
    throw new Error('exists() must be implemented by subclass');
  }

  /**
   * List all key IDs
   * @returns {Promise<string[]>} Array of key IDs
   */
  async list() {
    const keys = await this.loadAll();
    return keys.map(k => k.kid);
  }

  /**
   * Clean up resources (optional)
   * @returns {Promise<void>}
   */
  async close() {
    // Optional - override if needed
  }

  /**
   * Initialize the keystore (optional)
   * @returns {Promise<void>}
   */
  async initialize() {
    // Optional - override if needed
  }
}

module.exports = BaseKeyStore;
