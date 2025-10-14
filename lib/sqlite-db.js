const path = require('path');
const os = require('os');
const fs = require('fs');
const websql = require('websql');

/**
 * SQLite-backed database using WebSQL API
 * This provides an IndexedDB-like interface backed by a SQLite file via WebSQL.
 */
class SQLiteDB {
  constructor(dbName, version, dbPath) {
    this.dbName = dbName;
    this.version = version;
    this.dbPath = dbPath;
    this.db = websql(dbPath, String(version), dbName, 50 * 1024 * 1024); // 50MB
    this._initialized = false;
  }

  async _ensureInitialized(upgrade) {
    if (this._initialized) return;

    return new Promise((resolve, reject) => {
      this.db.transaction((tx) => {
        // Check if the chunks table exists
        tx.executeSql(
          `SELECT name FROM sqlite_master WHERE type='table' AND name='chunks'`,
          [],
          (tx, results) => {
            if (results.rows.length === 0 && upgrade) {
              // Table doesn't exist, create it
              tx.executeSql(
                `CREATE TABLE chunks (
                  id TEXT PRIMARY KEY,
                  fileName TEXT,
                  chunkIndex INTEGER,
                  data BLOB
                )`,
                [],
                () => {
                  this._initialized = true;
                  resolve();
                },
                (tx, error) => {
                  reject(error);
                  return true;
                }
              );
            } else {
              this._initialized = true;
              resolve();
            }
          },
          (tx, error) => {
            reject(error);
            return true;
          }
        );
      });
    });
  }

  async add(storeName, record) {
    return new Promise((resolve, reject) => {
      this.db.transaction((tx) => {
        // Serialize the data (convert Buffer to base64)
        const serializedData = record.data ? Buffer.from(record.data).toString('base64') : null;
        
        tx.executeSql(
          `INSERT INTO chunks (id, fileName, chunkIndex, data) VALUES (?, ?, ?, ?)`,
          [
            record.id, 
            record.fileName !== undefined ? record.fileName : null, 
            record.chunkIndex !== undefined ? record.chunkIndex : null, 
            serializedData
          ],
          (tx, results) => {
            resolve(record);
          },
          (tx, error) => {
            reject(error);
            return true;
          }
        );
      });
    });
  }

  async get(storeName, key) {
    return new Promise((resolve, reject) => {
      this.db.readTransaction((tx) => {
        tx.executeSql(
          `SELECT * FROM chunks WHERE id = ?`,
          [key],
          (tx, results) => {
            if (results.rows.length > 0) {
              const row = results.rows.item(0);
              // Deserialize the data (convert base64 back to Buffer)
              const record = {
                id: row.id,
                fileName: row.fileName,
                chunkIndex: row.chunkIndex,
                data: row.data ? Buffer.from(row.data, 'base64') : null
              };
              resolve(record);
            } else {
              resolve(undefined);
            }
          },
          (tx, error) => {
            reject(error);
            return true;
          }
        );
      });
    });
  }

  async delete(storeName, key) {
    return new Promise((resolve, reject) => {
      this.db.transaction((tx) => {
        tx.executeSql(
          `DELETE FROM chunks WHERE id = ?`,
          [key],
          (tx, results) => {
            resolve(undefined);
          },
          (tx, error) => {
            reject(error);
            return true;
          }
        );
      });
    });
  }

  transaction(storeNames, mode) {
    const self = this;
    return {
      objectStore: (name) => ({
        getAll: () => {
          return new Promise((resolve, reject) => {
            self.db.readTransaction((tx) => {
              tx.executeSql(
                `SELECT * FROM chunks`,
                [],
                (tx, results) => {
                  const records = [];
                  for (let i = 0; i < results.rows.length; i++) {
                    const row = results.rows.item(i);
                    records.push({
                      id: row.id,
                      fileName: row.fileName,
                      chunkIndex: row.chunkIndex,
                      data: row.data ? Buffer.from(row.data, 'base64') : null
                    });
                  }
                  resolve(records);
                },
                (tx, error) => {
                  reject(error);
                  return true;
                }
              );
            });
          });
        },
        delete: (key) => self.delete(storeNames, key)
      }),
      done: Promise.resolve()
    };
  }

  close() {
    // WebSQL doesn't have an explicit close method
  }
}

/**
 * Factory function to open a SQLite database with idb-like API
 */
async function openSQLiteDB(dbName, version, options) {
  // Ensure the database directory exists
  const dbDir = path.join(os.homedir(), '.indexcp', 'db');
  if (!fs.existsSync(dbDir)) {
    fs.mkdirSync(dbDir, { recursive: true });
  }

  // Set up the database file path
  const dbPath = path.join(dbDir, 'indexedcp.sqlite');

  const db = new SQLiteDB(dbName, version, dbPath);
  
  // Initialize the database (run upgrade if needed)
  if (options && options.upgrade) {
    await db._ensureInitialized(options.upgrade);
  }
  
  return db;
}

module.exports = { openSQLiteDB };
