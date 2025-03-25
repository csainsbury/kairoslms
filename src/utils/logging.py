"""
Logging utilities for kairoslms.

This module provides a centralized logging configuration system including:
- File-based logging with rotation
- JSON formatted logs for easier parsing
- Log level configuration via environment variables
- Integration with external log aggregation services (optional)
"""
import os
import sys
import logging
import logging.handlers
import json
from typing import Dict, Any, Optional, List, Union
from datetime import datetime
import traceback

# Define custom JSON formatter
class JsonFormatter(logging.Formatter):
    """
    Formatter that outputs JSON strings after parsing the log record.
    """
    def __init__(self, **kwargs):
        self.json_default = kwargs.pop('json_default', str)
        self.json_encoder = kwargs.pop('json_encoder', None)
        self.json_indent = kwargs.pop('json_indent', None)
        self.json_separators = kwargs.pop('json_separators', None)
        self.prefix = kwargs.pop('prefix', '')
        
        # Update the format to add metadata information
        self.reserved_keys = {
            'args', 'asctime', 'created', 'exc_info', 'exc_text', 'filename',
            'funcName', 'levelname', 'levelno', 'lineno', 'module',
            'msecs', 'message', 'msg', 'name', 'pathname', 'process',
            'processName', 'relativeCreated', 'stack_info', 'thread', 'threadName'
        }
        
        super(JsonFormatter, self).__init__(**kwargs)

    def format(self, record: logging.LogRecord) -> str:
        """
        Format the log record as JSON.
        
        Args:
            record: The log record to format
            
        Returns:
            str: JSON formatted log record
        """
        # Process the log record
        record_dict = self._prepare_log_dict(record)
        
        # Add exception info if available
        if record.exc_info:
            record_dict['exception'] = {
                'type': record.exc_info[0].__name__,
                'message': str(record.exc_info[1]),
                'traceback': self._format_traceback(record.exc_info[2])
            }
        
        # Add stack info if available
        if record.stack_info:
            record_dict['stack_info'] = record.stack_info
        
        # Convert to JSON
        return self.prefix + json.dumps(
            record_dict,
            default=self.json_default,
            cls=self.json_encoder,
            indent=self.json_indent,
            separators=self.json_separators
        )
    
    def _prepare_log_dict(self, record: logging.LogRecord) -> Dict[str, Any]:
        """
        Convert the log record to a dictionary.
        
        Args:
            record: The log record to convert
            
        Returns:
            Dict[str, Any]: Dictionary representation of the log record
        """
        # Get the log message
        message = record.getMessage()
        
        # Start with a timestamp and the log message
        result = {
            'timestamp': datetime.fromtimestamp(record.created).isoformat(),
            'level': record.levelname,
            'name': record.name,
            'message': message
        }
        
        # Add standard record attributes
        for key, value in record.__dict__.items():
            if key not in self.reserved_keys:
                result[key] = value
        
        # Add location info
        result['location'] = {
            'file': record.pathname,
            'line': record.lineno,
            'function': record.funcName
        }
        
        # Add process and thread info
        result['process'] = {
            'id': record.process,
            'name': record.processName
        }
        result['thread'] = {
            'id': record.thread,
            'name': record.threadName
        }
        
        return result
    
    def _format_traceback(self, tb) -> List[Dict[str, Any]]:
        """
        Format traceback into a list of dictionaries.
        
        Args:
            tb: Traceback object
            
        Returns:
            List[Dict[str, Any]]: List of formatted traceback frames
        """
        frames = []
        while tb:
            frame = tb.tb_frame
            frames.append({
                'filename': frame.f_code.co_filename,
                'name': frame.f_code.co_name,
                'lineno': tb.tb_lineno
            })
            tb = tb.tb_next
        return frames


def configure_logging(
    log_level: str = None,
    log_file: str = None,
    max_bytes: int = 10485760,  # 10 MB
    backup_count: int = 5,
    json_format: bool = True,
    console_output: bool = True
) -> None:
    """
    Configure the logging system for the application.
    
    Args:
        log_level: The log level (DEBUG, INFO, WARNING, ERROR, CRITICAL)
        log_file: Path to the log file
        max_bytes: Maximum size of log file before rotation
        backup_count: Number of backup files to keep
        json_format: Whether to output logs in JSON format
        console_output: Whether to output logs to the console
    """
    # Get log level from environment variable if not provided
    if log_level is None:
        log_level = os.getenv('LOG_LEVEL', 'INFO').upper()
    
    # Ensure valid log level
    numeric_level = getattr(logging, log_level, None)
    if not isinstance(numeric_level, int):
        raise ValueError(f"Invalid log level: {log_level}")
    
    # Get log file path from environment variable if not provided
    if log_file is None:
        log_directory = os.getenv('LOG_DIR', 'logs')
        os.makedirs(log_directory, exist_ok=True)
        log_file = os.path.join(log_directory, 'kairoslms.log')
    
    # Configure root logger
    root_logger = logging.getLogger()
    root_logger.setLevel(numeric_level)
    
    # Remove existing handlers to avoid duplicate logs
    for handler in root_logger.handlers[:]:
        root_logger.removeHandler(handler)
    
    # Create handlers
    handlers = []
    
    # File handler with rotation
    if log_file:
        file_handler = logging.handlers.RotatingFileHandler(
            log_file,
            maxBytes=max_bytes,
            backupCount=backup_count
        )
        handlers.append(file_handler)
    
    # Console handler
    if console_output:
        console_handler = logging.StreamHandler(sys.stdout)
        handlers.append(console_handler)
    
    # Set formatter for all handlers
    for handler in handlers:
        if json_format:
            handler.setFormatter(JsonFormatter())
        else:
            handler.setFormatter(logging.Formatter(
                '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
            ))
        root_logger.addHandler(handler)
    
    # Log the configuration
    logging.info(f"Logging configured: level={log_level}, file={log_file}, json_format={json_format}")
    

def get_logger(name: str) -> logging.Logger:
    """
    Get a logger with the specified name.
    
    Args:
        name: The name of the logger
        
    Returns:
        logging.Logger: Configured logger
    """
    return logging.getLogger(name)