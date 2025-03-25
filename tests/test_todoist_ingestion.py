"""
Unit tests for Todoist ingestion module.
"""
import os
import pytest
from unittest.mock import patch, MagicMock, call
from datetime import datetime, timedelta

from todoist_api_python.models import Task as TodoistTask
from todoist_api_python.models import Due as TodoistDue
from src.ingestion.todoist_ingestion import TodoistClient, ingest_todoist_tasks, sync_task_to_todoist, parse_todoist_due_date


@pytest.fixture
def mock_todoist_task():
    """Fixture for creating a mock Todoist task."""
    # Create a mock TodoistTask
    task = MagicMock(spec=TodoistTask)
    task.id = "12345"
    task.content = "Test Task"
    task.priority = 3
    task.is_completed = False
    task.parent_id = None
    
    # Mock due date
    due = MagicMock(spec=TodoistDue)
    due.date = "2023-01-01"
    due.datetime = "2023-01-01T23:59:59Z"
    task.due = due
    
    return task


@pytest.fixture
def todoist_client():
    """Fixture for creating a TodoistClient instance with mocked API."""
    with patch('todoist_api_python.api.TodoistAPI') as MockTodoistAPI:
        mock_api = MagicMock()
        MockTodoistAPI.return_value = mock_api
        client = TodoistClient(api_token="fake_token")
        yield client


class TestTodoistClient:
    """Tests for the TodoistClient class."""
    
    def test_init(self):
        """Test initialization of TodoistClient."""
        with patch.dict(os.environ, {"TODOIST_API_KEY": "env_token"}):
            client = TodoistClient()
            assert client.api_token == "env_token"
        
        client = TodoistClient(api_token="custom_token")
        assert client.api_token == "custom_token"
    
    def test_fetch_tasks(self, todoist_client, mock_todoist_task):
        """Test fetching tasks."""
        # Setup mock return value
        todoist_client.api.get_tasks.return_value = [mock_todoist_task]
        
        # Call the method
        tasks = todoist_client.fetch_tasks()
        
        # Assertions
        assert len(tasks) == 1
        assert tasks[0].id == "12345"
        assert tasks[0].content == "Test Task"
        todoist_client.api.get_tasks.assert_called_once()
    
    def test_fetch_tasks_with_error(self, todoist_client):
        """Test handling errors when fetching tasks."""
        # Setup mock to raise an exception
        todoist_client.api.get_tasks.side_effect = Exception("API error")
        
        # Call the method
        tasks = todoist_client.fetch_tasks()
        
        # Assertions
        assert tasks == []
        todoist_client.api.get_tasks.assert_called_once()
    
    def test_fetch_projects(self, todoist_client):
        """Test fetching projects."""
        # Setup mock return value
        mock_project = MagicMock()
        mock_project.id = "p1"
        mock_project.name = "Test Project"
        todoist_client.api.get_projects.return_value = [mock_project]
        
        # Call the method
        projects = todoist_client.fetch_projects()
        
        # Assertions
        assert len(projects) == 1
        assert projects[0].id == "p1"
        assert projects[0].name == "Test Project"
        todoist_client.api.get_projects.assert_called_once()
    
    def test_fetch_projects_with_error(self, todoist_client):
        """Test handling errors when fetching projects."""
        # Setup mock to raise an exception
        todoist_client.api.get_projects.side_effect = Exception("API error")
        
        # Call the method
        projects = todoist_client.fetch_projects()
        
        # Assertions
        assert projects == []
        todoist_client.api.get_projects.assert_called_once()
    
    def test_create_todoist_task(self, todoist_client, mock_todoist_task):
        """Test creating a Todoist task."""
        # Setup mock
        todoist_client.api.add_task.return_value = mock_todoist_task
        
        # Call the method with various parameters
        task = todoist_client.create_todoist_task(
            content="New Task",
            project_id="p1",
            parent_id="12345",
            due_string="tomorrow"
        )
        
        # Assertions
        assert task is mock_todoist_task
        todoist_client.api.add_task.assert_called_once_with(
            content="New Task",
            project_id="p1",
            parent_id="12345",
            due_string="tomorrow"
        )
    
    def test_create_todoist_task_minimal(self, todoist_client, mock_todoist_task):
        """Test creating a minimal Todoist task."""
        # Setup mock
        todoist_client.api.add_task.return_value = mock_todoist_task
        
        # Call the method with only required parameters
        task = todoist_client.create_todoist_task(content="New Task")
        
        # Assertions
        assert task is mock_todoist_task
        todoist_client.api.add_task.assert_called_once_with(content="New Task")
    
    def test_create_todoist_task_with_error(self, todoist_client):
        """Test handling errors when creating a task."""
        # Setup mock to raise an exception
        todoist_client.api.add_task.side_effect = Exception("API error")
        
        # Call the method
        task = todoist_client.create_todoist_task(content="New Task")
        
        # Assertions
        assert task is None
        todoist_client.api.add_task.assert_called_once()
    
    def test_update_todoist_task(self, todoist_client):
        """Test updating a Todoist task."""
        # Call the method
        result = todoist_client.update_todoist_task(
            task_id="12345",
            content="Updated Task",
            due_string="next week"
        )
        
        # Assertions
        assert result is True
        todoist_client.api.update_task.assert_called_once_with(
            task_id="12345",
            content="Updated Task",
            due_string="next week"
        )
    
    def test_update_todoist_task_with_error(self, todoist_client):
        """Test handling errors when updating a task."""
        # Setup mock to raise an exception
        todoist_client.api.update_task.side_effect = Exception("API error")
        
        # Call the method
        result = todoist_client.update_todoist_task(task_id="12345", content="Updated Task")
        
        # Assertions
        assert result is False
        todoist_client.api.update_task.assert_called_once()
    
    def test_complete_todoist_task(self, todoist_client):
        """Test completing a Todoist task."""
        # Call the method
        result = todoist_client.complete_todoist_task(task_id="12345")
        
        # Assertions
        assert result is True
        todoist_client.api.close_task.assert_called_once_with(task_id="12345")
    
    def test_complete_todoist_task_with_error(self, todoist_client):
        """Test handling errors when completing a task."""
        # Setup mock to raise an exception
        todoist_client.api.close_task.side_effect = Exception("API error")
        
        # Call the method
        result = todoist_client.complete_todoist_task(task_id="12345")
        
        # Assertions
        assert result is False
        todoist_client.api.close_task.assert_called_once()


