"""
Settings API for kairoslms.
"""
from typing import Dict, Any
from fastapi import APIRouter, HTTPException, Body, Depends
from pydantic import BaseModel
import os
from dotenv import load_dotenv

from src.db import get_db, execute_query
from src.ingestion.scheduler import get_scheduler

router = APIRouter(prefix="/settings", tags=["settings"])

class SchedulingSettings(BaseModel):
    """Model for scheduling settings."""
    email_ingestion_interval_minutes: int = 1440  # Daily
    calendar_ingestion_interval_minutes: int = 60  # Hourly
    todoist_ingestion_interval_minutes: int = 30   # Every 30 minutes
    status_overview_interval_hours: int = 12      # Every 12 hours
    task_prioritization_interval_minutes: int = 30  # Every 30 minutes
    llm_enhanced_processing_interval_hours: int = 24  # Daily

@router.get("/scheduling", response_model=SchedulingSettings)
async def get_scheduling_settings():
    """Get current scheduling settings."""
    try:
        # Get settings from environment variables
        email_interval = int(os.getenv("EMAIL_INGESTION_INTERVAL_MINUTES", "1440"))
        calendar_interval = int(os.getenv("CALENDAR_INGESTION_INTERVAL_MINUTES", "60"))
        todoist_interval = int(os.getenv("TODOIST_INGESTION_INTERVAL_MINUTES", "30"))
        status_interval = int(os.getenv("STATUS_OVERVIEW_INTERVAL_HOURS", "12"))
        task_interval = int(os.getenv("TASK_PRIORITIZATION_INTERVAL_MINUTES", "30"))
        llm_interval = int(os.getenv("LLM_ENHANCED_PROCESSING_INTERVAL_HOURS", "24"))
        
        return SchedulingSettings(
            email_ingestion_interval_minutes=email_interval,
            calendar_ingestion_interval_minutes=calendar_interval,
            todoist_ingestion_interval_minutes=todoist_interval,
            status_overview_interval_hours=status_interval,
            task_prioritization_interval_minutes=task_interval,
            llm_enhanced_processing_interval_hours=llm_interval
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error fetching scheduling settings: {str(e)}")

@router.put("/scheduling", response_model=SchedulingSettings)
async def update_scheduling_settings(settings: SchedulingSettings = Body(...)):
    """Update scheduling settings and restart the scheduler."""
    try:
        # Update environment variables
        env_path = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), "config", ".env")
        
        # Read existing env file
        with open(env_path, 'r') as file:
            env_lines = file.readlines()
        
        # Update or add settings
        updated_settings = {
            "EMAIL_INGESTION_INTERVAL_MINUTES": settings.email_ingestion_interval_minutes,
            "CALENDAR_INGESTION_INTERVAL_MINUTES": settings.calendar_ingestion_interval_minutes,
            "TODOIST_INGESTION_INTERVAL_MINUTES": settings.todoist_ingestion_interval_minutes,
            "STATUS_OVERVIEW_INTERVAL_HOURS": settings.status_overview_interval_hours,
            "TASK_PRIORITIZATION_INTERVAL_MINUTES": settings.task_prioritization_interval_minutes,
            "LLM_ENHANCED_PROCESSING_INTERVAL_HOURS": settings.llm_enhanced_processing_interval_hours
        }
        
        # Update env vars in memory for current process
        for key, value in updated_settings.items():
            os.environ[key] = str(value)
        
        # Find and update existing settings or add new ones
        settings_found = {key: False for key in updated_settings.keys()}
        
        for i, line in enumerate(env_lines):
            for key in updated_settings.keys():
                if line.startswith(f"{key}="):
                    env_lines[i] = f"{key}={updated_settings[key]}\n"
                    settings_found[key] = True
        
        # Add any settings that weren't found
        for key, found in settings_found.items():
            if not found:
                env_lines.append(f"{key}={updated_settings[key]}\n")
        
        # Write updated env file
        with open(env_path, 'w') as file:
            file.writelines(env_lines)
        
        # Reload env vars
        load_dotenv(env_path, override=True)
        
        # Restart scheduler with new settings
        scheduler = get_scheduler()
        scheduler.shutdown()
        
        # Reinitialize scheduler with new settings
        scheduler = get_scheduler()
        
        # Add ingestion jobs with new intervals
        scheduler.add_email_ingestion_job(days=1, interval_minutes=settings.email_ingestion_interval_minutes)
        scheduler.add_calendar_ingestion_job(days_past=0, days_future=30, interval_minutes=settings.calendar_ingestion_interval_minutes)
        scheduler.add_todoist_ingestion_job(interval_minutes=settings.todoist_ingestion_interval_minutes)
        
        # Add processing jobs with new intervals
        scheduler.add_status_overview_job(interval_hours=settings.status_overview_interval_hours)
        scheduler.add_task_prioritization_job(interval_minutes=settings.task_prioritization_interval_minutes)
        
        # Add LLM-enhanced processing if API key is available
        if os.getenv("ANTHROPIC_API_KEY"):
            scheduler.add_llm_enhanced_processing_job(interval_hours=settings.llm_enhanced_processing_interval_hours)
        
        # Start the scheduler
        scheduler.start()
        
        return settings
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error updating scheduling settings: {str(e)}")

@router.get("/status", response_model=Dict[str, Any])
async def get_system_status():
    """Get current system status including API keys and services."""
    try:
        scheduler = get_scheduler()
        
        status = {
            "services": {
                "scheduler_running": scheduler.is_running(),
                "database_connected": bool(get_db()),
            },
            "apis": {
                "gmail_configured": bool(os.getenv("GMAIL_API_KEY")),
                "google_calendar_configured": bool(os.getenv("GOOGLE_CALENDAR_API_KEY")),
                "todoist_configured": bool(os.getenv("TODOIST_API_KEY")),
                "llm_configured": bool(os.getenv("ANTHROPIC_API_KEY")),
            },
            "jobs": [job.name for job in scheduler.get_jobs()],
        }
        
        return status
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error fetching system status: {str(e)}")