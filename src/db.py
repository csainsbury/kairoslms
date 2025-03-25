"""
Database connection module for kairoslms.

This module handles connections, CRUD operations, and transactions with the
PostgreSQL database. It provides functions for working with context documents,
tasks, and status overviews.
"""
import os
import logging
from typing import Dict, List, Optional, Any, Union
from datetime import datetime

from sqlalchemy import create_engine, Column, Integer, String, Text, DateTime, Boolean, Float, ForeignKey
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, relationship
from sqlalchemy.sql import func

# Configure logging
logger = logging.getLogger(__name__)

# Get database connection details from environment variables
DB_USER = os.getenv("DB_USER", "postgres")
DB_PASSWORD = os.getenv("DB_PASSWORD", "postgres")
DB_NAME = os.getenv("DB_NAME", "kairoslms")
DB_HOST = os.getenv("DB_HOST", "localhost")
DB_PORT = os.getenv("DB_PORT", "5432")

# Create database URL
DATABASE_URL = f"postgresql://{DB_USER}:{DB_PASSWORD}@{DB_HOST}:{DB_PORT}/{DB_NAME}"

# Create SQLAlchemy engine
engine = create_engine(DATABASE_URL)

# Create sessionmaker
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# Create base class for models
Base = declarative_base()

class ContextDocument(Base):
    """Model for storing contextual documents like biography or project documentation."""
    __tablename__ = "context_documents"

    id = Column(Integer, primary_key=True, index=True)
    title = Column(String(255), index=True)
    content = Column(Text)
    document_type = Column(String(50), index=True)  # e.g., 'biography', 'project_doc'
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

class Goal(Base):
    """Model for storing high-level goals (HLGs) and project-level goals (PLGs)."""
    __tablename__ = "goals"

    id = Column(Integer, primary_key=True, index=True)
    title = Column(String(255), index=True)
    description = Column(Text)
    goal_type = Column(String(50), index=True)  # 'high_level' or 'project_level'
    parent_id = Column(Integer, ForeignKey("goals.id"), nullable=True)  # For PLGs to reference their parent HLG
    importance = Column(Float)  # 0-10 scale
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    # Relationships
    parent = relationship("Goal", remote_side=[id], backref="subgoals")
    tasks = relationship("Task", back_populates="goal")
    status_overviews = relationship("StatusOverview", back_populates="goal")

class Task(Base):
    """Model for storing tasks and subtasks."""
    __tablename__ = "tasks"

    id = Column(Integer, primary_key=True, index=True)
    title = Column(String(255), index=True)
    description = Column(Text, nullable=True)
    goal_id = Column(Integer, ForeignKey("goals.id"), nullable=True)
    parent_id = Column(Integer, ForeignKey("tasks.id"), nullable=True)  # For subtasks
    priority = Column(Float)  # Calculated priority score
    manual_priority_override = Column(Boolean, default=False)
    manual_priority_value = Column(Float, nullable=True)
    deadline = Column(DateTime(timezone=True), nullable=True)
    completed = Column(Boolean, default=False)
    completed_at = Column(DateTime(timezone=True), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())
    todoist_id = Column(String(100), nullable=True)  # External ID for Todoist integration

    # Relationships
    goal = relationship("Goal", back_populates="tasks")
    parent = relationship("Task", remote_side=[id], backref="subtasks")

