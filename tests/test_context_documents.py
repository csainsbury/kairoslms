"""
Tests for the context documents API.
"""
import pytest
from fastapi.testclient import TestClient
from unittest.mock import patch, MagicMock

from src.app import app
from src.db import ContextDocument

client = TestClient(app)

# Mock the database session and functions
@pytest.fixture
def mock_db_functions():
    with patch("src.api.context_documents.create_context_document") as mock_create, \
         patch("src.api.context_documents.get_context_document") as mock_get, \
         patch("src.api.context_documents.get_context_documents_by_type") as mock_get_by_type, \
         patch("src.api.context_documents.update_context_document") as mock_update:
        
        # Mock return values
        mock_document = MagicMock(spec=ContextDocument)
        mock_document.id = 1
        mock_document.title = "Test Biography"
        mock_document.content = "This is a test biography"
        mock_document.document_type = "biography"
        mock_document.created_at = "2023-01-01T00:00:00"
        mock_document.updated_at = "2023-01-01T00:00:00"
        
        mock_create.return_value = mock_document
        mock_get.return_value = mock_document
        mock_get_by_type.return_value = [mock_document]
        mock_update.return_value = mock_document
        
        yield {
            "create": mock_create,
            "get": mock_get,
            "get_by_type": mock_get_by_type,
            "update": mock_update,
            "mock_document": mock_document
        }

def test_create_document(mock_db_functions):
    """Test creating a new context document."""
    response = client.post(
        "/api/context-documents/",
        json={
            "title": "Test Biography",
            "content": "This is a test biography",
            "document_type": "biography"
        }
    )
    
    assert response.status_code == 201
    assert response.json()["title"] == "Test Biography"
    assert response.json()["content"] == "This is a test biography"
    assert response.json()["document_type"] == "biography"
    
    # Check if create_context_document was called with correct args
    mock_db_functions["create"].assert_called_once_with(
        title="Test Biography",
        content="This is a test biography",
        document_type="biography"
    )

def test_get_document(mock_db_functions):
    """Test getting a specific context document by ID."""
    response = client.get("/api/context-documents/1")
    
    assert response.status_code == 200
    assert response.json()["id"] == 1
    assert response.json()["title"] == "Test Biography"
    
    # Check if get_context_document was called with correct ID
    mock_db_functions["get"].assert_called_once_with(1)

def test_get_document_not_found(mock_db_functions):
    """Test getting a non-existent document."""
    mock_db_functions["get"].return_value = None
    
    response = client.get("/api/context-documents/999")
    
    assert response.status_code == 404
    assert "not found" in response.json()["detail"].lower()

def test_get_documents_by_type(mock_db_functions):
    """Test getting all documents of a specific type."""
    response = client.get("/api/context-documents/?document_type=biography")
    
    assert response.status_code == 200
    assert isinstance(response.json(), list)
    assert len(response.json()) == 1
    assert response.json()[0]["document_type"] == "biography"
    
    # Check if get_context_documents_by_type was called correctly
    mock_db_functions["get_by_type"].assert_called_once_with("biography")

def test_update_document(mock_db_functions):
    """Test updating a document."""
    response = client.put(
        "/api/context-documents/1",
        json={
            "title": "Updated Biography",
            "content": "This biography has been updated"
        }
    )
    
    assert response.status_code == 200
    
    # Check if update_context_document was called with correct args
    mock_db_functions["update"].assert_called_once_with(
        doc_id=1,
        title="Updated Biography",
        content="This biography has been updated"
    )

def test_get_latest_biography(mock_db_functions):
    """Test getting the latest biography document."""
    response = client.get("/api/context-documents/biography/latest")
    
    assert response.status_code == 200
    assert response.json()["document_type"] == "biography"
    
    # Check if get_context_documents_by_type was called correctly
    mock_db_functions["get_by_type"].assert_called_once_with("biography")

def test_get_latest_biography_not_found(mock_db_functions):
    """Test getting the latest biography when none exists."""
    mock_db_functions["get_by_type"].return_value = []
    
    response = client.get("/api/context-documents/biography/latest")
    
    assert response.status_code == 404
    assert "no biography" in response.json()["detail"].lower()