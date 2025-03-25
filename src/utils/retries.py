"""
Retry utilities for kairoslms.

This module provides functionality for retrying operations with exponential backoff:
- Retry decorators for functions
- Configurable retry policies
- Specific retry handling for external APIs
"""
import time
import random
import logging
import functools
from typing import Callable, Any, Optional, Type, List, Union, Tuple
import inspect
import asyncio

# Configure module logger
logger = logging.getLogger(__name__)

class RetryableError(Exception):
    """Base class for errors that should be retried."""
    pass


def retry(
    max_tries: int = 3,
    backoff_factor: float = 1.0,
    max_backoff: float = 60.0,
    jitter: bool = True,
    retryable_exceptions: Tuple[Type[Exception], ...] = (RetryableError,),
    on_retry: Optional[Callable[[Exception, int], None]] = None
):
    """
    Decorator to retry a function on failure with exponential backoff.
    
    Args:
        max_tries: Maximum number of attempts (1 means no retries)
        backoff_factor: Exponential backoff factor (seconds)
        max_backoff: Maximum backoff time (seconds)
        jitter: Whether to add jitter to the backoff time
        retryable_exceptions: Tuple of exceptions that should trigger a retry
        on_retry: Optional callback function called on each retry
        
    Returns:
        Callable: Decorated function
    """
    def decorator(func):
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            last_exception = None
            
            for attempt in range(1, max_tries + 1):
                try:
                    return func(*args, **kwargs)
                except retryable_exceptions as e:
                    last_exception = e
                    
                    # Last attempt, re-raise the exception
                    if attempt == max_tries:
                        raise
                    
                    # Calculate backoff time with exponential backoff
                    backoff = min(backoff_factor * (2 ** (attempt - 1)), max_backoff)
                    
                    # Add jitter if requested
                    if jitter:
                        backoff = backoff * (0.5 + random.random())
                    
                    # Log the retry
                    logger.warning(
                        f"Retry {attempt}/{max_tries - 1} for {func.__name__} after {backoff:.2f}s "
                        f"due to: {str(e)}"
                    )
                    
                    # Call the on_retry callback if provided
                    if on_retry:
                        on_retry(e, attempt)
                    
                    # Sleep before the next attempt
                    time.sleep(backoff)
                except Exception as e:
                    # Non-retryable exception, re-raise immediately
                    raise
            
            # We should never get here, but just in case
            if last_exception:
                raise last_exception
            
            return None
        
        @functools.wraps(func)
        async def async_wrapper(*args, **kwargs):
            last_exception = None
            
            for attempt in range(1, max_tries + 1):
                try:
                    return await func(*args, **kwargs)
                except retryable_exceptions as e:
                    last_exception = e
                    
                    # Last attempt, re-raise the exception
                    if attempt == max_tries:
                        raise
                    
                    # Calculate backoff time with exponential backoff
                    backoff = min(backoff_factor * (2 ** (attempt - 1)), max_backoff)
                    
                    # Add jitter if requested
                    if jitter:
                        backoff = backoff * (0.5 + random.random())
                    
                    # Log the retry
                    logger.warning(
                        f"Retry {attempt}/{max_tries - 1} for {func.__name__} after {backoff:.2f}s "
                        f"due to: {str(e)}"
                    )
                    
                    # Call the on_retry callback if provided
                    if on_retry:
                        on_retry(e, attempt)
                    
                    # Sleep before the next attempt
                    await asyncio.sleep(backoff)
                except Exception as e:
                    # Non-retryable exception, re-raise immediately
                    raise
            
            # We should never get here, but just in case
            if last_exception:
                raise last_exception
            
            return None
        
        # Return the appropriate wrapper based on whether the function is async
        if inspect.iscoroutinefunction(func):
            return async_wrapper
        else:
            return wrapper
    
    return decorator


# Specialized retry for API calls
def api_retry(
    api_name: str,
    max_tries: int = 5,
    backoff_factor: float = 2.0,
    max_backoff: float = 120.0,
    jitter: bool = True,
    retryable_exceptions: Optional[Tuple[Type[Exception], ...]] = None
):
    """
    Specialized retry decorator for API calls with logging.
    
    Args:
        api_name: Name of the API (for logging)
        max_tries: Maximum number of attempts
        backoff_factor: Exponential backoff factor (seconds)
        max_backoff: Maximum backoff time (seconds)
        jitter: Whether to add jitter to the backoff time
        retryable_exceptions: Tuple of exceptions that should trigger a retry
        
    Returns:
        Callable: Decorated function
    """
    # Default retryable exceptions if none provided
    if retryable_exceptions is None:
        retryable_exceptions = (
            ConnectionError, TimeoutError, RetryableError,
            # Common HTTP library exceptions
            Exception
        )
    
    def on_retry(exception: Exception, attempt: int):
        """Log detailed information on each retry."""
        logger.warning(
            f"{api_name} API call failed (attempt {attempt}): {str(exception)}",
            extra={
                "api_name": api_name,
                "attempt": attempt,
                "exception": str(exception),
                "exception_type": type(exception).__name__
            }
        )
    
    # Use the base retry decorator with API-specific settings
    return retry(
        max_tries=max_tries,
        backoff_factor=backoff_factor,
        max_backoff=max_backoff,
        jitter=jitter,
        retryable_exceptions=retryable_exceptions,
        on_retry=on_retry
    )


def is_retryable_http_error(status_code: int) -> bool:
    """
    Determine if an HTTP status code should trigger a retry.
    
    Args:
        status_code: The HTTP status code
        
    Returns:
        bool: True if the status code should trigger a retry
    """
    # Retry on 429 (Too Many Requests) and 5xx server errors
    return status_code == 429 or (500 <= status_code < 600)