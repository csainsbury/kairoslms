"""
Todoist ingestion module for kairoslms.

This module connects to the Todoist API to fetch and sync tasks and subtasks.
"""
import os
import logging
from datetime import datetime, timedelta
from typing import List, Dict, Any, Optional, Tuple

from todoist_api_python.api import TodoistAPI
from todoist_api_python.models import Task as TodoistTask
from todoist_api_python.models import Project as TodoistProject

from src.db import create_task, update_task, get_task, Task

# Configure logging
logger = logging.getLogger(__name__)

class TodoistClient:
    """Client for interacting with Todoist API."""
    
    def __init__(self, api_token: Optional[str] = None):
        """
        Initialize the Todoist client.
        
        Args:
            api_token: Todoist API token
        """
        self.api_token = api_token or os.getenv("TODOIST_API_KEY")
        self.api = TodoistAPI(self.api_token)
    
    def fetch_tasks(self, include_completed: bool = False) -> List[TodoistTask]:
        """
        Fetch all tasks from Todoist.
        
        Args:
            include_completed: Whether to include completed tasks
            
        Returns:
            List of Todoist tasks
        """
        try:
            tasks = self.api.get_tasks()
            logger.info(f"Fetched {len(tasks)} active tasks from Todoist")
            
            if include_completed:
                # Note: The Python Todoist API doesn't directly support fetching completed tasks
                # This would require using the REST API directly with additional authentication
                logger.warning("Fetching completed tasks is not supported in this version")
            
            return tasks
        except Exception as e:
            logger.error(f"Error fetching tasks from Todoist: {str(e)}")
            return []
    
    def fetch_projects(self) -> List[TodoistProject]:
        """
        Fetch all projects from Todoist.
        
        Returns:
            List of Todoist projects
        """
        try:
            projects = self.api.get_projects()
            logger.info(f"Fetched {len(projects)} projects from Todoist")
            return projects
        except Exception as e:
            logger.error(f"Error fetching projects from Todoist: {str(e)}")
            return []
    
    def create_todoist_task(self, content: str, project_id: Optional[str] = None,
                           parent_id: Optional[str] = None, due_string: Optional[str] = None) -> Optional[TodoistTask]:
        """
        Create a new task in Todoist.
        
        Args:
            content: Task content/title
            project_id: ID of the project to add the task to
            parent_id: ID of the parent task (for creating subtasks)
            due_string: Due date as a string (e.g., "tomorrow", "next Monday")
            
        Returns:
            Created Todoist task, or None if creation failed
        """
        try:
            task_args = {"content": content}
            
            if project_id:
                task_args["project_id"] = project_id
                
            if parent_id:
                task_args["parent_id"] = parent_id
                
            if due_string:
                task_args["due_string"] = due_string
            
            task = self.api.add_task(**task_args)
            logger.info(f"Created Todoist task: {content}")
            return task
        except Exception as e:
            logger.error(f"Error creating Todoist task: {str(e)}")
            return None
    
    def update_todoist_task(self, task_id: str, **kwargs) -> bool:
        """
        Update an existing Todoist task.
        
        Args:
            task_id: ID of the task to update
            **kwargs: Task properties to update
            
        Returns:
            True if update was successful, False otherwise
        """
        try:
            self.api.update_task(task_id=task_id, **kwargs)
            logger.info(f"Updated Todoist task: {task_id}")
            return True
        except Exception as e:
            logger.error(f"Error updating Todoist task {task_id}: {str(e)}")
            return False
    
    def complete_todoist_task(self, task_id: str) -> bool:
        """
        Mark a Todoist task as completed.
        
        Args:
            task_id: ID of the task to complete
            
        Returns:
            True if completion was successful, False otherwise
        """
        try:
            self.api.close_task(task_id=task_id)
            logger.info(f"Completed Todoist task: {task_id}")
            return True
        except Exception as e:
            logger.error(f"Error completing Todoist task {task_id}: {str(e)}")
            return False


def parse_todoist_due_date(due: Any) -> Optional[datetime]:
    """
    Parse Todoist due date into a datetime object.
    
    Args:
        due: Todoist due date object
        
    Returns:
        Parsed datetime or None if parsing fails
    """
    if not due:
        return None
    
    try:
        # For datetime format
        if hasattr(due, 'datetime') and due.datetime:
            return datetime.fromisoformat(due.datetime.replace('Z', '+00:00'))
        # For date format
        elif hasattr(due, 'date') and due.date:
            return datetime.fromisoformat(f"{due.date}T23:59:59")
        return None
    except Exception as e:
        logger.error(f"Error parsing due date: {str(e)}")
        return None


