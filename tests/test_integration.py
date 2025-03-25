"""
End-to-end integration tests for kairoslms.

This module tests the complete application workflow including:
- Data ingestion from multiple sources
- Status overview generation
- Task prioritization
- LLM-enhanced processing
- API interactions
"""
import os
import pytest
import json
from unittest.mock import patch, MagicMock
from datetime import datetime, timedelta
from fastapi.testclient import TestClient

from src.app import app
from src.db import (
    create_context_document, create_task, create_goal, 
    store_email, store_calendar_event,
    get_task, get_goal
)
from src.status_overview import generate_status_overview
from src.task_prioritization import prioritize_tasks
from src.llm_integration import LLMIntegration


client = TestClient(app)


@pytest.fixture
def mock_db():
    """Fixture for mocking database interactions."""
    # Create mock database entries
    yield


@pytest.fixture
def mock_gmail_client():
    """Fixture for mocking Gmail client."""
    with patch('src.ingestion.email_ingestion.GmailClient') as MockGmailClient:
        mock_client = MagicMock()
        MockGmailClient.return_value = mock_client
        
        # Setup mock emails
        mock_client.fetch_emails.return_value = [
            {
                'message_id': 'email1',
                'subject': 'Project X Update',
                'sender': 'teammate@example.com',
                'recipients': 'me@example.com',
                'received_at': datetime.now() - timedelta(hours=5),
                'content': 'The Project X deadline has been extended by one week.'
            },
            {
                'message_id': 'email2',
                'subject': 'Meeting Reminder',
                'sender': 'calendar@example.com',
                'recipients': 'me@example.com',
                'received_at': datetime.now() - timedelta(hours=2),
                'content': 'Reminder: Team meeting tomorrow at 10 AM.'
            }
        ]
        yield mock_client


@pytest.fixture
def mock_calendar_client():
    """Fixture for mocking Calendar client."""
    with patch('src.ingestion.calendar_ingestion.CalendarClient') as MockCalendarClient:
        mock_client = MagicMock()
        MockCalendarClient.return_value = mock_client
        
        # Setup mock calendar events
        mock_client.fetch_events.return_value = [
            {
                'event_id': 'event1',
                'title': 'Team Meeting',
                'start_time': datetime.now() + timedelta(days=1, hours=10),
                'end_time': datetime.now() + timedelta(days=1, hours=11),
                'location': 'Conference Room A',
                'description': 'Weekly team meeting',
                'attendees': 'teammate1@example.com, teammate2@example.com'
            },
            {
                'event_id': 'event2',
                'title': 'Project Deadline',
                'start_time': datetime.now() + timedelta(days=7),
                'end_time': datetime.now() + timedelta(days=7, hours=1),
                'location': '',
                'description': 'Submit final deliverables',
                'attendees': ''
            }
        ]
        yield mock_client


@pytest.fixture
def mock_todoist_client():
    """Fixture for mocking Todoist client."""
    with patch('src.ingestion.todoist_ingestion.TodoistClient') as MockTodoistClient:
        mock_client = MagicMock()
        MockTodoistClient.return_value = mock_client
        
        # Create mock task class
        class MockTask:
            def __init__(self, task_id, content, priority=4, completed=False, parent_id=None, due=None):
                self.id = task_id
                self.content = content
                self.priority = priority
                self.is_completed = completed
                self.parent_id = parent_id
                self.due = due
        
        # Create mock due date class
        class MockDue:
            def __init__(self, date_str):
                self.date = date_str
                self.datetime = None
        
        # Setup mock tasks
        task1 = MockTask('task1', 'Complete project documentation', 3, False)
        task1.due = MockDue('2023-12-15')
        
        task2 = MockTask('task2', 'Review code changes', 4, False, 'task1')
        
        task3 = MockTask('task3', 'Schedule team meeting', 2, True)
        
        mock_client.fetch_tasks.return_value = [task1, task2, task3]
        yield mock_client


@pytest.fixture
def mock_llm():
    """Fixture for mocking LLM integration."""
    with patch('src.llm_integration.LLMIntegration') as MockLLM:
        mock_llm = MagicMock()
        MockLLM.return_value = mock_llm
        
        # Setup mock responses
        mock_llm.query_llm.return_value = """
        The current status shows good progress on Project X, with the deadline extended by one week.
        
        Key priorities for the next 7 days:
        1. Complete project documentation (high priority)
        2. Review code changes (medium priority)
        3. Prepare for team meeting tomorrow
        
        Potential obstacles:
        - Time constraints due to the upcoming deadline
        - Need to coordinate with team members who may have conflicting schedules
        
        Recommended actions:
        - Schedule focused time for documentation
        - Assign code review to specific team members
        - Prepare agenda for tomorrow's meeting
        """
        
        mock_llm.generate_goal_analysis.return_value = {
            'summary': 'Good progress on the project with extended deadline',
            'next_steps': ['Complete documentation', 'Review code', 'Prepare for meeting'],
            'obstacles': ['Time constraints', 'Coordination challenges'],
            'raw_response': mock_llm.query_llm.return_value
        }
        
        mock_llm.prioritize_tasks.return_value = [
            {'id': 1, 'title': 'Complete project documentation', 'llm_priority': 8},
            {'id': 2, 'title': 'Review code changes', 'llm_priority': 6},
            {'id': 3, 'title': 'Prepare for team meeting', 'llm_priority': 7}
        ]
        
        yield mock_llm


