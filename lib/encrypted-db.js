const path = require("path");
const os = require("os");
const { createLogger } = require("./logger");

const logger = createLogger({ prefix: "[EncryptedDB]" });

/**
 * Enhanced IndexedDB-compatible storage with encryption support
 * Uses IndexedDBShim for persistent storage in Node.js
 *
 * Schema:
 * - sessions: { sessionId, kid, wrappedKey, createdAt }
 * - packets: { id, sessionId, seq, iv, aad, ciphertext, authTag, status }
 * - keyCache: { kid, publicKey, fetchedAt, expiresAt }
 */

/**
 * Open encrypted database with proper schema
 * Uses IndexedDBShim in production, fake-indexeddb in tests
 */
async function openEncryptedDB(dbName, version) {
  const isTestMode = process.env.NODE_ENV === "test";

  if (isTestMode) {
    // Testing: Use fake-indexeddb (ephemeral)
    require("fake-indexeddb/auto");
    const { openDB } = require("idb");

    return await openDB(dbName, version, {
      upgrade(db) {
        // Create sessions store
        if (!db.objectStoreNames.contains("sessions")) {
          db.createObjectStore("sessions", { keyPath: "sessionId" });
        }

        // Create packets store with indexes
        if (!db.objectStoreNames.contains("packets")) {
          const packetsStore = db.createObjectStore("packets", {
            keyPath: "id",
          });
          packetsStore.createIndex("sessionId", "sessionId", { unique: false });
          packetsStore.createIndex("status", "status", { unique: false });
        }

        // Create key cache store
        if (!db.objectStoreNames.contains("keyCache")) {
          db.createObjectStore("keyCache", { keyPath: "kid" });
        }
      },
    });
  } else {
    // Production: Use IndexedDBShim (persistent, SQLite-backed)
    const setGlobalVars = require("indexeddbshim");
    const fs = require("fs");

    // Configure IndexedDBShim with persistent storage location
    const dbDir = path.join(os.homedir(), ".indexcp", "idb");
    if (!fs.existsSync(dbDir)) {
      fs.mkdirSync(dbDir, { recursive: true });
    }

    // Initialize IndexedDBShim - pass global to set up indexedDB
    setGlobalVars(global, {
      checkOrigin: false, // Allow opaque origins in Node.js
      databaseBasePath: dbDir,
      deleteDatabaseFiles: false,
    });

    const { openDB } = require("idb");

    return await openDB(dbName, version, {
      upgrade(db) {
        // Create sessions store
        if (!db.objectStoreNames.contains("sessions")) {
          db.createObjectStore("sessions", { keyPath: "sessionId" });
        }

        // Create packets store with indexes
        if (!db.objectStoreNames.contains("packets")) {
          const packetsStore = db.createObjectStore("packets", {
            keyPath: "id",
          });
          packetsStore.createIndex("sessionId", "sessionId", { unique: false });
          packetsStore.createIndex("status", "status", { unique: false });
        }

        // Create key cache store
        if (!db.objectStoreNames.contains("keyCache")) {
          db.createObjectStore("keyCache", { keyPath: "kid" });
        }
      },
    });
  }
}

module.exports = { openEncryptedDB };