class TestParseTodoistDueDate:
    """Tests for the parse_todoist_due_date function."""
    
    def test_parse_due_date_datetime(self):
        """Test parsing a due date with datetime."""
        # Create a mock due date with datetime
        due = MagicMock()
        due.datetime = "2023-01-01T12:00:00Z"
        due.date = "2023-01-01"
        
        # Parse the due date
        result = parse_todoist_due_date(due)
        
        # Assertions
        assert result is not None
        assert result.year == 2023
        assert result.month == 1
        assert result.day == 1
        assert result.hour == 12
        assert result.minute == 0
    
    def test_parse_due_date_date_only(self):
        """Test parsing a due date with date only."""
        # Create a mock due date with date only
        due = MagicMock()
        due.datetime = None
        due.date = "2023-01-01"
        
        # Parse the due date
        result = parse_todoist_due_date(due)
        
        # Assertions
        assert result is not None
        assert result.year == 2023
        assert result.month == 1
        assert result.day == 1
        assert result.hour == 23
        assert result.minute == 59
    
    def test_parse_due_date_none(self):
        """Test parsing a None due date."""
        # Parse a None due date
        result = parse_todoist_due_date(None)
        
        # Assertions
        assert result is None
    
    def test_parse_due_date_invalid(self):
        """Test parsing an invalid due date."""
        # Create a mock due date with invalid format
        due = MagicMock()
        due.datetime = "not-a-date"
        due.date = None
        
        # Parse the due date
        result = parse_todoist_due_date(due)
        
        # Assertions
        assert result is None


