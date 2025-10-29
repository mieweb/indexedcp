"""
Example demonstrating the logger module usage
"""

from indexedcp import create_logger

# Example 1: Basic logger with default INFO level
logger = create_logger("IndexedCP.Client")
logger.info("Client initialized")
logger.warning("This is a warning")
logger.error("This is an error")

# Example 2: Logger with DEBUG level
debug_logger = create_logger("IndexedCP.Server", level="DEBUG")
debug_logger.debug("Debug information")
debug_logger.info("Server started on port 3000")

# Example 3: Multiple loggers for different components
client_logger = create_logger("IndexedCP.Client", level="INFO")
server_logger = create_logger("IndexedCP.Server", level="DEBUG")
crypto_logger = create_logger("IndexedCP.Crypto", level="WARNING")

client_logger.info("Uploading file: myfile.txt")
server_logger.debug("Received upload request")
crypto_logger.warning("Key rotation recommended")

# Example 4: Using environment variable
import os
os.environ['INDEXEDCP_LOG_LEVEL'] = 'ERROR'
env_logger = create_logger("IndexedCP.Module")
env_logger.info("This won't be shown (level is ERROR)")
env_logger.error("This will be shown")
