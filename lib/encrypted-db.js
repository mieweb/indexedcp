const fs = require('fs');
const path = require('path');
const os = require('os');

/**
 * Enhanced IndexedDB-compatible storage with encryption support
 * 
 * Schema:
 * - sessions: { sessionId, kid, wrappedKey, createdAt }
 * - packets: { id, sessionId, seq, iv, aad, ciphertext, authTag, status }
 * - keyCache: { kid, publicKey, fetchedAt, expiresAt }
 */

class EncryptedDB {
  constructor(dbName, version) {
    this.dbName = dbName;
    this.version = version;
    this.dbPath = path.join(os.homedir(), '.indexcp', 'encrypted-db');
    this.sessionsPath = path.join(this.dbPath, 'sessions.json');
    this.packetsPath = path.join(this.dbPath, 'packets.json');
    this.keyCachePath = path.join(this.dbPath, 'key-cache.json');
    this.ensureDbDir();
  }

  ensureDbDir() {
    if (!fs.existsSync(this.dbPath)) {
      fs.mkdirSync(this.dbPath, { recursive: true });
    }
  }

  loadStore(storeName) {
    let storePath;
    switch (storeName) {
      case 'sessions':
        storePath = this.sessionsPath;
        break;
      case 'packets':
        storePath = this.packetsPath;
        break;
      case 'keyCache':
        storePath = this.keyCachePath;
        break;
      default:
        throw new Error(`Unknown store: ${storeName}`);
    }

    try {
      if (fs.existsSync(storePath)) {
        const data = fs.readFileSync(storePath, 'utf8');
        return JSON.parse(data);
      }
    } catch (error) {
      console.warn(`Failed to load store ${storeName}:`, error.message);
    }
    return [];
  }

  saveStore(storeName, records) {
    let storePath;
    switch (storeName) {
      case 'sessions':
        storePath = this.sessionsPath;
        break;
      case 'packets':
        storePath = this.packetsPath;
        break;
      case 'keyCache':
        storePath = this.keyCachePath;
        break;
      default:
        throw new Error(`Unknown store: ${storeName}`);
    }

    try {
      if (records.length === 0) {
        // Delete the file if there are no records
        if (fs.existsSync(storePath)) {
          fs.unlinkSync(storePath);
        }
      } else {
        fs.writeFileSync(storePath, JSON.stringify(records, null, 2));
      }
    } catch (error) {
      console.error(`Failed to save store ${storeName}:`, error.message);
      throw error;
    }
  }

  async add(storeName, record) {
    const records = this.loadStore(storeName);
    
    // Auto-generate ID if not present
    if (!record.id && storeName === 'packets') {
      record.id = `${record.sessionId}-${record.seq}`;
    }
    
    records.push(record);
    this.saveStore(storeName, records);
    return record;
  }

  async put(storeName, record) {
    const records = this.loadStore(storeName);
    
    // Find and replace existing record or add new
    const keyPath = this.getKeyPath(storeName);
    const keyValue = record[keyPath];
    const index = records.findIndex(r => r[keyPath] === keyValue);
    
    if (index >= 0) {
      records[index] = record;
    } else {
      records.push(record);
    }
    
    this.saveStore(storeName, records);
    return record;
  }

  async get(storeName, key) {
    const records = this.loadStore(storeName);
    const keyPath = this.getKeyPath(storeName);
    return records.find(r => r[keyPath] === key);
  }

  async delete(storeName, key) {
    const records = this.loadStore(storeName);
    const keyPath = this.getKeyPath(storeName);
    const filteredRecords = records.filter(r => r[keyPath] !== key);
    this.saveStore(storeName, filteredRecords);
    return true;
  }

  async getAll(storeName) {
    return this.loadStore(storeName);
  }

  async getAllFromIndex(storeName, indexName, value) {
    const records = this.loadStore(storeName);
    return records.filter(r => r[indexName] === value);
  }

  getKeyPath(storeName) {
    switch (storeName) {
      case 'sessions':
        return 'sessionId';
      case 'packets':
        return 'id';
      case 'keyCache':
        return 'kid';
      default:
        return 'id';
    }
  }

  transaction(storeNames, mode) {
    const self = this;
    const stores = Array.isArray(storeNames) ? storeNames : [storeNames];
    
    const storeHandlers = {};
    stores.forEach(storeName => {
      storeHandlers[storeName] = {
        add: (record) => self.add(storeName, record),
        put: (record) => self.put(storeName, record),
        get: (key) => self.get(storeName, key),
        delete: (key) => self.delete(storeName, key),
        getAll: () => self.getAll(storeName),
        index: (indexName) => ({
          getAll: (value) => self.getAllFromIndex(storeName, indexName, value)
        })
      };
    });

    return {
      objectStore: (name) => storeHandlers[name],
      done: Promise.resolve()
    };
  }

  /**
   * Cleanup old packets by session ID
   */
  async cleanupSession(sessionId) {
    const packets = this.loadStore('packets');
    const filteredPackets = packets.filter(p => p.sessionId !== sessionId);
    this.saveStore('packets', filteredPackets);
    
    const sessions = this.loadStore('sessions');
    const filteredSessions = sessions.filter(s => s.sessionId !== sessionId);
    this.saveStore('sessions', filteredSessions);
  }

  /**
   * Get pending packets for upload
   */
  async getPendingPackets() {
    const packets = this.loadStore('packets');
    return packets.filter(p => p.status === 'pending');
  }

  /**
   * Update packet status
   */
  async updatePacketStatus(packetId, status) {
    const packets = this.loadStore('packets');
    const packet = packets.find(p => p.id === packetId);
    if (packet) {
      packet.status = status;
      this.saveStore('packets', packets);
    }
  }
}

/**
 * Factory function to create EncryptedDB instance
 */
async function openEncryptedDB(dbName, version, options) {
  const db = new EncryptedDB(dbName, version);
  
  // Run upgrade if provided
  if (options && options.upgrade) {
    const mockDB = {
      createObjectStore: (name, opts) => {
        // Return mock with index creation support
        return {
          createIndex: (indexName, keyPath, opts) => {
            // Just a placeholder for compatibility
          }
        };
      },
      objectStoreNames: {
        contains: (name) => ['sessions', 'packets', 'keyCache'].includes(name)
      }
    };
    options.upgrade(mockDB);
  }
  
  return db;
}

module.exports = { openEncryptedDB, EncryptedDB };
