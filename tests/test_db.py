"""
Unit tests for database operations module.
"""
import os
import pytest
from unittest.mock import patch, MagicMock
from datetime import datetime, timedelta
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, Session
from sqlalchemy.pool import StaticPool

from src.db import (
    Base, get_db, close_db, create_tables,
    ContextDocument, Task, Goal, StatusOverview, Email, CalendarEvent,
    ModelSuggestion, ChatSession, ChatMessage,
    create_context_document, update_context_document, get_context_document,
    create_task, update_task, get_task, delete_task,
    create_goal, update_goal, get_goal, delete_goal,
    store_email, get_emails,
    store_calendar_event, get_calendar_events,
    create_chat_session, add_chat_message, get_chat_sessions, get_chat_messages
)


@pytest.fixture
def test_db():
    """Create a test database."""
    # Create in-memory SQLite database for testing
    engine = create_engine(
        'sqlite:///:memory:',
        connect_args={"check_same_thread": False},
        poolclass=StaticPool
    )
    
    # Create tables
    Base.metadata.create_all(engine)
    
    # Create a session factory
    TestSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    
    # Patch the get_db function to use our test database
    with patch('src.db.SessionLocal', TestSessionLocal):
        # Create a test session
        db = TestSessionLocal()
        
        try:
            yield db
        finally:
            db.close()


@pytest.fixture
def sample_context_document(test_db):
    """Create a sample context document in the test database."""
    document = ContextDocument(
        title="Test Biography",
        content="This is a test biography.",
        document_type="biography",
        created_at=datetime.now(),
        updated_at=datetime.now()
    )
    test_db.add(document)
    test_db.commit()
    test_db.refresh(document)
    return document


@pytest.fixture
def sample_task(test_db):
    """Create a sample task in the test database."""
    task = Task(
        title="Test Task",
        description="This is a test task.",
        created_at=datetime.now(),
        updated_at=datetime.now(),
        priority=5.0,
        completed=False
    )
    test_db.add(task)
    test_db.commit()
    test_db.refresh(task)
    return task


@pytest.fixture
def sample_goal(test_db):
    """Create a sample goal in the test database."""
    goal = Goal(
        title="Test Goal",
        description="This is a test goal.",
        importance=8,
        timeframe="monthly",
        created_at=datetime.now(),
        updated_at=datetime.now()
    )
    test_db.add(goal)
    test_db.commit()
    test_db.refresh(goal)
    return goal


class TestDatabaseConnection:
    """Tests for database connection functions."""
    
    def test_get_db_session(self):
        """Test the database session generator."""
        # Create a mock session class
        mock_session = MagicMock(spec=Session)
        
        # Setup the mock sessionmaker
        mock_sessionmaker = MagicMock()
        mock_sessionmaker.return_value = mock_session
        
        # Patch the SessionLocal
        with patch('src.db.SessionLocal', mock_sessionmaker):
            # Get an instance using the generator
            session = next(get_db())
            
            # Verify the session was created
            mock_sessionmaker.assert_called_once()
            assert session is mock_session
    
    def test_close_db(self):
        """Test closing the database session."""
        # Create a mock session
        mock_session = MagicMock(spec=Session)
        
        # Close the session
        close_db(mock_session)
        
        # Verify close was called
        mock_session.close.assert_called_once()
    
    def test_create_tables(self):
        """Test creating database tables."""
        # Create a mock engine
        mock_engine = MagicMock()
        
        # Patch the engine
        with patch('src.db.engine', mock_engine):
            create_tables()
            
            # Verify create_all was called
            Base.metadata.create_all.assert_called_once_with(bind=mock_engine)


class TestContextDocumentOperations:
    """Tests for context document database operations."""
    
    def test_create_context_document(self, test_db):
        """Test creating a context document."""
        # Create a new document
        doc = create_context_document(
            title="Test Document",
            content="Test content",
            document_type="project"
        )
        
        # Verify the document was created
        assert doc.id is not None
        assert doc.title == "Test Document"
        assert doc.content == "Test content"
        assert doc.document_type == "project"
        assert doc.created_at is not None
        assert doc.updated_at is not None
    
    def test_update_context_document(self, test_db, sample_context_document):
        """Test updating a context document."""
        # Update the document
        doc = update_context_document(
            document_id=sample_context_document.id,
            title="Updated Title",
            content="Updated content"
        )
        
        # Verify the document was updated
        assert doc.id == sample_context_document.id
        assert doc.title == "Updated Title"
        assert doc.content == "Updated content"
        assert doc.document_type == sample_context_document.document_type
        assert doc.updated_at > sample_context_document.updated_at
    
    def test_get_context_document(self, test_db, sample_context_document):
        """Test getting a context document."""
        # Get by ID
        doc = get_context_document(document_id=sample_context_document.id)
        assert doc.id == sample_context_document.id
        assert doc.title == sample_context_document.title
        
        # Get by type
        docs = get_context_document(document_type="biography")
        assert len(docs) > 0
        assert docs[0].document_type == "biography"
        
        # Get all
        all_docs = get_context_document()
        assert len(all_docs) > 0
        
        # Get non-existent document
        non_existent = get_context_document(document_id=9999)
        assert non_existent is None


