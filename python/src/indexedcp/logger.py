"""
Logger module for IndexedCP

Provides a centralized logging utility compatible with Python's logging module.
"""

import logging
import os
import sys
from typing import Optional


# ANSI color codes for different log levels
class LogColors:
    """ANSI color codes for terminal output"""
    RESET = '\033[0m'
    DEBUG = '\033[36m'      # Cyan
    INFO = '\033[32m'       # Green
    WARNING = '\033[33m'    # Yellow
    ERROR = '\033[31m'      # Red
    CRITICAL = '\033[35m'   # Magenta
    

class ColoredFormatter(logging.Formatter):
    """Formatter that adds color to log level names"""
    
    COLORS = {
        logging.DEBUG: LogColors.DEBUG,
        logging.INFO: LogColors.INFO,
        logging.WARNING: LogColors.WARNING,
        logging.ERROR: LogColors.ERROR,
        logging.CRITICAL: LogColors.CRITICAL,
    }
    
    def format(self, record):
        # Only add colors if output is to a terminal
        if hasattr(sys.stderr, 'isatty') and sys.stderr.isatty():
            levelname = record.levelname
            if record.levelno in self.COLORS:
                record.levelname = f"{self.COLORS[record.levelno]}{levelname}{LogColors.RESET}"
        return super().format(record)


def create_logger(name: str, level: Optional[str] = None) -> logging.Logger:
    """
    Create a logger instance with the specified log level.
    
    Args:
        name: Logger name (typically module name, e.g., "IndexedCP.Client")
        level: Log level (DEBUG, INFO, WARNING, ERROR, CRITICAL).
               Falls back to INDEXEDCP_LOG_LEVEL env var, then INFO.
    
    Returns:
        Configured logger instance
    
    Example:
        >>> logger = create_logger("IndexedCP.Client", level="INFO")
        >>> logger.info("Client initialized")
    """
    # Determine log level
    if level is None:
        level = os.environ.get('INDEXEDCP_LOG_LEVEL', 'INFO')
    
    level = level.upper()
    
    # Create logger
    logger = logging.getLogger(name)
    logger.setLevel(getattr(logging, level, logging.INFO))
    
    # Avoid duplicate handlers if logger already configured
    if not logger.handlers:
        # Create console handler
        handler = logging.StreamHandler()
        handler.setLevel(getattr(logging, level, logging.INFO))
        
        # Create colored formatter with prefix (name) included
        formatter = ColoredFormatter(
            fmt='%(name)s %(levelname)s %(message)s',
            datefmt='%Y-%m-%d %H:%M:%S'
        )
        handler.setFormatter(formatter)
        
        # Add handler to logger
        logger.addHandler(handler)
    
    # Prevent propagation to root logger to avoid duplicate logs
    logger.propagate = False
    
    return logger
