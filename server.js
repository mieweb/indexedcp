// Server-only entry point for server usage
// Exports only the server functionality without client IndexedDB dependencies
const server = require('./lib/server');

module.exports = server;