class TestTaskOperations:
    """Tests for task database operations."""
    
    def test_create_task(self, test_db):
        """Test creating a task."""
        # Create a new task
        task = create_task(
            title="New Task",
            description="Description for new task",
            priority=7.5,
            deadline=datetime.now() + timedelta(days=7)
        )
        
        # Verify the task was created
        assert task.id is not None
        assert task.title == "New Task"
        assert task.description == "Description for new task"
        assert task.priority == 7.5
        assert task.deadline is not None
        assert task.completed is False
        assert task.created_at is not None
    
    def test_update_task(self, test_db, sample_task):
        """Test updating a task."""
        # Update the task
        task = update_task(
            task_id=sample_task.id,
            title="Updated Task",
            priority=8.0,
            completed=True
        )
        
        # Verify the task was updated
        assert task.id == sample_task.id
        assert task.title == "Updated Task"
        assert task.description == sample_task.description
        assert task.priority == 8.0
        assert task.completed is True
        assert task.updated_at > sample_task.updated_at
    
    def test_get_task(self, test_db, sample_task):
        """Test getting a task."""
        # Get by ID
        task = get_task(task_id=sample_task.id)
        assert task.id == sample_task.id
        
        # Get all
        all_tasks = get_task(None)
        assert len(all_tasks) > 0
        
        # Get completed tasks
        update_task(task_id=sample_task.id, completed=True)
        completed = get_task(None, completed=True)
        assert len(completed) > 0
        assert completed[0].completed is True
        
        # Get non-existent task
        non_existent = get_task(task_id=9999)
        assert non_existent is None
    
    def test_delete_task(self, test_db, sample_task):
        """Test deleting a task."""
        # Delete the task
        result = delete_task(task_id=sample_task.id)
        
        # Verify the task was deleted
        assert result is True
        assert get_task(task_id=sample_task.id) is None
        
        # Try to delete non-existent task
        result = delete_task(task_id=9999)
        assert result is False


class TestGoalOperations:
    """Tests for goal database operations."""
    
    def test_create_goal(self, test_db):
        """Test creating a goal."""
        # Create a new goal
        goal = create_goal(
            title="New Goal",
            description="Description for new goal",
            importance=9,
            timeframe="yearly"
        )
        
        # Verify the goal was created
        assert goal.id is not None
        assert goal.title == "New Goal"
        assert goal.description == "Description for new goal"
        assert goal.importance == 9
        assert goal.timeframe == "yearly"
        assert goal.created_at is not None
    
    def test_update_goal(self, test_db, sample_goal):
        """Test updating a goal."""
        # Update the goal
        goal = update_goal(
            goal_id=sample_goal.id,
            title="Updated Goal",
            importance=10
        )
        
        # Verify the goal was updated
        assert goal.id == sample_goal.id
        assert goal.title == "Updated Goal"
        assert goal.description == sample_goal.description
        assert goal.importance == 10
        assert goal.updated_at > sample_goal.updated_at
    
    def test_get_goal(self, test_db, sample_goal):
        """Test getting a goal."""
        # Get by ID
        goal = get_goal(goal_id=sample_goal.id)
        assert goal.id == sample_goal.id
        
        # Get all
        all_goals = get_goal(None)
        assert len(all_goals) > 0
        
        # Get goals by timeframe
        goals_by_timeframe = get_goal(None, timeframe="monthly")
        assert len(goals_by_timeframe) > 0
        assert goals_by_timeframe[0].timeframe == "monthly"
        
        # Get non-existent goal
        non_existent = get_goal(goal_id=9999)
        assert non_existent is None
    
    def test_delete_goal(self, test_db, sample_goal):
        """Test deleting a goal."""
        # Delete the goal
        result = delete_goal(goal_id=sample_goal.id)
        
        # Verify the goal was deleted
        assert result is True
        assert get_goal(goal_id=sample_goal.id) is None
        
        # Try to delete non-existent goal
        result = delete_goal(goal_id=9999)
        assert result is False


class TestEmailOperations:
    """Tests for email database operations."""
    
    def test_store_email(self, test_db):
        """Test storing an email."""
        # Store a new email
        email = store_email(
            subject="Test Email",
            sender="sender@example.com",
            recipients="recipient@example.com",
            received_at=datetime.now(),
            content="Test email content",
            message_id="msg123"
        )
        
        # Verify the email was stored
        assert email.id is not None
        assert email.subject == "Test Email"
        assert email.sender == "sender@example.com"
        assert email.recipients == "recipient@example.com"
        assert email.content == "Test email content"
        assert email.message_id == "msg123"
        assert email.received_at is not None
        assert email.created_at is not None
    
    def test_get_emails(self, test_db):
        """Test getting emails."""
        # Store sample emails
        email1 = store_email(
            subject="Email 1",
            sender="sender1@example.com",
            recipients="recipient1@example.com",
            received_at=datetime.now() - timedelta(days=2),
            content="Content 1",
            message_id="msg1"
        )
        
        email2 = store_email(
            subject="Email 2",
            sender="sender2@example.com",
            recipients="recipient2@example.com",
            received_at=datetime.now() - timedelta(days=1),
            content="Content 2",
            message_id="msg2"
        )
        
        # Get all emails
        all_emails = get_emails()
        assert len(all_emails) >= 2
        
        # Get emails by sender
        sender_emails = get_emails(sender="sender1@example.com")
        assert len(sender_emails) == 1
        assert sender_emails[0].sender == "sender1@example.com"
        
        # Get emails with limit
        limited_emails = get_emails(limit=1)
        assert len(limited_emails) == 1
        
        # Get emails with date range
        date_emails = get_emails(
            start_date=datetime.now() - timedelta(days=3),
            end_date=datetime.now()
        )
        assert len(date_emails) >= 2