def ingest_todoist_tasks() -> Tuple[int, int]:
    """
    Ingest tasks from Todoist and store them in the database.
    
    Returns:
        Tuple of (total tasks found, tasks stored/updated)
    """
    # Create Todoist client
    todoist_client = TodoistClient()
    
    try:
        # Fetch tasks from Todoist
        todoist_tasks = todoist_client.fetch_tasks()
        
        # Process and store tasks
        processed_count = 0
        for todoist_task in todoist_tasks:
            try:
                # Convert Todoist due date to datetime
                deadline = parse_todoist_due_date(todoist_task.due)
                
                # Check if the task already exists in our database
                existing_task = None
                if todoist_task.id:
                    existing_tasks = [t for t in get_task(None) if hasattr(t, 'todoist_id') and t.todoist_id == todoist_task.id]
                    if existing_tasks:
                        existing_task = existing_tasks[0]
                
                if existing_task:
                    # Update existing task
                    update_task(
                        task_id=existing_task.id,
                        title=todoist_task.content,
                        priority=float(todoist_task.priority) if hasattr(todoist_task, 'priority') else 5.0,
                        deadline=deadline,
                        completed=bool(todoist_task.is_completed) if hasattr(todoist_task, 'is_completed') else False
                    )
                else:
                    # Create new task
                    create_task(
                        title=todoist_task.content,
                        description=None,  # Todoist API doesn't provide a separate description field
                        parent_id=None if not todoist_task.parent_id else todoist_task.parent_id,
                        priority=float(todoist_task.priority) if hasattr(todoist_task, 'priority') else 5.0,
                        deadline=deadline,
                        todoist_id=todoist_task.id
                    )
                
                processed_count += 1
            except Exception as e:
                logger.error(f"Error processing Todoist task {todoist_task.content}: {str(e)}")
                continue
        
        logger.info(f"Processed {processed_count} out of {len(todoist_tasks)} Todoist tasks")
        return len(todoist_tasks), processed_count
        
    except Exception as e:
        logger.error(f"Error in Todoist ingestion process: {str(e)}")
        return 0, 0


def sync_task_to_todoist(task_id: int) -> bool:
    """
    Sync a task from the local database to Todoist.
    
    Args:
        task_id: ID of the local task to sync
        
    Returns:
        True if sync was successful, False otherwise
    """
    # Create Todoist client
    todoist_client = TodoistClient()
    
    try:
        # Fetch the task from the database
        task = get_task(task_id)
        if not task:
            logger.error(f"Task with ID {task_id} not found")
            return False
        
        # Check if the task already has a Todoist ID
        if task.todoist_id:
            # Update existing Todoist task
            update_args = {"content": task.title}
            
            if task.deadline:
                update_args["due_date"] = task.deadline.strftime("%Y-%m-%d")
                
            if task.completed:
                # If the task is completed, complete it in Todoist
                success = todoist_client.complete_todoist_task(task.todoist_id)
            else:
                # Otherwise, update its properties
                success = todoist_client.update_todoist_task(task.todoist_id, **update_args)
            
            if success:
                logger.info(f"Updated task {task.title} in Todoist")
                return True
            else:
                logger.error(f"Failed to update task {task.title} in Todoist")
                return False
        else:
            # Create new Todoist task
            todoist_task = todoist_client.create_todoist_task(
                content=task.title,
                due_string=task.deadline.strftime("%Y-%m-%d") if task.deadline else None,
                parent_id=task.parent.todoist_id if task.parent and hasattr(task.parent, 'todoist_id') else None
            )
            
            if todoist_task:
                # Update local task with Todoist ID
                update_task(
                    task_id=task.id,
                    todoist_id=todoist_task.id
                )
                logger.info(f"Created task {task.title} in Todoist")
                return True
            else:
                logger.error(f"Failed to create task {task.title} in Todoist")
                return False
            
    except Exception as e:
        logger.error(f"Error syncing task {task_id} to Todoist: {str(e)}")
        return False


if __name__ == "__main__":
    # Configure logging for standalone use
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    )
    
    # Ingest Todoist tasks
    total, processed = ingest_todoist_tasks()
    print(f"Todoist ingestion complete. Found {total} tasks, processed {processed}.")