"""
Dashboard API for kairoslms.
"""
from typing import List, Dict, Any, Optional
from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel

from src.db import get_db, execute_query
from src.status_overview import generate_status_overview
from src.task_prioritization import prioritize_tasks, get_prioritized_tasks

router = APIRouter(prefix="/dashboard", tags=["dashboard"])

class Goal(BaseModel):
    """Model for high-level and project-level goals."""
    id: int
    name: str
    description: str
    level: str  # "high" or "project"
    status: str
    priority: int
    
class Task(BaseModel):
    """Model for task data."""
    id: int
    name: str
    description: Optional[str] = None
    goal_id: Optional[int] = None
    priority: int
    deadline: Optional[str] = None
    status: str
    
class ModelSuggestion(BaseModel):
    """Model for LLM-generated suggestions."""
    id: int
    content: str
    category: str
    created_at: str

@router.get("/goals", response_model=List[Goal])
async def get_goals():
    """Get all high-level and project-level goals."""
    try:
        conn = get_db()
        query = "SELECT * FROM goals ORDER BY priority DESC, level DESC"
        goals = execute_query(conn, query)
        return goals
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error fetching goals: {str(e)}")

@router.get("/goals/{goal_id}", response_model=Goal)
async def get_goal(goal_id: int):
    """Get a specific goal by ID."""
    try:
        conn = get_db()
        query = "SELECT * FROM goals WHERE id = ?"
        goals = execute_query(conn, query, (goal_id,))
        if not goals:
            raise HTTPException(status_code=404, detail=f"Goal with ID {goal_id} not found")
        return goals[0]
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error fetching goal: {str(e)}")

@router.get("/tasks", response_model=List[Task])
async def get_tasks(goal_id: Optional[int] = None):
    """Get all tasks, optionally filtered by goal ID."""
    try:
        conn = get_db()
        if goal_id:
            query = "SELECT * FROM tasks WHERE goal_id = ? ORDER BY priority DESC"
            tasks = execute_query(conn, query, (goal_id,))
        else:
            tasks = get_prioritized_tasks()
        return tasks
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error fetching tasks: {str(e)}")

@router.put("/tasks/{task_id}/priority", response_model=Task)
async def update_task_priority(task_id: int, priority: int):
    """Manually update a task's priority."""
    try:
        conn = get_db()
        query = "UPDATE tasks SET priority = ? WHERE id = ? RETURNING *"
        updated_tasks = execute_query(conn, query, (priority, task_id))
        if not updated_tasks:
            raise HTTPException(status_code=404, detail=f"Task with ID {task_id} not found")
        return updated_tasks[0]
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error updating task priority: {str(e)}")

@router.get("/suggestions", response_model=List[ModelSuggestion])
async def get_suggestions():
    """Get recent LLM-generated suggestions."""
    try:
        conn = get_db()
        query = """
        SELECT * FROM model_suggestions 
        ORDER BY created_at DESC 
        LIMIT 10
        """
        suggestions = execute_query(conn, query)
        return suggestions
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error fetching suggestions: {str(e)}")

@router.get("/status-overview", response_model=Dict[str, Any])
async def get_status_overview(goal_id: Optional[int] = None):
    """Get status overview, optionally for a specific goal."""
    try:
        if goal_id:
            conn = get_db()
            query = "SELECT * FROM goals WHERE id = ?"
            goals = execute_query(conn, query, (goal_id,))
            if not goals:
                raise HTTPException(status_code=404, detail=f"Goal with ID {goal_id} not found")
            
            overview = generate_status_overview(goal_id=goal_id)
        else:
            overview = generate_status_overview()
        
        return overview
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error generating status overview: {str(e)}")