class TestCalendarEventOperations:
    """Tests for calendar event database operations."""
    
    def test_store_calendar_event(self, test_db):
        """Test storing a calendar event."""
        # Store a new event
        event = store_calendar_event(
            title="Test Event",
            start_time=datetime.now(),
            end_time=datetime.now() + timedelta(hours=1),
            location="Test Location",
            description="Test description",
            attendees="person1@example.com, person2@example.com",
            event_id="event123"
        )
        
        # Verify the event was stored
        assert event.id is not None
        assert event.title == "Test Event"
        assert event.location == "Test Location"
        assert event.description == "Test description"
        assert event.attendees == "person1@example.com, person2@example.com"
        assert event.event_id == "event123"
        assert event.start_time is not None
        assert event.end_time is not None
        assert event.created_at is not None
    
    def test_get_calendar_events(self, test_db):
        """Test getting calendar events."""
        # Store sample events
        now = datetime.now()
        
        event1 = store_calendar_event(
            title="Event 1",
            start_time=now + timedelta(days=1),
            end_time=now + timedelta(days=1, hours=1),
            location="Location 1",
            description="Description 1",
            attendees="person1@example.com",
            event_id="event1"
        )
        
        event2 = store_calendar_event(
            title="Event 2",
            start_time=now + timedelta(days=2),
            end_time=now + timedelta(days=2, hours=2),
            location="Location 2",
            description="Description 2",
            attendees="person2@example.com",
            event_id="event2"
        )
        
        # Get all events
        all_events = get_calendar_events()
        assert len(all_events) >= 2
        
        # Get events by date range
        date_events = get_calendar_events(
            start_date=now,
            end_date=now + timedelta(days=3)
        )
        assert len(date_events) >= 2
        
        # Get events with limit
        limited_events = get_calendar_events(limit=1)
        assert len(limited_events) == 1


class TestChatOperations:
    """Tests for chat session and message database operations."""
    
    def test_create_chat_session(self, test_db):
        """Test creating a chat session."""
        # Create a new chat session
        session = create_chat_session(
            user_id="test_user",
            title="Test Chat",
            metadata={"purpose": "testing"}
        )
        
        # Verify the session was created
        assert session.id is not None
        assert session.user_id == "test_user"
        assert session.title == "Test Chat"
        assert session.metadata == {"purpose": "testing"}
        assert session.created_at is not None
    
    def test_add_chat_message(self, test_db):
        """Test adding a chat message."""
        # Create a session first
        session = create_chat_session(
            user_id="test_user",
            title="Test Chat"
        )
        
        # Add a message
        message = add_chat_message(
            session_id=session.id,
            role="user",
            content="Hello, this is a test message"
        )
        
        # Verify the message was added
        assert message.id is not None
        assert message.session_id == session.id
        assert message.role == "user"
        assert message.content == "Hello, this is a test message"
        assert message.created_at is not None
        
        # Add an AI message
        ai_message = add_chat_message(
            session_id=session.id,
            role="assistant",
            content="Hello, I'm the assistant",
            metadata={"tokens": 10}
        )
        
        assert ai_message.role == "assistant"
        assert ai_message.metadata == {"tokens": 10}
    
    def test_get_chat_sessions(self, test_db):
        """Test getting chat sessions."""
        # Create sample sessions
        session1 = create_chat_session(
            user_id="user1",
            title="Session 1"
        )
        
        session2 = create_chat_session(
            user_id="user2",
            title="Session 2"
        )
        
        # Get all sessions
        all_sessions = get_chat_sessions()
        assert len(all_sessions) >= 2
        
        # Get sessions by user
        user_sessions = get_chat_sessions(user_id="user1")
        assert len(user_sessions) == 1
        assert user_sessions[0].user_id == "user1"
    
    def test_get_chat_messages(self, test_db):
        """Test getting chat messages."""
        # Create a session
        session = create_chat_session(
            user_id="test_user",
            title="Message Test"
        )
        
        # Add messages
        message1 = add_chat_message(
            session_id=session.id,
            role="user",
            content="Message 1"
        )
        
        message2 = add_chat_message(
            session_id=session.id,
            role="assistant",
            content="Message 2"
        )
        
        # Get messages for the session
        messages = get_chat_messages(session_id=session.id)
        assert len(messages) == 2
        
        # Verify order (most recent last)
        assert messages[0].content == "Message 1"
        assert messages[1].content == "Message 2"