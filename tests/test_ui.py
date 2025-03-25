"""
Tests for the UI components of kairoslms.
"""
import pytest
from fastapi.testclient import TestClient
from src.app import app

client = TestClient(app)

def test_dashboard_route():
    """Test that the dashboard route returns a 200 status code."""
    response = client.get("/")
    assert response.status_code == 200
    assert "Kairos LMS - Dashboard" in response.text

def test_chat_route():
    """Test that the chat route returns a 200 status code."""
    response = client.get("/chat")
    assert response.status_code == 200
    assert "Kairos LMS - Chat" in response.text

def test_settings_route():
    """Test that the settings route returns a 200 status code."""
    response = client.get("/settings")
    assert response.status_code == 200
    assert "Kairos LMS - Settings" in response.text

def test_health_check():
    """Test the health check endpoint."""
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "healthy"}

def test_dashboard_api():
    """Test the dashboard API endpoints."""
    # Test goals endpoint
    response = client.get("/api/dashboard/goals")
    assert response.status_code in [200, 404]  # 404 is acceptable if no goals exist yet
    
    # Test tasks endpoint
    response = client.get("/api/dashboard/tasks")
    assert response.status_code in [200, 404]  # 404 is acceptable if no tasks exist yet
    
    # Test status overview endpoint
    response = client.get("/api/dashboard/status-overview")
    assert response.status_code in [200, 404]  # 404 is acceptable if no status overview exists yet

def test_chat_api():
    """Test the chat API endpoints."""
    # Test chat sessions endpoint
    response = client.get("/api/chat/sessions")
    assert response.status_code in [200, 404]  # 404 is acceptable if no sessions exist yet

def test_settings_api():
    """Test the settings API endpoints."""
    # Test scheduling settings endpoint
    response = client.get("/api/settings/scheduling")
    assert response.status_code == 200
    assert "email_ingestion_interval_minutes" in response.json()
    assert "calendar_ingestion_interval_minutes" in response.json()
    assert "todoist_ingestion_interval_minutes" in response.json()
    assert "status_overview_interval_hours" in response.json()
    assert "task_prioritization_interval_minutes" in response.json()
    assert "llm_enhanced_processing_interval_hours" in response.json()
    
    # Test system status endpoint
    response = client.get("/api/settings/status")
    assert response.status_code == 200
    assert "services" in response.json()
    assert "apis" in response.json()
    assert "jobs" in response.json()