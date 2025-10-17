const BaseKeyStore = require('./base-keystore');

/**
 * MongoDB-based KeyStore implementation
 * 
 * Stores keys in a MongoDB collection.
 * Requires: mongodb driver (npm install mongodb)
 * 
 * Usage:
 *   const { MongoClient } = require('mongodb');
 *   const client = await MongoClient.connect('mongodb://localhost:27017');
 *   const keystore = new MongoDBKeyStore({
 *     client: client,
 *     dbName: 'indexcp',
 *     collectionName: 'server_keys'
 *   });
 */
class MongoDBKeyStore extends BaseKeyStore {
  constructor(options = {}) {
    super(options);
    
    if (!options.client) {
      throw new Error('MongoDB client is required. Pass { client: MongoClient }');
    }
    
    this.client = options.client;
    this.dbName = options.dbName || 'indexcp';
    this.collectionName = options.collectionName || 'server_keys';
    this.db = null;
    this.collection = null;
  }

  async initialize() {
    try {
      this.db = this.client.db(this.dbName);
      this.collection = this.db.collection(this.collectionName);
      
      // Create index on kid for faster lookups
      await this.collection.createIndex({ kid: 1 }, { unique: true });
      
      // Create index on createdAt for sorting
      await this.collection.createIndex({ createdAt: -1 });
      
      this.logger.info(`✓ MongoDB keystore initialized: ${this.dbName}.${this.collectionName}`);
    } catch (error) {
      this.logger.error('Failed to initialize MongoDB keystore:', error);
      throw error;
    }
  }

  async save(kid, keyData) {
    try {
      // Use upsert to handle both insert and update
      await this.collection.updateOne(
        { kid },
        { 
          $set: {
            ...keyData,
            updatedAt: Date.now()
          }
        },
        { upsert: true }
      );
      
      this.logger.info(`🔑 Persisted key to MongoDB: ${kid}`);
    } catch (error) {
      this.logger.error(`Failed to save key ${kid} to MongoDB:`, error);
      throw error;
    }
  }

  async load(kid) {
    try {
      const doc = await this.collection.findOne({ kid });
      
      if (!doc) {
        return null;
      }
      
      // Remove MongoDB _id field
      const { _id, updatedAt, ...keyData } = doc;
      return keyData;
    } catch (error) {
      this.logger.error(`Failed to load key ${kid} from MongoDB:`, error);
      throw error;
    }
  }

  async loadAll() {
    try {
      const docs = await this.collection
        .find({})
        .sort({ createdAt: -1 })
        .toArray();
      
      // Remove MongoDB _id field from each document
      return docs.map(({ _id, updatedAt, ...keyData }) => keyData);
    } catch (error) {
      this.logger.error('Failed to load all keys from MongoDB:', error);
      return [];
    }
  }

  async delete(kid) {
    try {
      const result = await this.collection.deleteOne({ kid });
      
      if (result.deletedCount > 0) {
        this.logger.info(`🗑️  Deleted key from MongoDB: ${kid}`);
        return true;
      }
      
      return false; // Key not found
    } catch (error) {
      this.logger.error(`Failed to delete key ${kid} from MongoDB:`, error);
      throw error;
    }
  }

  async exists(kid) {
    try {
      const count = await this.collection.countDocuments({ kid }, { limit: 1 });
      return count > 0;
    } catch (error) {
      this.logger.error(`Failed to check existence of key ${kid}:`, error);
      return false;
    }
  }

  async list() {
    try {
      const docs = await this.collection
        .find({}, { projection: { kid: 1, _id: 0 } })
        .toArray();
      
      return docs.map(doc => doc.kid);
    } catch (error) {
      this.logger.error('Failed to list keys from MongoDB:', error);
      return [];
    }
  }

  async close() {
    // Note: We don't close the client here as it may be shared
    // The application should manage the MongoDB client lifecycle
    this.logger.info('✓ MongoDB keystore closed (client still managed by application)');
  }

  /**
   * Clean up old keys (optional utility method)
   * @param {number} maxAge - Maximum age in milliseconds
   * @returns {Promise<number>} Number of keys deleted
   */
  async cleanup(maxAge) {
    try {
      const cutoff = Date.now() - maxAge;
      const result = await this.collection.deleteMany({
        createdAt: { $lt: cutoff },
        active: { $ne: true } // Don't delete active keys
      });
      
      this.logger.info(`🧹 Cleaned up ${result.deletedCount} old keys from MongoDB`);
      return result.deletedCount;
    } catch (error) {
      this.logger.error('Failed to cleanup old keys:', error);
      return 0;
    }
  }

  /**
   * Find keys by criteria
   * @param {Object} query - MongoDB query
   * @returns {Promise<Object[]>} Array of matching key data
   */
  async find(query) {
    try {
      const docs = await this.collection.find(query).toArray();
      return docs.map(({ _id, updatedAt, ...keyData }) => keyData);
    } catch (error) {
      this.logger.error('Failed to find keys:', error);
      return [];
    }
  }
}

module.exports = MongoDBKeyStore;
