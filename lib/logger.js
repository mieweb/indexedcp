const log = require('console-log-level');

/**
 * Create a logger instance with the specified log level
 * @param {Object} options - Logger options
 * @param {string} options.level - Log level (trace, debug, info, warn, error, fatal)
 * @param {string} options.prefix - Optional prefix for log messages
 * @returns {Object} Logger instance
 */
function createLogger(options = {}) {
  const level = options.level || process.env.INDEXCP_LOG_LEVEL || 'info';
  const prefix = options.prefix || '';
  
  const logger = log({ level });
  
  // If a prefix is provided, wrap the logger methods to include it
  if (prefix) {
    const wrappedLogger = {};
    ['trace', 'debug', 'info', 'warn', 'error', 'fatal'].forEach(method => {
      wrappedLogger[method] = (...args) => {
        logger[method](prefix, ...args);
      };
    });
    return wrappedLogger;
  }
  
  return logger;
}

module.exports = { createLogger };