class TestIngestTodoistTasks:
    """Tests for the ingest_todoist_tasks function."""
    
    @patch('src.ingestion.todoist_ingestion.TodoistClient')
    @patch('src.ingestion.todoist_ingestion.get_task')
    @patch('src.ingestion.todoist_ingestion.create_task')
    @patch('src.ingestion.todoist_ingestion.update_task')
    def test_ingest_tasks_new(self, mock_update_task, mock_create_task, mock_get_task, MockTodoistClient):
        """Test ingesting new tasks from Todoist."""
        # Setup mock client
        mock_client = MagicMock()
        MockTodoistClient.return_value = mock_client
        
        # Create mock tasks
        task1 = MagicMock()
        task1.id = "t1"
        task1.content = "Task 1"
        task1.priority = 3
        task1.is_completed = False
        task1.parent_id = None
        task1.due = None
        
        task2 = MagicMock()
        task2.id = "t2"
        task2.content = "Task 2"
        task2.priority = 4
        task2.is_completed = True
        task2.parent_id = "t1"
        due = MagicMock()
        due.date = "2023-01-01"
        due.datetime = None
        task2.due = due
        
        # Setup mock client to return the tasks
        mock_client.fetch_tasks.return_value = [task1, task2]
        
        # Setup mock get_task to return no existing tasks
        mock_get_task.return_value = []
        
        # Call the function
        total, processed = ingest_todoist_tasks()
        
        # Assertions
        assert total == 2
        assert processed == 2
        mock_client.fetch_tasks.assert_called_once()
        
        # Both tasks should be created as new
        mock_create_task.assert_has_calls([
            call(
                title="Task 1",
                description=None,
                parent_id=None,
                priority=3.0,
                deadline=None,
                todoist_id="t1"
            ),
            call(
                title="Task 2",
                description=None,
                parent_id="t1",
                priority=4.0,
                deadline=pytest.approx(datetime(2023, 1, 1, 23, 59, 59), abs=timedelta(seconds=1)),
                todoist_id="t2"
            )
        ])
    
    @patch('src.ingestion.todoist_ingestion.TodoistClient')
    @patch('src.ingestion.todoist_ingestion.get_task')
    @patch('src.ingestion.todoist_ingestion.create_task')
    @patch('src.ingestion.todoist_ingestion.update_task')
    def test_ingest_tasks_existing(self, mock_update_task, mock_create_task, mock_get_task, MockTodoistClient):
        """Test ingesting existing tasks from Todoist."""
        # Setup mock client
        mock_client = MagicMock()
        MockTodoistClient.return_value = mock_client
        
        # Create mock task
        task = MagicMock()
        task.id = "t1"
        task.content = "Task 1"
        task.priority = 3
        task.is_completed = True
        task.parent_id = None
        task.due = None
        
        # Setup mock client to return the task
        mock_client.fetch_tasks.return_value = [task]
        
        # Setup mock get_task to return an existing task
        existing_task = MagicMock()
        existing_task.id = 1
        existing_task.todoist_id = "t1"
        mock_get_task.return_value = [existing_task]
        
        # Call the function
        total, processed = ingest_todoist_tasks()
        
        # Assertions
        assert total == 1
        assert processed == 1
        mock_client.fetch_tasks.assert_called_once()
        
        # The task should be updated, not created
        mock_update_task.assert_called_once_with(
            task_id=1,
            title="Task 1",
            priority=3.0,
            deadline=None,
            completed=True
        )
        mock_create_task.assert_not_called()
    
    @patch('src.ingestion.todoist_ingestion.TodoistClient')
    def test_ingest_tasks_fetch_error(self, MockTodoistClient):
        """Test error handling when fetching tasks."""
        # Setup mock client
        mock_client = MagicMock()
        MockTodoistClient.return_value = mock_client
        
        # Setup mock client to raise an exception
        mock_client.fetch_tasks.side_effect = Exception("API error")
        
        # Call the function
        total, processed = ingest_todoist_tasks()
        
        # Assertions
        assert total == 0
        assert processed == 0
        mock_client.fetch_tasks.assert_called_once()


