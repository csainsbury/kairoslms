"""
Tests for error handling and logging in kairoslms.
"""
import pytest
import logging
import os
import json
from fastapi.testclient import TestClient

from src.app import app
from src.utils.error_handling import (
    KairosError, DataValidationError, ResourceNotFoundError, 
    ExternalAPIError, AuthenticationError, AuthorizationError
)

client = TestClient(app)

def test_custom_errors():
    """Test that custom errors are properly initialized."""
    # Test base KairosError
    error = KairosError("Test error", 400, {"detail": "test"})
    assert error.message == "Test error"
    assert error.status_code == 400
    assert error.details == {"detail": "test"}
    
    # Test DataValidationError
    error = DataValidationError("Invalid data", {"field": "value"})
    assert error.message == "Invalid data"
    assert error.status_code == 400
    assert error.details == {"field": "value"}
    
    # Test ResourceNotFoundError
    error = ResourceNotFoundError("User", 123)
    assert error.message == "User with ID 123 not found"
    assert error.status_code == 404
    
    # Test ExternalAPIError
    error = ExternalAPIError("Gmail", "Connection refused", 503, {"retry_after": 30})
    assert error.api_name == "Gmail"
    assert "Gmail API error" in error.message
    assert error.status_code == 503
    assert "retry_after" in error.details
    
    # Test AuthenticationError
    error = AuthenticationError()
    assert "Authentication failed" in error.message
    assert error.status_code == 401
    
    # Test AuthorizationError
    error = AuthorizationError("Not allowed")
    assert "Not allowed" in error.message
    assert error.status_code == 403


def test_http_error_handling():
    """Test HTTP error handling."""
    # Test 404 error
    response = client.get("/nonexistent-endpoint")
    assert response.status_code == 404
    assert "error" in response.json()
    assert response.json()["status_code"] == 404
    
    # Test method not allowed
    response = client.post("/health")
    assert response.status_code == 405
    assert "error" in response.json()
    assert response.json()["status_code"] == 405


def test_validation_error_handling():
    """Test validation error handling."""
    # Create a test endpoint that requires validation
    @app.post("/api/test-validation")
    async def test_validation(name: str, age: int):
        return {"name": name, "age": age}
    
    # Test missing required field
    response = client.post("/api/test-validation", json={"name": "test"})
    assert response.status_code == 422
    assert "error" in response.json()
    assert response.json()["status_code"] == 422
    assert "details" in response.json()
    
    # Test invalid field type
    response = client.post("/api/test-validation", json={"name": "test", "age": "not_a_number"})
    assert response.status_code == 422
    assert "error" in response.json()
    assert "details" in response.json()


def test_custom_error_handling():
    """Test custom KairosError handling."""
    # Create test endpoints that raise custom errors
    @app.get("/api/test-validation-error")
    async def test_validation_error():
        raise DataValidationError("Invalid input data", {"field": "Must be a number"})
    
    @app.get("/api/test-not-found-error")
    async def test_not_found_error():
        raise ResourceNotFoundError("Document", 42)
    
    @app.get("/api/test-auth-error")
    async def test_auth_error():
        raise AuthenticationError("Invalid credentials")
    
    # Test validation error
    response = client.get("/api/test-validation-error")
    assert response.status_code == 400
    assert response.json()["error"] == "Invalid input data"
    assert response.json()["details"] == {"field": "Must be a number"}
    
    # Test not found error
    response = client.get("/api/test-not-found-error")
    assert response.status_code == 404
    assert "Document with ID 42 not found" in response.json()["error"]
    
    # Test auth error
    response = client.get("/api/test-auth-error")
    assert response.status_code == 401
    assert "Invalid credentials" in response.json()["error"]


def test_logging_json_formatter(tmpdir):
    """Test the JSON formatting of logs."""
    # Create a temporary log file
    log_file = tmpdir.join("test.log")
    
    # Configure logging
    from src.utils.logging import JsonFormatter
    
    logger = logging.getLogger("test")
    logger.setLevel(logging.INFO)
    
    handler = logging.FileHandler(log_file)
    handler.setFormatter(JsonFormatter())
    logger.addHandler(handler)
    
    # Log some messages
    logger.info("Test info message", extra={"user_id": 123})
    logger.error("Test error message", extra={"request_id": "abc123"})
    
    # Test exception logging
    try:
        raise ValueError("Test exception")
    except ValueError:
        logger.exception("Exception occurred")
    
    # Read the log file
    with open(log_file) as f:
        log_lines = f.readlines()
    
    # Parse JSON logs
    logs = [json.loads(line) for line in log_lines]
    
    # Check info log
    assert logs[0]["level"] == "INFO"
    assert logs[0]["message"] == "Test info message"
    assert logs[0]["user_id"] == 123
    
    # Check error log
    assert logs[1]["level"] == "ERROR"
    assert logs[1]["message"] == "Test error message"
    assert logs[1]["request_id"] == "abc123"
    
    # Check exception log
    assert logs[2]["level"] == "ERROR"
    assert logs[2]["message"] == "Exception occurred"
    assert "exception" in logs[2]
    assert logs[2]["exception"]["type"] == "ValueError"
    assert logs[2]["exception"]["message"] == "Test exception"
    assert isinstance(logs[2]["exception"]["traceback"], list)


def test_retry_mechanism():
    """Test retry mechanism with exponential backoff."""
    from src.utils.retries import retry, RetryableError
    
    # Track number of attempts
    attempts = 0
    
    # Create a function that fails for the first two attempts
    @retry(max_tries=3, backoff_factor=0.1)  # Fast retry for testing
    def flaky_function():
        nonlocal attempts
        attempts += 1
        if attempts < 3:
            raise RetryableError("Temporary failure")
        return "success"
    
    # Call the function and check that it eventually succeeds
    result = flaky_function()
    assert result == "success"
    assert attempts == 3  # Should have taken 3 attempts
    
    # Reset attempts for next test
    attempts = 0
    
    # Test that non-retryable exceptions are not retried
    @retry(max_tries=3, backoff_factor=0.1)
    def non_retryable_function():
        nonlocal attempts
        attempts += 1
        raise ValueError("Non-retryable error")
    
    # Call the function and check that it fails immediately
    with pytest.raises(ValueError):
        non_retryable_function()
    
    assert attempts == 1  # Should have only attempted once


def test_notification_system():
    """Test the notification system."""
    from src.utils.notifications import (
        Notification, add_notification, get_user_notifications,
        mark_notification_read, clear_notifications
    )
    
    # Add a notification
    notification = Notification(
        type="info",
        title="Test Notification",
        message="This is a test notification"
    )
    
    # Add notification for a user
    added = add_notification("test_user", notification)
    
    # Check that the notification has timestamp and ID
    assert added.timestamp is not None
    assert added.id is not None
    
    # Get notifications for the user
    notifications = get_user_notifications("test_user")
    assert len(notifications) == 1
    assert notifications[0].title == "Test Notification"
    assert not notifications[0].read
    
    # Mark the notification as read
    success = mark_notification_read("test_user", added.id)
    assert success
    
    # Get unread notifications
    unread = get_user_notifications("test_user", unread_only=True)
    assert len(unread) == 0
    
    # Add another notification
    add_notification("test_user", Notification(
        type="warning",
        title="Another Notification",
        message="Another test"
    ))
    
    # Clear all notifications
    count = clear_notifications("test_user")
    assert count == 2
    
    # Get notifications after clearing
    notifications = get_user_notifications("test_user")
    assert len(notifications) == 0