"""
Middleware for kairoslms application.

This module defines FastAPI middleware for:
- Error handling and exception processing
- Request logging
- Authentication
- Rate limiting
- CORS configuration
"""
import time
import logging
from typing import Callable, Dict, Any, Optional, List, Union
import traceback
import json
import os

from fastapi import FastAPI, Request, Response
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.status import HTTP_500_INTERNAL_SERVER_ERROR, HTTP_429_TOO_MANY_REQUESTS

from src.utils.error_handling import KairosError, ErrorResponse
from src.utils.logging import get_logger

# Configure module logger
logger = get_logger(__name__)

class ErrorHandlingMiddleware(BaseHTTPMiddleware):
    """Middleware for handling exceptions and converting them to appropriate responses."""
    
    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        """
        Process a request and handle any exceptions.
        
        Args:
            request: The incoming request
            call_next: The next middleware or route handler
            
        Returns:
            Response: The response
        """
        try:
            # Process the request
            response = await call_next(request)
            return response
        
        except Exception as exc:
            # Get traceback
            tb_str = traceback.format_exc()
            
            # Determine status code and error message
            status_code = HTTP_500_INTERNAL_SERVER_ERROR
            error_message = "Internal server error"
            error_details = {}
            
            # Handle custom exceptions
            if isinstance(exc, KairosError):
                status_code = exc.status_code
                error_message = exc.message
                error_details = exc.details
            else:
                # Log stack trace for 500 errors
                logger.error(f"Unhandled exception: {str(exc)}\n{tb_str}")
            
            # Create error response
            timestamp = time.strftime("%Y-%m-%d %H:%M:%S UTC", time.gmtime())
            error_response = ErrorResponse(
                error=error_message,
                status_code=status_code,
                details=error_details,
                timestamp=timestamp,
                path=request.url.path
            )
            
            # Return JSON response
            return JSONResponse(
                status_code=status_code,
                content=error_response.dict()
            )


class RequestLoggingMiddleware(BaseHTTPMiddleware):
    """Middleware for logging requests and responses."""
    
    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        """
        Log requests and responses.
        
        Args:
            request: The incoming request
            call_next: The next middleware or route handler
            
        Returns:
            Response: The response
        """
        # Start timer
        start_time = time.time()
        
        # Generate request ID
        request_id = f"req-{int(start_time * 1000)}"
        
        # Log the request
        logger.info(
            f"Request started: {request.method} {request.url.path}",
            extra={
                "request_id": request_id,
                "method": request.method,
                "path": request.url.path,
                "client_ip": request.client.host if request.client else "unknown",
                "user_agent": request.headers.get("user-agent", "unknown")
            }
        )
        
        # Process the request
        response = await call_next(request)
        
        # Calculate duration
        duration = time.time() - start_time
        
        # Log the response
        logger.info(
            f"Request completed: {request.method} {request.url.path} - {response.status_code} ({duration:.3f}s)",
            extra={
                "request_id": request_id,
                "method": request.method,
                "path": request.url.path,
                "status_code": response.status_code,
                "duration": duration
            }
        )
        
        # Add request ID header to the response
        response.headers["X-Request-ID"] = request_id
        
        return response


class RateLimitingMiddleware(BaseHTTPMiddleware):
    """Middleware for rate limiting requests."""
    
    def __init__(self, app: FastAPI, requests_per_minute: int = 60, by_ip: bool = True):
        """
        Initialize the middleware.
        
        Args:
            app: The FastAPI application
            requests_per_minute: Maximum requests per minute
            by_ip: Whether to apply rate limiting per IP address
        """
        super().__init__(app)
        self.requests_per_minute = requests_per_minute
        self.by_ip = by_ip
        self.request_counts: Dict[str, List[float]] = {}
        self.window_size = 60.0  # seconds
    
    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        """
        Apply rate limiting to requests.
        
        Args:
            request: The incoming request
            call_next: The next middleware or route handler
            
        Returns:
            Response: The response
        """
        # Skip rate limiting for some paths (like static files)
        if request.url.path.startswith("/static/"):
            return await call_next(request)
        
        # Get client identifier (IP address or user ID)
        client_id = request.client.host if self.by_ip else "global"
        
        # Check rate limit
        current_time = time.time()
        
        # Clean up old request timestamps
        if client_id in self.request_counts:
            self.request_counts[client_id] = [
                timestamp for timestamp in self.request_counts[client_id]
                if current_time - timestamp < self.window_size
            ]
        else:
            self.request_counts[client_id] = []
        
        # Check if rate limit exceeded
        if len(self.request_counts[client_id]) >= self.requests_per_minute:
            logger.warning(
                f"Rate limit exceeded for {client_id}: {len(self.request_counts[client_id])} "
                f"requests in the last minute"
            )
            
            # Return rate limit error
            error_response = ErrorResponse(
                error="Rate limit exceeded",
                status_code=HTTP_429_TOO_MANY_REQUESTS,
                details={
                    "limit": self.requests_per_minute,
                    "current": len(self.request_counts[client_id]),
                    "reset_after": int(
                        self.window_size - (current_time - min(self.request_counts[client_id]))
                    )
                },
                timestamp=time.strftime("%Y-%m-%d %H:%M:%S UTC", time.gmtime()),
                path=request.url.path
            )
            
            return JSONResponse(
                status_code=HTTP_429_TOO_MANY_REQUESTS,
                content=error_response.dict(),
                headers={"Retry-After": "60"}
            )
        
        # Record the request
        self.request_counts[client_id].append(current_time)
        
        # Process the request
        return await call_next(request)


def configure_middlewares(app: FastAPI) -> None:
    """
    Configure all middlewares for the application.
    
    Args:
        app: The FastAPI application
    """
    # Add error handling middleware
    app.add_middleware(ErrorHandlingMiddleware)
    
    # Add request logging middleware
    app.add_middleware(RequestLoggingMiddleware)
    
    # Add CORS middleware
    app.add_middleware(
        CORSMiddleware,
        allow_origins=os.getenv("CORS_ORIGINS", "http://localhost:8000").split(","),
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    
    # Add rate limiting middleware (if enabled)
    rate_limit_enabled = os.getenv("RATE_LIMIT_ENABLED", "false").lower() == "true"
    if rate_limit_enabled:
        rate_limit = int(os.getenv("RATE_LIMIT", "60"))
        app.add_middleware(RateLimitingMiddleware, requests_per_minute=rate_limit)
    
    logger.info("Application middlewares configured")