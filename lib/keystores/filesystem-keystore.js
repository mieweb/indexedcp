const fs = require('fs').promises;
const path = require('path');
const BaseKeyStore = require('./base-keystore');

/**
 * Filesystem-based KeyStore implementation
 * 
 * Stores keys as JSON files in a directory.
 * Default implementation - no external dependencies.
 */
class FileSystemKeyStore extends BaseKeyStore {
  constructor(options = {}) {
    super(options);
    this.keyStorePath = options.keyStorePath || './server-keys';
    this.fileExtension = '.json';
  }

  async initialize() {
    try {
      await fs.mkdir(this.keyStorePath, { recursive: true });
      this.logger.info(`✓ Filesystem keystore initialized: ${this.keyStorePath}`);
    } catch (error) {
      this.logger.error('Failed to initialize filesystem keystore:', error);
      throw error;
    }
  }

  async save(kid, keyData) {
    try {
      const keyFile = path.join(this.keyStorePath, `${kid}${this.fileExtension}`);
      await fs.writeFile(keyFile, JSON.stringify(keyData, null, 2), 'utf-8');
      this.logger.info(`🔑 Persisted key to filesystem: ${kid}`);
    } catch (error) {
      this.logger.error(`Failed to save key ${kid}:`, error);
      throw error;
    }
  }

  async load(kid) {
    try {
      const keyFile = path.join(this.keyStorePath, `${kid}${this.fileExtension}`);
      const data = await fs.readFile(keyFile, 'utf-8');
      return JSON.parse(data);
    } catch (error) {
      if (error.code === 'ENOENT') {
        return null; // Key not found
      }
      this.logger.error(`Failed to load key ${kid}:`, error);
      throw error;
    }
  }

  async loadAll() {
    try {
      await fs.mkdir(this.keyStorePath, { recursive: true });
      const files = await fs.readdir(this.keyStorePath);
      
      const keys = [];
      for (const file of files) {
        if (!file.endsWith(this.fileExtension)) {
          continue;
        }
        
        try {
          const keyFile = path.join(this.keyStorePath, file);
          const data = await fs.readFile(keyFile, 'utf-8');
          keys.push(JSON.parse(data));
        } catch (error) {
          this.logger.warn(`Failed to load key file ${file}:`, error.message);
          // Continue loading other keys
        }
      }
      
      return keys;
    } catch (error) {
      this.logger.error('Failed to load all keys:', error);
      return [];
    }
  }

  async delete(kid) {
    try {
      const keyFile = path.join(this.keyStorePath, `${kid}${this.fileExtension}`);
      await fs.unlink(keyFile);
      this.logger.info(`🗑️  Deleted key from filesystem: ${kid}`);
      return true;
    } catch (error) {
      if (error.code === 'ENOENT') {
        return false; // Already deleted or never existed
      }
      this.logger.error(`Failed to delete key ${kid}:`, error);
      throw error;
    }
  }

  async exists(kid) {
    try {
      const keyFile = path.join(this.keyStorePath, `${kid}${this.fileExtension}`);
      await fs.access(keyFile);
      return true;
    } catch (error) {
      return false;
    }
  }

  async list() {
    try {
      const files = await fs.readdir(this.keyStorePath);
      return files
        .filter(f => f.endsWith(this.fileExtension))
        .map(f => f.replace(this.fileExtension, ''));
    } catch (error) {
      return [];
    }
  }

  async close() {
    // No resources to clean up for filesystem
  }
}

module.exports = FileSystemKeyStore;