class StatusOverview(Base):
    """Model for storing status overviews generated for goals."""
    __tablename__ = "status_overviews"

    id = Column(Integer, primary_key=True, index=True)
    goal_id = Column(Integer, ForeignKey("goals.id"))
    overview = Column(Text)
    obstacles = Column(Text, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    # Relationships
    goal = relationship("Goal", back_populates="status_overviews")

class Email(Base):
    """Model for storing ingested emails."""
    __tablename__ = "emails"

    id = Column(Integer, primary_key=True, index=True)
    subject = Column(String(255))
    sender = Column(String(255))
    recipients = Column(String(1000))
    received_at = Column(DateTime(timezone=True))
    content = Column(Text)
    processed = Column(Boolean, default=False)
    message_id = Column(String(255), unique=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

class CalendarEvent(Base):
    """Model for storing ingested calendar events."""
    __tablename__ = "calendar_events"

    id = Column(Integer, primary_key=True, index=True)
    title = Column(String(255))
    start_time = Column(DateTime(timezone=True))
    end_time = Column(DateTime(timezone=True))
    location = Column(String(255), nullable=True)
    description = Column(Text, nullable=True)
    attendees = Column(String(1000), nullable=True)
    event_id = Column(String(255), unique=True)  # External event ID from Google Calendar
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

class ModelSuggestion(Base):
    """Model for storing LLM-generated suggestions."""
    __tablename__ = "model_suggestions"

    id = Column(Integer, primary_key=True, index=True)
    content = Column(Text)
    category = Column(String(50))  # e.g., 'task', 'goal', 'obstacle'
    goal_id = Column(Integer, ForeignKey("goals.id"), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    # Relationship
    goal = relationship("Goal", backref="suggestions")

class ChatSession(Base):
    """Model for storing chat sessions."""
    __tablename__ = "chat_sessions"

    id = Column(Integer, primary_key=True, index=True)
    title = Column(String(255))
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    # Relationship
    messages = relationship("ChatMessage", back_populates="session", cascade="all, delete-orphan")

class ChatMessage(Base):
    """Model for storing chat messages."""
    __tablename__ = "chat_messages"

    id = Column(Integer, primary_key=True, index=True)
    session_id = Column(Integer, ForeignKey("chat_sessions.id"))
    sender = Column(String(50))  # 'user' or 'system'
    content = Column(Text)
    timestamp = Column(DateTime(timezone=True), server_default=func.now())

    # Relationship
    session = relationship("ChatSession", back_populates="messages")

def get_db():
    """Get a database session."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

def create_tables():
    """Create all tables in the database."""
    Base.metadata.create_all(bind=engine)
    logger.info("Database tables created")

# Context Document Operations
def create_context_document(title: str, content: str, document_type: str) -> ContextDocument:
    """Create a new context document."""
    db = SessionLocal()
    try:
        doc = ContextDocument(
            title=title,
            content=content,
            document_type=document_type
        )
        db.add(doc)
        db.commit()
        db.refresh(doc)
        logger.info(f"Created new context document: {title}")
        return doc
    except Exception as e:
        db.rollback()
        logger.error(f"Error creating context document: {str(e)}")
        raise
    finally:
        db.close()

def get_context_document(doc_id: int) -> Optional[ContextDocument]:
    """Get a context document by ID."""
    db = SessionLocal()
    try:
        return db.query(ContextDocument).filter(ContextDocument.id == doc_id).first()
    finally:
        db.close()

def get_context_documents_by_type(document_type: str) -> List[ContextDocument]:
    """Get all context documents of a specific type."""
    db = SessionLocal()
    try:
        return db.query(ContextDocument).filter(ContextDocument.document_type == document_type).all()
    finally:
        db.close()

def update_context_document(doc_id: int, title: str = None, content: str = None) -> Optional[ContextDocument]:
    """Update a context document."""
    db = SessionLocal()
    try:
        doc = db.query(ContextDocument).filter(ContextDocument.id == doc_id).first()
        if doc is None:
            return None
        
        if title is not None:
            doc.title = title
        if content is not None:
            doc.content = content
        
        db.commit()
        db.refresh(doc)
        logger.info(f"Updated context document: {doc_id}")
        return doc
    except Exception as e:
        db.rollback()
        logger.error(f"Error updating context document: {str(e)}")
        raise
    finally:
        db.close()

# Goal Operations
def create_goal(
    title: str, 
    description: str, 
    goal_type: str,
    importance: float,
    parent_id: Optional[int] = None
) -> Goal:
    """Create a new goal (HLG or PLG)."""
    db = SessionLocal()
    try:
        goal = Goal(
            title=title,
            description=description,
            goal_type=goal_type,
            importance=importance,
            parent_id=parent_id
        )
        db.add(goal)
        db.commit()
        db.refresh(goal)
        logger.info(f"Created new {goal_type} goal: {title}")
        return goal
    except Exception as e:
        db.rollback()
        logger.error(f"Error creating goal: {str(e)}")
        raise
    finally:
        db.close()

def get_goal(goal_id: int) -> Optional[Goal]:
    """Get a goal by ID."""
    db = SessionLocal()
    try:
        return db.query(Goal).filter(Goal.id == goal_id).first()
    finally:
        db.close()

def get_goals_by_type(goal_type: str) -> List[Goal]:
    """Get all goals of a specific type."""
    db = SessionLocal()
    try:
        return db.query(Goal).filter(Goal.goal_type == goal_type).all()
    finally:
        db.close()

def update_goal(
    goal_id: int, 
    title: str = None, 
    description: str = None, 
    importance: float = None
) -> Optional[Goal]:
    """Update a goal."""
    db = SessionLocal()
    try:
        goal = db.query(Goal).filter(Goal.id == goal_id).first()
        if goal is None:
            return None
        
        if title is not None:
            goal.title = title
        if description is not None:
            goal.description = description
        if importance is not None:
            goal.importance = importance
        
        db.commit()
        db.refresh(goal)
        logger.info(f"Updated goal: {goal_id}")
        return goal
    except Exception as e:
        db.rollback()
        logger.error(f"Error updating goal: {str(e)}")
        raise
    finally:
        db.close()

# Task Operations
def create_task(
    title: str,
    description: Optional[str] = None,
    goal_id: Optional[int] = None,
    parent_id: Optional[int] = None,
    priority: float = 5.0,
    deadline: Optional[datetime] = None,
    todoist_id: Optional[str] = None
) -> Task:
    """Create a new task or subtask."""
    db = SessionLocal()
    try:
        task = Task(
            title=title,
            description=description,
            goal_id=goal_id,
            parent_id=parent_id,
            priority=priority,
            deadline=deadline,
            todoist_id=todoist_id
        )
        db.add(task)
        db.commit()
        db.refresh(task)
        logger.info(f"Created new task: {title}")
        return task
    except Exception as e:
        db.rollback()
        logger.error(f"Error creating task: {str(e)}")
        raise
    finally:
        db.close()

def get_task(task_id: int) -> Optional[Task]:
    """Get a task by ID."""
    db = SessionLocal()
    try:
        return db.query(Task).filter(Task.id == task_id).first()
    finally:
        db.close()

def get_tasks_by_goal(goal_id: int) -> List[Task]:
    """Get all tasks associated with a specific goal."""
    db = SessionLocal()
    try:
        return db.query(Task).filter(Task.goal_id == goal_id, Task.parent_id == None).all()
    finally:
        db.close()

def get_subtasks(task_id: int) -> List[Task]:
    """Get all subtasks for a given task."""
    db = SessionLocal()
    try:
        return db.query(Task).filter(Task.parent_id == task_id).all()
    finally:
        db.close()

def update_task(
    task_id: int,
    title: str = None,
    description: str = None,
    priority: float = None,
    manual_priority_override: bool = None,
    manual_priority_value: float = None,
    deadline: datetime = None,
    completed: bool = None
) -> Optional[Task]:
    """Update a task."""
    db = SessionLocal()
    try:
        task = db.query(Task).filter(Task.id == task_id).first()
        if task is None:
            return None
        
        if title is not None:
            task.title = title
        if description is not None:
            task.description = description
        if priority is not None and not task.manual_priority_override:
            task.priority = priority
        if manual_priority_override is not None:
            task.manual_priority_override = manual_priority_override
        if manual_priority_value is not None:
            task.manual_priority_value = manual_priority_value
            if manual_priority_override:
                task.priority = manual_priority_value
        if deadline is not None:
            task.deadline = deadline
        if completed is not None:
            task.completed = completed
            task.completed_at = datetime.now() if completed else None
        
        db.commit()
        db.refresh(task)
        logger.info(f"Updated task: {task_id}")
        return task
    except Exception as e:
        db.rollback()
        logger.error(f"Error updating task: {str(e)}")
        raise
    finally:
        db.close()

# Status Overview Operations
def create_status_overview(goal_id: int, overview: str, obstacles: Optional[str] = None) -> StatusOverview:
    """Create a new status overview for a goal."""
    db = SessionLocal()
    try:
        status = StatusOverview(
            goal_id=goal_id,
            overview=overview,
            obstacles=obstacles
        )
        db.add(status)
        db.commit()
        db.refresh(status)
        logger.info(f"Created new status overview for goal: {goal_id}")
        return status
    except Exception as e:
        db.rollback()
        logger.error(f"Error creating status overview: {str(e)}")
        raise
    finally:
        db.close()

def get_latest_status_overview(goal_id: int) -> Optional[StatusOverview]:
    """Get the most recent status overview for a goal."""
    db = SessionLocal()
    try:
        return db.query(StatusOverview).filter(
            StatusOverview.goal_id == goal_id
        ).order_by(StatusOverview.created_at.desc()).first()
    finally:
        db.close()

# Email and Calendar Operations
def store_email(
    subject: str,
    sender: str,
    recipients: str,
    received_at: datetime,
    content: str,
    message_id: str
) -> Email:
    """Store a parsed email in the database."""
    db = SessionLocal()
    try:
        email = Email(
            subject=subject,
            sender=sender,
            recipients=recipients,
            received_at=received_at,
            content=content,
            message_id=message_id
        )
        db.add(email)
        db.commit()
        db.refresh(email)
        logger.info(f"Stored new email: {subject}")
        return email
    except Exception as e:
        db.rollback()
        logger.error(f"Error storing email: {str(e)}")
        raise
    finally:
        db.close()

def store_calendar_event(
    title: str,
    start_time: datetime,
    end_time: datetime,
    location: Optional[str] = None,
    description: Optional[str] = None,
    attendees: Optional[str] = None,
    event_id: str = None
) -> CalendarEvent:
    """Store a calendar event in the database."""
    db = SessionLocal()
    try:
        event = CalendarEvent(
            title=title,
            start_time=start_time,
            end_time=end_time,
            location=location,
            description=description,
            attendees=attendees,
            event_id=event_id
        )
        db.add(event)
        db.commit()
        db.refresh(event)
        logger.info(f"Stored new calendar event: {title}")
        return event
    except Exception as e:
        db.rollback()
        logger.error(f"Error storing calendar event: {str(e)}")
        raise
    finally:
        db.close()

def get_unprocessed_emails() -> List[Email]:
    """Get all unprocessed emails."""
    db = SessionLocal()
    try:
        return db.query(Email).filter(Email.processed == False).all()
    finally:
        db.close()

def mark_email_as_processed(email_id: int) -> Optional[Email]:
    """Mark an email as processed."""
    db = SessionLocal()
    try:
        email = db.query(Email).filter(Email.id == email_id).first()
        if email:
            email.processed = True
            db.commit()
            db.refresh(email)
            return email
        return None
    except Exception as e:
        db.rollback()
        logger.error(f"Error marking email as processed: {str(e)}")
        raise
    finally:
        db.close()

def get_upcoming_calendar_events(days: int = 7) -> List[CalendarEvent]:
    """Get calendar events for the next few days."""
    from datetime import datetime, timedelta
    
    db = SessionLocal()
    try:
        now = datetime.now()
        future = now + timedelta(days=days)
        return db.query(CalendarEvent).filter(
            CalendarEvent.start_time >= now,
            CalendarEvent.start_time <= future
        ).order_by(CalendarEvent.start_time).all()
    finally:
        db.close()

# Model Suggestion Operations
def create_model_suggestion(content: str, category: str, goal_id: Optional[int] = None) -> ModelSuggestion:
    """Create a new model suggestion."""
    db = SessionLocal()
    try:
        suggestion = ModelSuggestion(
            content=content,
            category=category,
            goal_id=goal_id
        )
        db.add(suggestion)
        db.commit()
        db.refresh(suggestion)
        logger.info(f"Created new model suggestion in category: {category}")
        return suggestion
    except Exception as e:
        db.rollback()
        logger.error(f"Error creating model suggestion: {str(e)}")
        raise
    finally:
        db.close()

def get_recent_model_suggestions(limit: int = 10) -> List[ModelSuggestion]:
    """Get the most recent model suggestions."""
    db = SessionLocal()
    try:
        return db.query(ModelSuggestion).order_by(
            ModelSuggestion.created_at.desc()
        ).limit(limit).all()
    finally:
        db.close()

def get_model_suggestions_by_goal(goal_id: int) -> List[ModelSuggestion]:
    """Get all model suggestions for a specific goal."""
    db = SessionLocal()
    try:
        return db.query(ModelSuggestion).filter(
            ModelSuggestion.goal_id == goal_id
        ).order_by(ModelSuggestion.created_at.desc()).all()
    finally:
        db.close()

# Chat Operations
def create_chat_session(title: str) -> ChatSession:
    """Create a new chat session."""
    db = SessionLocal()
    try:
        session = ChatSession(title=title)
        db.add(session)
        db.commit()
        db.refresh(session)
        logger.info(f"Created new chat session: {title}")
        return session
    except Exception as e:
        db.rollback()
        logger.error(f"Error creating chat session: {str(e)}")
        raise
    finally:
        db.close()

def get_chat_session(session_id: int) -> Optional[ChatSession]:
    """Get a chat session by ID."""
    db = SessionLocal()
    try:
        return db.query(ChatSession).filter(ChatSession.id == session_id).first()
    finally:
        db.close()

def get_chat_sessions() -> List[ChatSession]:
    """Get all chat sessions ordered by most recent update."""
    db = SessionLocal()
    try:
        return db.query(ChatSession).order_by(ChatSession.updated_at.desc()).all()
    finally:
        db.close()

def create_chat_message(session_id: int, sender: str, content: str) -> ChatMessage:
    """Create a new chat message."""
    db = SessionLocal()
    try:
        # If session doesn't exist, create it
        session = db.query(ChatSession).filter(ChatSession.id == session_id).first()
        if not session:
            session = ChatSession(id=session_id, title=f"Chat {datetime.now().isoformat()}")
            db.add(session)
        
        message = ChatMessage(
            session_id=session_id,
            sender=sender,
            content=content
        )
        db.add(message)
        
        # Update session updated_at timestamp
        session.updated_at = datetime.now()
        
        db.commit()
        db.refresh(message)
        logger.info(f"Created new chat message in session: {session_id}")
        return message
    except Exception as e:
        db.rollback()
        logger.error(f"Error creating chat message: {str(e)}")
        raise
    finally:
        db.close()

def get_chat_messages(session_id: int) -> List[ChatMessage]:
    """Get all messages for a chat session."""
    db = SessionLocal()
    try:
        return db.query(ChatMessage).filter(
            ChatMessage.session_id == session_id
        ).order_by(ChatMessage.timestamp.asc()).all()
    finally:
        db.close()

def get_recent_chat_messages(session_id: int, limit: int = 10) -> List[ChatMessage]:
    """Get the most recent messages for a chat session."""
    db = SessionLocal()
    try:
        return db.query(ChatMessage).filter(
            ChatMessage.session_id == session_id
        ).order_by(ChatMessage.timestamp.desc()).limit(limit).all()
    finally:
        db.close()