class TestSyncTaskToTodoist:
    """Tests for the sync_task_to_todoist function."""
    
    @patch('src.ingestion.todoist_ingestion.TodoistClient')
    @patch('src.ingestion.todoist_ingestion.get_task')
    @patch('src.ingestion.todoist_ingestion.update_task')
    def test_sync_task_new(self, mock_update_task, mock_get_task, MockTodoistClient):
        """Test syncing a new task to Todoist."""
        # Setup mock client
        mock_client = MagicMock()
        MockTodoistClient.return_value = mock_client
        
        # Setup mock task to return
        task = MagicMock()
        task.id = 1
        task.title = "Test Task"
        task.todoist_id = None
        task.deadline = datetime(2023, 1, 1)
        task.completed = False
        task.parent = None
        mock_get_task.return_value = task
        
        # Setup mock client to return a new Todoist task
        todoist_task = MagicMock()
        todoist_task.id = "t1"
        mock_client.create_todoist_task.return_value = todoist_task
        
        # Call the function
        result = sync_task_to_todoist(task_id=1)
        
        # Assertions
        assert result is True
        mock_get_task.assert_called_once_with(1)
        mock_client.create_todoist_task.assert_called_once_with(
            content="Test Task",
            due_string="2023-01-01",
            parent_id=None
        )
        mock_update_task.assert_called_once_with(
            task_id=1,
            todoist_id="t1"
        )
    
    @patch('src.ingestion.todoist_ingestion.TodoistClient')
    @patch('src.ingestion.todoist_ingestion.get_task')
    def test_sync_task_existing_incomplete(self, mock_get_task, MockTodoistClient):
        """Test syncing an existing incomplete task to Todoist."""
        # Setup mock client
        mock_client = MagicMock()
        MockTodoistClient.return_value = mock_client
        
        # Setup mock task to return
        task = MagicMock()
        task.id = 1
        task.title = "Test Task"
        task.todoist_id = "t1"
        task.deadline = datetime(2023, 1, 1)
        task.completed = False
        mock_get_task.return_value = task
        
        # Setup mock client to return success
        mock_client.update_todoist_task.return_value = True
        
        # Call the function
        result = sync_task_to_todoist(task_id=1)
        
        # Assertions
        assert result is True
        mock_get_task.assert_called_once_with(1)
        mock_client.update_todoist_task.assert_called_once_with(
            "t1",
            content="Test Task",
            due_date="2023-01-01"
        )
        mock_client.complete_todoist_task.assert_not_called()
    
    @patch('src.ingestion.todoist_ingestion.TodoistClient')
    @patch('src.ingestion.todoist_ingestion.get_task')
    def test_sync_task_existing_completed(self, mock_get_task, MockTodoistClient):
        """Test syncing an existing completed task to Todoist."""
        # Setup mock client
        mock_client = MagicMock()
        MockTodoistClient.return_value = mock_client
        
        # Setup mock task to return
        task = MagicMock()
        task.id = 1
        task.title = "Test Task"
        task.todoist_id = "t1"
        task.deadline = None
        task.completed = True
        mock_get_task.return_value = task
        
        # Setup mock client to return success
        mock_client.complete_todoist_task.return_value = True
        
        # Call the function
        result = sync_task_to_todoist(task_id=1)
        
        # Assertions
        assert result is True
        mock_get_task.assert_called_once_with(1)
        mock_client.complete_todoist_task.assert_called_once_with("t1")
        mock_client.update_todoist_task.assert_not_called()
    
    @patch('src.ingestion.todoist_ingestion.TodoistClient')
    @patch('src.ingestion.todoist_ingestion.get_task')
    def test_sync_task_not_found(self, mock_get_task, MockTodoistClient):
        """Test syncing a non-existent task."""
        # Setup mock task to return None
        mock_get_task.return_value = None
        
        # Call the function
        result = sync_task_to_todoist(task_id=1)
        
        # Assertions
        assert result is False
        mock_get_task.assert_called_once_with(1)
    
    @patch('src.ingestion.todoist_ingestion.TodoistClient')
    @patch('src.ingestion.todoist_ingestion.get_task')
    def test_sync_task_api_error(self, mock_get_task, MockTodoistClient):
        """Test error handling with API errors."""
        # Setup mock client
        mock_client = MagicMock()
        MockTodoistClient.return_value = mock_client
        
        # Setup mock task to return
        task = MagicMock()
        task.id = 1
        task.title = "Test Task"
        task.todoist_id = "t1"
        task.deadline = None
        task.completed = True
        mock_get_task.return_value = task
        
        # Setup mock client to raise an exception
        mock_client.complete_todoist_task.side_effect = Exception("API error")
        
        # Call the function
        result = sync_task_to_todoist(task_id=1)
        
        # Assertions
        assert result is False
        mock_get_task.assert_called_once_with(1)
        mock_client.complete_todoist_task.assert_called_once()