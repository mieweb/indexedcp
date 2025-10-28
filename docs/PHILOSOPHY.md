# IndexedDB Philosophy

## Why IndexedDB?

IndexedCP leverages IndexedDB to provide robust, transaction-safe, and universally available storage for resumable file transfers. While some browser implementations use SQLite as a backing store, IndexedDB offers a consistent API and experience across all platforms—browsers, devices, and server-side JavaScript environments. For Node.js, we use filesystem-backed storage (`~/.indexcp/db/chunks.json`) that provides the same transactional guarantees while persisting uploads across restarts.

## The Name: IndexedDB

The name "IndexedDB" reflects efficient indexing and querying capabilities, not a specific storage engine. IndexedCP embraces this philosophy: the underlying implementation may use filesystem storage (Node.js) or browser IndexedDB, but the API and guarantees remain consistent—object stores, indexes, and transactional integrity for resumable, encrypted file transfers.

## Universal Availability

IndexedCP's design goal is to work everywhere JavaScript runs. All platforms—browsers, mobile, desktop, and server-side environments like Node.js or Deno—support persistent, transactional storage through IndexedDB or equivalent filesystem-backed implementations. This universality ensures developers can rely on a single API for resumable uploads, whether in a web app or a CLI tool.

## Transaction Safety

IndexedCP relies on IndexedDB's unique support for ACID transactions in the JavaScript ecosystem. Unlike in-memory or "fake" databases, IndexedDB provides true disk persistence and transactional guarantees. This is critical for resumable file transfers—uploads survive browser crashes, network failures, and system restarts because every chunk is safely committed to disk before being marked complete.

## Isolation and Security

IndexedDB enforces user or page isolation, ensuring that data is only accessible to the origin (website) that created it. This isolation is a foundational security feature, and one of the reasons IndexedDB is not trivially available in server-side environments without careful consideration.

## Encryption and Privacy

IndexedCP pioneers asymmetric envelope encryption within IndexedDB to ensure that data is secure at rest. Our vision is for file transfer tools to support end-to-end encryption, so that only authorized recipients can decrypt uploaded data—even if the underlying storage (IndexedDB or SQLite files) is accessible. We use per-stream AES session keys wrapped by RSA public keys, providing both performance and security. In the future, we aim to expand asymmetric encryption support, further enhancing privacy and enabling zero-knowledge architectures.

## The Future: Transaction-Safe, Encrypted, Resumable File Transfers

Currently, no JavaScript file transfer library offers transaction-safe, disk-persisted, encrypted uploads as a "batteries-included" solution. IndexedCP fills this gap. Our ongoing work aims to make resumable, encrypted file transfers the standard everywhere JavaScript runs. By leveraging IndexedDB's transactional guarantees and adding asymmetric encryption, we empower developers to build secure, reliable file transfer systems for browsers, mobile apps, CLI tools, and servers.

---

*This philosophy guides the development of IndexedCP and our commitment to making IndexedDB a first-class storage solution across all JavaScript environments.*
