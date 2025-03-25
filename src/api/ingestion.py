"""
API endpoints for managing data ingestion.
"""
from typing import Dict, Any, List
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from src.ingestion.scheduler import get_scheduler
from src.ingestion.email_ingestion import ingest_emails
from src.ingestion.calendar_ingestion import ingest_calendar_events
from src.ingestion.todoist_ingestion import ingest_todoist_tasks, sync_task_to_todoist

# Create router
router = APIRouter(prefix="/ingestion", tags=["ingestion"])

# Pydantic models for request and response
class EmailIngestionRequest(BaseModel):
    """Request model for manually triggering email ingestion."""
    days: int = Field(1, description="Number of days of emails to fetch")

class CalendarIngestionRequest(BaseModel):
    """Request model for manually triggering calendar ingestion."""
    days_past: int = Field(0, description="Number of days in the past to fetch events for")
    days_future: int = Field(30, description="Number of days in the future to fetch events for")

class TaskSyncRequest(BaseModel):
    """Request model for syncing a task to Todoist."""
    task_id: int = Field(..., description="ID of the task to sync with Todoist")

class JobResponse(BaseModel):
    """Response model for job information."""
    id: str
    name: str
    next_run_time: str = None
    status: Dict[str, Any] = {}

class IngestionResponse(BaseModel):
    """Response model for ingestion operations."""
    success: bool
    message: str
    result: Any = None

# API endpoints
@router.post("/emails", response_model=IngestionResponse)
async def trigger_email_ingestion(request: EmailIngestionRequest):
    """
    Manually trigger email ingestion.
    
    This endpoint will fetch and process emails from the configured Gmail account
    for the specified number of days.
    """
    try:
        result = ingest_emails(days=request.days)
        return {
            "success": True,
            "message": f"Email ingestion completed. Found {result[0]} emails, stored {result[1]}.",
            "result": result
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error triggering email ingestion: {str(e)}")

@router.post("/calendar", response_model=IngestionResponse)
async def trigger_calendar_ingestion(request: CalendarIngestionRequest):
    """
    Manually trigger calendar ingestion.
    
    This endpoint will fetch and process calendar events from Google Calendar
    for the specified time range.
    """
    try:
        result = ingest_calendar_events(days_past=request.days_past, days_future=request.days_future)
        return {
            "success": True,
            "message": f"Calendar ingestion completed. Found {result[0]} events, stored {result[1]}.",
            "result": result
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error triggering calendar ingestion: {str(e)}")

@router.post("/todoist", response_model=IngestionResponse)
async def trigger_todoist_ingestion():
    """
    Manually trigger Todoist ingestion.
    
    This endpoint will fetch and process tasks from Todoist.
    """
    try:
        result = ingest_todoist_tasks()
        return {
            "success": True,
            "message": f"Todoist ingestion completed. Found {result[0]} tasks, processed {result[1]}.",
            "result": result
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error triggering Todoist ingestion: {str(e)}")

@router.post("/sync-task", response_model=IngestionResponse)
async def sync_task(request: TaskSyncRequest):
    """
    Sync a task to Todoist.
    
    This endpoint will sync a local task with Todoist, creating or updating the task as needed.
    """
    try:
        result = sync_task_to_todoist(task_id=request.task_id)
        if result:
            return {
                "success": True,
                "message": f"Task {request.task_id} successfully synced to Todoist.",
                "result": result
            }
        else:
            return {
                "success": False,
                "message": f"Failed to sync task {request.task_id} to Todoist.",
                "result": result
            }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error syncing task to Todoist: {str(e)}")

@router.get("/jobs", response_model=List[JobResponse])
async def get_ingestion_jobs():
    """
    Get all scheduled ingestion jobs.
    
    This endpoint returns information about all currently scheduled ingestion jobs,
    including when they will next run and their status.
    """
    scheduler = get_scheduler()
    return scheduler.get_jobs()

@router.post("/job/email", response_model=IngestionResponse)
async def schedule_email_job(interval_minutes: int):
    """
    Schedule or reschedule the email ingestion job.
    
    Args:
        interval_minutes: Interval in minutes between ingestion runs
    """
    try:
        scheduler = get_scheduler()
        scheduler.add_email_ingestion_job(days=1, interval_minutes=interval_minutes)
        return {
            "success": True,
            "message": f"Email ingestion job scheduled to run every {interval_minutes} minutes."
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error scheduling email ingestion job: {str(e)}")

@router.post("/job/calendar", response_model=IngestionResponse)
async def schedule_calendar_job(interval_minutes: int):
    """
    Schedule or reschedule the calendar ingestion job.
    
    Args:
        interval_minutes: Interval in minutes between ingestion runs
    """
    try:
        scheduler = get_scheduler()
        scheduler.add_calendar_ingestion_job(days_past=0, days_future=30, interval_minutes=interval_minutes)
        return {
            "success": True,
            "message": f"Calendar ingestion job scheduled to run every {interval_minutes} minutes."
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error scheduling calendar ingestion job: {str(e)}")

@router.post("/job/todoist", response_model=IngestionResponse)
async def schedule_todoist_job(interval_minutes: int):
    """
    Schedule or reschedule the Todoist ingestion job.
    
    Args:
        interval_minutes: Interval in minutes between ingestion runs
    """
    try:
        scheduler = get_scheduler()
        scheduler.add_todoist_ingestion_job(interval_minutes=interval_minutes)
        return {
            "success": True,
            "message": f"Todoist ingestion job scheduled to run every {interval_minutes} minutes."
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error scheduling Todoist ingestion job: {str(e)}")

@router.delete("/job/{job_id}", response_model=IngestionResponse)
async def remove_job(job_id: str):
    """
    Remove a scheduled ingestion job.
    
    Args:
        job_id: ID of the job to remove
    """
    try:
        scheduler = get_scheduler()
        scheduler.remove_job(job_id)
        return {
            "success": True,
            "message": f"Job {job_id} removed successfully."
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error removing job: {str(e)}")