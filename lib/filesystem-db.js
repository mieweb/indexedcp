const fs = require('fs');
const path = require('path');
const os = require('os');

class FileSystemDB {
  constructor(dbName, version) {
    this.dbName = dbName;
    this.version = version;
    this.dbPath = path.join(os.homedir(), '.indexcp', 'db');
    this.storePath = path.join(this.dbPath, 'chunks.json');
    this.ensureDbDir();
  }

  ensureDbDir() {
    if (!fs.existsSync(this.dbPath)) {
      fs.mkdirSync(this.dbPath, { recursive: true });
    }
  }

  loadStore() {
    try {
      if (fs.existsSync(this.storePath)) {
        const data = fs.readFileSync(this.storePath, 'utf8');
        return JSON.parse(data);
      }
    } catch (error) {
      console.warn('Failed to load store:', error.message);
    }
    return [];
  }

  saveStore(records) {
    try {
      if (records.length === 0) {
        // Delete the file if there are no records
        if (fs.existsSync(this.storePath)) {
          fs.unlinkSync(this.storePath);
        }
      } else {
        fs.writeFileSync(this.storePath, JSON.stringify(records, null, 2));
      }
    } catch (error) {
      console.error('Failed to save store:', error.message);
      throw error;
    }
  }

  async add(storeName, record) {
    const records = this.loadStore();
    
    // Convert Buffer data to base64 for JSON serialization
    const serializedRecord = {
      ...record,
      data: record.data ? Buffer.from(record.data).toString('base64') : null
    };
    
    records.push(serializedRecord);
    this.saveStore(records);
    return record;
  }

  async get(storeName, key) {
    const records = this.loadStore();
    const record = records.find(r => r.id === key);
    
    if (record && record.data) {
      // Convert base64 back to Buffer
      record.data = Buffer.from(record.data, 'base64');
    }
    
    return record;
  }

  async delete(storeName, key) {
    const records = this.loadStore();
    const filteredRecords = records.filter(r => r.id !== key);
    this.saveStore(filteredRecords);
    return true;
  }

  async getAll() {
    const records = this.loadStore();
    
    // Convert base64 data back to Buffers
    return records.map(record => ({
      ...record,
      data: record.data ? Buffer.from(record.data, 'base64') : null
    }));
  }

  transaction(storeName, mode) {
    const self = this;
    return {
      objectStore: (name) => ({
        getAll: () => self.getAll(),
        delete: (key) => self.delete(storeName, key)
      }),
      done: Promise.resolve() // Add for compatibility with IndexedDB API
    };
  }
}

// Factory function to create DB instance
async function openFileSystemDB(dbName, version, options) {
  const db = new FileSystemDB(dbName, version);
  
  // Run upgrade if provided
  if (options && options.upgrade) {
    const mockDB = {
      createObjectStore: (name, opts) => {
        // Just a placeholder - we use a single store
        return {};
      },
      objectStoreNames: {
        contains: (name) => true
      }
    };
    options.upgrade(mockDB);
  }
  
  return db;
}

module.exports = { openFileSystemDB };