class TestEndToEndWorkflow:
    """Tests for the end-to-end workflow."""
    
    @patch('src.ingestion.email_ingestion.ingest_emails')
    @patch('src.ingestion.calendar_ingestion.ingest_calendar_events')
    @patch('src.ingestion.todoist_ingestion.ingest_todoist_tasks')
    def test_data_ingestion_workflow(self, mock_ingest_todoist, mock_ingest_calendar, mock_ingest_emails, 
                                    mock_gmail_client, mock_calendar_client, mock_todoist_client):
        """Test complete data ingestion workflow."""
        # Set up mock return values
        mock_ingest_emails.return_value = (2, 2)
        mock_ingest_calendar.return_value = (2, 2)
        mock_ingest_todoist.return_value = (3, 3)
        
        # Create a context document
        bio = create_context_document(
            title="User Biography",
            content="User is a software developer working on Project X.",
            document_type="biography"
        )
        
        # Create a goal
        goal = create_goal(
            title="Complete Project X",
            description="Finish all deliverables for Project X",
            importance=9,
            timeframe="monthly"
        )
        
        # Simulate ingestion process
        from src.ingestion.scheduler import run_all_ingestion
        run_all_ingestion()
        
        # Verify mocks were called
        mock_ingest_emails.assert_called_once()
        mock_ingest_calendar.assert_called_once()
        mock_ingest_todoist.assert_called_once()
        
        # Test email endpoint
        response = client.get("/api/ingestion/emails")
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)
        
        # Test calendar endpoint
        response = client.get("/api/ingestion/calendar")
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)
        
        # Test tasks endpoint
        response = client.get("/api/ingestion/tasks")
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)
    
    @patch('src.status_overview.generate_status_overview')
    @patch('src.task_prioritization.prioritize_tasks')
    def test_processing_workflow(self, mock_prioritize, mock_generate_overview, mock_llm):
        """Test the processing workflow."""
        # Setup mock returns
        overview = {
            'id': 1,
            'title': 'Weekly Status Overview',
            'content': 'Project X is on track with the extended deadline.',
            'created_at': datetime.now().isoformat()
        }
        mock_generate_overview.return_value = overview
        
        prioritized_tasks = [
            {'id': 1, 'title': 'Complete documentation', 'priority': 8.5},
            {'id': 2, 'title': 'Review code', 'priority': 7.0}
        ]
        mock_prioritize.return_value = prioritized_tasks
        
        # Test status overview endpoint
        response = client.get("/api/status/overview")
        assert response.status_code == 200
        data = response.json()
        assert 'id' in data
        assert 'title' in data
        assert 'content' in data
        
        # Test prioritized tasks endpoint
        response = client.get("/api/tasks/prioritized")
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)
        assert len(data) > 0
        assert 'priority' in data[0]
    
    def test_ui_endpoints(self):
        """Test the UI endpoints."""
        # Test dashboard page
        response = client.get("/")
        assert response.status_code == 200
        
        # Test chat page
        response = client.get("/chat")
        assert response.status_code == 200
        
        # Test settings page
        response = client.get("/settings")
        assert response.status_code == 200
    
    @patch('src.api.auth.create_access_token')
    def test_authentication_flow(self, mock_create_token):
        """Test the authentication flow."""
        # Setup mock token
        mock_create_token.return_value = "fake_access_token"
        
        # Test login endpoint
        login_data = {
            "username": "testuser",
            "password": "password123"
        }
        response = client.post("/api/auth/login", json=login_data)
        assert response.status_code == 200
        data = response.json()
        assert "access_token" in data
        assert data["access_token"] == "fake_access_token"
        assert data["token_type"] == "bearer"
    
    def test_error_handling(self):
        """Test error handling mechanisms."""
        # Test 404 error
        response = client.get("/nonexistent-endpoint")
        assert response.status_code == 404
        assert "error" in response.json()
        
        # Test validation error
        response = client.post("/api/auth/login", json={"username": "test"})  # Missing password
        assert response.status_code == 422
        assert "error" in response.json()
        assert "details" in response.json()


@pytest.mark.skipif(not os.getenv("RUN_FULL_E2E"), reason="Full E2E tests disabled")
class TestFullE2EWithRealServices:
    """
    Tests using real external services (requires credentials).
    
    These tests are skipped by default and should only be run manually
    when appropriate credentials are available.
    """
    
    def test_gmail_integration(self):
        """Test real Gmail integration."""
        from src.ingestion.email_ingestion import ingest_emails
        total, stored = ingest_emails(days=1)
        assert total >= 0
        assert stored >= 0
    
    def test_calendar_integration(self):
        """Test real calendar integration."""
        from src.ingestion.calendar_ingestion import ingest_calendar_events
        total, stored = ingest_calendar_events(days_past=0, days_future=7)
        assert total >= 0
        assert stored >= 0
    
    def test_todoist_integration(self):
        """Test real Todoist integration."""
        from src.ingestion.todoist_ingestion import ingest_todoist_tasks
        total, stored = ingest_todoist_tasks()
        assert total >= 0
        assert stored >= 0
    
    def test_anthropic_integration(self):
        """Test real Anthropic API integration."""
        llm = LLMIntegration()
        response = llm.query_llm("Hello, this is a test query from kairoslms integration tests.")
        assert response
        assert len(response) > 0