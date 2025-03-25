"""
Error handling utilities for kairoslms.

This module provides centralized error handling functionality, including:
- Custom exception classes
- Decorator for automatic error handling
- Helper functions for consistent error responses
"""
import functools
import logging
import traceback
from typing import Callable, Any, Dict, Optional, Type, List, Union
import time

from fastapi import HTTPException, Request, status
from pydantic import BaseModel

# Configure module logger
logger = logging.getLogger(__name__)

# Custom exception classes
class KairosError(Exception):
    """Base exception class for all kairoslms errors."""
    def __init__(self, message: str, status_code: int = 500, details: Optional[Dict[str, Any]] = None):
        self.message = message
        self.status_code = status_code
        self.details = details or {}
        super().__init__(self.message)


class DataValidationError(KairosError):
    """Exception raised for data validation errors."""
    def __init__(self, message: str, details: Optional[Dict[str, Any]] = None):
        super().__init__(message, status_code=400, details=details)


class ResourceNotFoundError(KairosError):
    """Exception raised when a requested resource is not found."""
    def __init__(self, resource_type: str, resource_id: Any):
        message = f"{resource_type} with ID {resource_id} not found"
        super().__init__(message, status_code=404)


class ExternalAPIError(KairosError):
    """Exception raised for errors when interacting with external APIs."""
    def __init__(self, 
                 api_name: str, 
                 message: str, 
                 status_code: int = 500, 
                 details: Optional[Dict[str, Any]] = None):
        self.api_name = api_name
        details = details or {}
        details["api_name"] = api_name
        super().__init__(f"{api_name} API error: {message}", status_code, details)


class AuthenticationError(KairosError):
    """Exception raised for authentication errors."""
    def __init__(self, message: str = "Authentication failed"):
        super().__init__(message, status_code=401)


class AuthorizationError(KairosError):
    """Exception raised for authorization errors."""
    def __init__(self, message: str = "Not authorized to perform this action"):
        super().__init__(message, status_code=403)


class ConfigurationError(KairosError):
    """Exception raised for system configuration errors."""
    def __init__(self, message: str, details: Optional[Dict[str, Any]] = None):
        super().__init__(message, status_code=500, details=details)


# Error response model
class ErrorResponse(BaseModel):
    """Standard error response model."""
    error: str
    status_code: int
    details: Optional[Dict[str, Any]] = None
    timestamp: str
    path: Optional[str] = None
    trace_id: Optional[str] = None


def handle_exception(exc: Exception, request: Optional[Request] = None) -> ErrorResponse:
    """
    Convert an exception to a standardized ErrorResponse object.
    
    Args:
        exc: The exception to handle
        request: Optional FastAPI request object
        
    Returns:
        ErrorResponse: Standardized error response
    """
    # Default status code and error message
    status_code = 500
    error_message = "Internal server error"
    details = {}
    
    # Get the current timestamp
    timestamp = time.strftime("%Y-%m-%d %H:%M:%S UTC", time.gmtime())
    
    # Extract path from request if available
    path = request.url.path if request else None
    
    # Generate a simple trace ID (in production, use a proper request ID system)
    trace_id = f"trace-{int(time.time() * 1000)}"
    
    # Handle custom exceptions
    if isinstance(exc, KairosError):
        status_code = exc.status_code
        error_message = exc.message
        details = exc.details
    # Handle FastAPI HTTPException
    elif isinstance(exc, HTTPException):
        status_code = exc.status_code
        error_message = str(exc.detail)
    # For all other exceptions, use the exception message
    else:
        error_message = str(exc) or "Unknown error"
    
    # For 500 errors, log the full traceback
    if status_code >= 500:
        logger.error(
            f"Error processing request: {error_message}",
            exc_info=exc,
            extra={"path": path, "trace_id": trace_id}
        )
    # For 4xx errors, log with warning level
    else:
        logger.warning(
            f"Client error: {error_message}",
            extra={"path": path, "trace_id": trace_id, "status_code": status_code}
        )
    
    # Create standard error response
    return ErrorResponse(
        error=error_message,
        status_code=status_code,
        details=details,
        timestamp=timestamp,
        path=path,
        trace_id=trace_id
    )


def error_handler(func: Callable) -> Callable:
    """
    Decorator to handle exceptions in functions.
    
    Args:
        func: The function to wrap with error handling
        
    Returns:
        Callable: Wrapped function with error handling
    """
    @functools.wraps(func)
    async def wrapper(*args, **kwargs):
        try:
            return await func(*args, **kwargs)
        except Exception as exc:
            # Check if the first argument is a Request (for FastAPI endpoints)
            request = args[0] if args and isinstance(args[0], Request) else None
            
            # Convert to standard error response
            error_response = handle_exception(exc, request)
            
            # If this is a FastAPI endpoint, raise HTTPException
            if request is not None:
                raise HTTPException(
                    status_code=error_response.status_code,
                    detail=error_response.dict()
                )
            
            # For non-FastAPI functions, just return the error response
            return error_response
    
    return wrapper


def validate_required_env_vars(required_vars: List[str]) -> Dict[str, str]:
    """
    Validate that required environment variables are set.
    
    Args:
        required_vars: List of required environment variable names
        
    Returns:
        Dict[str, str]: Dictionary of environment variables and their values
        
    Raises:
        ConfigurationError: If any required variables are missing
    """
    import os
    
    env_vars = {}
    missing_vars = []
    
    for var in required_vars:
        value = os.getenv(var)
        if value is None:
            missing_vars.append(var)
        else:
            env_vars[var] = value
    
    if missing_vars:
        raise ConfigurationError(
            f"Missing required environment variables: {', '.join(missing_vars)}",
            details={"missing_vars": missing_vars}
        )
    
    return env_vars