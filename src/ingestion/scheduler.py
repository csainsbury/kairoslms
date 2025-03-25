"""
Scheduler for data ingestion and processing tasks in kairoslms.

This module schedules and runs data ingestion and processing tasks at specified intervals.
"""
import os
import logging
from datetime import datetime, timedelta
from typing import Dict, Any, Optional, List

from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.interval import IntervalTrigger
from apscheduler.triggers.cron import CronTrigger
from apscheduler.jobstores.sqlalchemy import SQLAlchemyJobStore
from apscheduler.executors.pool import ThreadPoolExecutor

from src.ingestion.email_ingestion import ingest_emails
from src.ingestion.calendar_ingestion import ingest_calendar_events
from src.ingestion.todoist_ingestion import ingest_todoist_tasks

# Import data processing modules
from src.status_overview import run_status_overview_generation
from src.task_prioritization import run_task_prioritization
from src.data_processor import run_data_processing
from src.llm_integration import get_llm

# Configure logging
logger = logging.getLogger(__name__)

class IngestionScheduler:
    """Scheduler for data ingestion and processing tasks."""
    
    def __init__(self):
        """Initialize the ingestion scheduler."""
        # Create job stores
        job_stores = {
            'default': SQLAlchemyJobStore(url=os.getenv('SCHEDULER_DB_URL', 'sqlite:///jobs.sqlite'))
        }
        
        # Create executor
        executors = {
            'default': ThreadPoolExecutor(max_workers=5)
        }
        
        # Create scheduler
        self.scheduler = BackgroundScheduler(
            jobstores=job_stores,
            executors=executors,
            timezone=os.getenv('TZ', 'UTC')
        )
        
        # Initialize job status tracking
        self.job_status: Dict[str, Dict[str, Any]] = {}
    
    def start(self):
        """Start the scheduler."""
        if not self.scheduler.running:
            self.scheduler.start()
            logger.info("Ingestion scheduler started")
    
    def shutdown(self):
        """Shutdown the scheduler."""
        if self.scheduler.running:
            self.scheduler.shutdown()
            logger.info("Ingestion scheduler shutdown")
    
    def add_email_ingestion_job(self, days: int = 1, interval_minutes: int = 1440):
        """
        Add an email ingestion job to the scheduler.
        
        Args:
            days: Number of days of emails to ingest
            interval_minutes: Interval in minutes between ingestion runs
        """
        job_id = 'email_ingestion'
        
        # Remove existing job with the same ID
        self.remove_job(job_id)
        
        # Add the job to the scheduler
        self.scheduler.add_job(
            func=self._run_email_ingestion,
            args=[days],
            trigger=IntervalTrigger(minutes=interval_minutes),
            id=job_id,
            replace_existing=True,
            name=f"Email Ingestion (every {interval_minutes} minutes)"
        )
        
        logger.info(f"Added email ingestion job: every {interval_minutes} minutes")
        
        # Initialize job status
        self.job_status[job_id] = {
            'last_run': None,
            'last_success': False,
            'last_result': None,
            'error': None
        }
    
    def add_calendar_ingestion_job(self, days_past: int = 0, days_future: int = 30, interval_minutes: int = 60):
        """
        Add a calendar ingestion job to the scheduler.
        
        Args:
            days_past: Number of days in the past to fetch events for
            days_future: Number of days in the future to fetch events for
            interval_minutes: Interval in minutes between ingestion runs
        """
        job_id = 'calendar_ingestion'
        
        # Remove existing job with the same ID
        self.remove_job(job_id)
        
        # Add the job to the scheduler
        self.scheduler.add_job(
            func=self._run_calendar_ingestion,
            args=[days_past, days_future],
            trigger=IntervalTrigger(minutes=interval_minutes),
            id=job_id,
            replace_existing=True,
            name=f"Calendar Ingestion (every {interval_minutes} minutes)"
        )
        
        logger.info(f"Added calendar ingestion job: every {interval_minutes} minutes")
        
        # Initialize job status
        self.job_status[job_id] = {
            'last_run': None,
            'last_success': False,
            'last_result': None,
            'error': None
        }
    
    def add_todoist_ingestion_job(self, interval_minutes: int = 30):
        """
        Add a Todoist ingestion job to the scheduler.
        
        Args:
            interval_minutes: Interval in minutes between ingestion runs
        """
        job_id = 'todoist_ingestion'
        
        # Remove existing job with the same ID
        self.remove_job(job_id)
        
        # Add the job to the scheduler
        self.scheduler.add_job(
            func=self._run_todoist_ingestion,
            trigger=IntervalTrigger(minutes=interval_minutes),
            id=job_id,
            replace_existing=True,
            name=f"Todoist Ingestion (every {interval_minutes} minutes)"
        )
        
        logger.info(f"Added Todoist ingestion job: every {interval_minutes} minutes")
        
        # Initialize job status
        self.job_status[job_id] = {
            'last_run': None,
            'last_success': False,
            'last_result': None,
            'error': None
        }
    
    def add_daily_ingestion_job(self, hour: int = 0, minute: int = 0):
        """
        Add a daily ingestion job that runs all ingestion tasks once per day.
        
        Args:
            hour: Hour of the day to run (0-23)
            minute: Minute of the hour to run (0-59)
        """
        job_id = 'daily_ingestion'
        
        # Remove existing job with the same ID
        self.remove_job(job_id)
        
        # Add the job to the scheduler
        self.scheduler.add_job(
            func=self._run_all_ingestion,
            trigger=CronTrigger(hour=hour, minute=minute),
            id=job_id,
            replace_existing=True,
            name=f"Daily Ingestion (at {hour:02d}:{minute:02d})"
        )
        
        logger.info(f"Added daily ingestion job: at {hour:02d}:{minute:02d}")
        
        # Initialize job status
        self.job_status[job_id] = {
            'last_run': None,
            'last_success': False,
            'last_result': None,
            'error': None
        }
    
    def remove_job(self, job_id: str):
        """
        Remove a job from the scheduler.
        
        Args:
            job_id: ID of the job to remove
        """
        try:
            self.scheduler.remove_job(job_id)
            logger.info(f"Removed job: {job_id}")
        except Exception as e:
            # Job might not exist, which is fine
            pass
    
    def get_job_status(self, job_id: Optional[str] = None) -> Dict[str, Any]:
        """
        Get the status of a specific job or all jobs.
        
        Args:
            job_id: ID of the job to get status for, or None for all jobs
            
        Returns:
            Dictionary with job status information
        """
        if job_id:
            return self.job_status.get(job_id, {})
        else:
            return self.job_status
    
    def get_jobs(self) -> List[Dict[str, Any]]:
        """
        Get information about all scheduled jobs.
        
        Returns:
            List of dictionaries with job information
        """
        jobs = []
        for job in self.scheduler.get_jobs():
            jobs.append({
                'id': job.id,
                'name': job.name,
                'next_run_time': job.next_run_time.isoformat() if job.next_run_time else None,
                'status': self.get_job_status(job.id)
            })
        return jobs
    
    def _run_email_ingestion(self, days: int = 1):
        """
        Run email ingestion task and update job status.
        
        Args:
            days: Number of days of emails to ingest
        """
        job_id = 'email_ingestion'
        self.job_status[job_id]['last_run'] = datetime.now()
        
        try:
            result = ingest_emails(days=days)
            
            self.job_status[job_id]['last_success'] = True
            self.job_status[job_id]['last_result'] = result
            self.job_status[job_id]['error'] = None
            
            logger.info(f"Email ingestion completed: {result}")
        except Exception as e:
            self.job_status[job_id]['last_success'] = False
            self.job_status[job_id]['error'] = str(e)
            
            logger.error(f"Error in email ingestion: {str(e)}")
    
    def _run_calendar_ingestion(self, days_past: int = 0, days_future: int = 30):
        """
        Run calendar ingestion task and update job status.
        
        Args:
            days_past: Number of days in the past to fetch events for
            days_future: Number of days in the future to fetch events for
        """
        job_id = 'calendar_ingestion'
        self.job_status[job_id]['last_run'] = datetime.now()
        
        try:
            result = ingest_calendar_events(days_past=days_past, days_future=days_future)
            
            self.job_status[job_id]['last_success'] = True
            self.job_status[job_id]['last_result'] = result
            self.job_status[job_id]['error'] = None
            
            logger.info(f"Calendar ingestion completed: {result}")
        except Exception as e:
            self.job_status[job_id]['last_success'] = False
            self.job_status[job_id]['error'] = str(e)
            
            logger.error(f"Error in calendar ingestion: {str(e)}")
    
    def _run_todoist_ingestion(self):
        """Run Todoist ingestion task and update job status."""
        job_id = 'todoist_ingestion'
        self.job_status[job_id]['last_run'] = datetime.now()
        
        try:
            result = ingest_todoist_tasks()
            
            self.job_status[job_id]['last_success'] = True
            self.job_status[job_id]['last_result'] = result
            self.job_status[job_id]['error'] = None
            
            logger.info(f"Todoist ingestion completed: {result}")
        except Exception as e:
            self.job_status[job_id]['last_success'] = False
            self.job_status[job_id]['error'] = str(e)
            
            logger.error(f"Error in Todoist ingestion: {str(e)}")
    
    def _run_all_ingestion(self):
        """Run all ingestion tasks and update job status."""
        job_id = 'daily_ingestion'
        self.job_status[job_id]['last_run'] = datetime.now()
        
        try:
            # Run email ingestion (last 1 day)
            email_result = ingest_emails(days=1)
            
            # Run calendar ingestion (past 7 days and future 30 days)
            calendar_result = ingest_calendar_events(days_past=7, days_future=30)
            
            # Run Todoist ingestion
            todoist_result = ingest_todoist_tasks()
            
            result = {
                'email': email_result,
                'calendar': calendar_result,
                'todoist': todoist_result
            }
            
            self.job_status[job_id]['last_success'] = True
            self.job_status[job_id]['last_result'] = result
            self.job_status[job_id]['error'] = None
            
            logger.info(f"Daily ingestion completed: {result}")
        except Exception as e:
            self.job_status[job_id]['last_success'] = False
            self.job_status[job_id]['error'] = str(e)
            
            logger.error(f"Error in daily ingestion: {str(e)}")
    
    def add_status_overview_job(self, interval_hours: int = 12):
        """
        Add a status overview generation job to the scheduler.
        
        Args:
            interval_hours: Interval in hours between status overview generation
        """
        job_id = 'status_overview_generation'
        
        # Remove existing job with the same ID
        self.remove_job(job_id)
        
        # Add the job to the scheduler
        self.scheduler.add_job(
            func=self._run_status_overview_generation,
            trigger=IntervalTrigger(hours=interval_hours),
            id=job_id,
            replace_existing=True,
            name=f"Status Overview Generation (every {interval_hours} hours)"
        )
        
        logger.info(f"Added status overview generation job: every {interval_hours} hours")
        
        # Initialize job status
        self.job_status[job_id] = {
            'last_run': None,
            'last_success': False,
            'last_result': None,
            'error': None
        }
    
    def add_task_prioritization_job(self, interval_minutes: int = 30):
        """
        Add a task prioritization job to the scheduler.
        
        Args:
            interval_minutes: Interval in minutes between task prioritization runs
        """
        job_id = 'task_prioritization'
        
        # Remove existing job with the same ID
        self.remove_job(job_id)
        
        # Add the job to the scheduler
        self.scheduler.add_job(
            func=self._run_task_prioritization,
            trigger=IntervalTrigger(minutes=interval_minutes),
            id=job_id,
            replace_existing=True,
            name=f"Task Prioritization (every {interval_minutes} minutes)"
        )
        
        logger.info(f"Added task prioritization job: every {interval_minutes} minutes")
        
        # Initialize job status
        self.job_status[job_id] = {
            'last_run': None,
            'last_success': False,
            'last_result': None,
            'error': None
        }
    
    def add_data_processing_job(self, interval_hours: int = 6):
        """
        Add a full data processing job to the scheduler.
        
        Args:
            interval_hours: Interval in hours between data processing runs
        """
        job_id = 'data_processing'
        
        # Remove existing job with the same ID
        self.remove_job(job_id)
        
        # Add the job to the scheduler
        self.scheduler.add_job(
            func=self._run_data_processing,
            trigger=IntervalTrigger(hours=interval_hours),
            id=job_id,
            replace_existing=True,
            name=f"Data Processing (every {interval_hours} hours)"
        )
        
        logger.info(f"Added data processing job: every {interval_hours} hours")
        
        # Initialize job status
        self.job_status[job_id] = {
            'last_run': None,
            'last_success': False,
            'last_result': None,
            'error': None
        }
    
    def add_llm_enhanced_processing_job(self, interval_hours: int = 12):
        """
        Add an LLM-enhanced processing job to the scheduler.
        
        This job uses the LLM for enhanced reasoning in status overview generation
        and task prioritization. It runs less frequently than standard processing
        to minimize API costs.
        
        Args:
            interval_hours: Interval in hours between LLM-enhanced processing runs
        """
        job_id = 'llm_enhanced_processing'
        
        # Remove existing job with the same ID
        self.remove_job(job_id)
        
        # Check if LLM is available
        if not os.getenv("ANTHROPIC_API_KEY"):
            logger.warning("ANTHROPIC_API_KEY is not set. LLM-enhanced processing will not be available.")
            return
        
        # Add the job to the scheduler
        self.scheduler.add_job(
            func=self._run_llm_enhanced_processing,
            trigger=IntervalTrigger(hours=interval_hours),
            id=job_id,
            replace_existing=True,
            name=f"LLM-Enhanced Processing (every {interval_hours} hours)"
        )
        
        logger.info(f"Added LLM-enhanced processing job: every {interval_hours} hours")
        
        # Initialize job status
        self.job_status[job_id] = {
            'last_run': None,
            'last_success': False,
            'last_result': None,
            'error': None
        }
    
    def _run_status_overview_generation(self):
        """Run status overview generation and update job status."""
        job_id = 'status_overview_generation'
        self.job_status[job_id]['last_run'] = datetime.now()
        
        try:
            result = run_status_overview_generation()
            
            self.job_status[job_id]['last_success'] = True
            self.job_status[job_id]['last_result'] = result
            self.job_status[job_id]['error'] = None
            
            logger.info("Status overview generation completed successfully")
        except Exception as e:
            self.job_status[job_id]['last_success'] = False
            self.job_status[job_id]['error'] = str(e)
            
            logger.error(f"Error in status overview generation: {str(e)}")
    
    def _run_task_prioritization(self):
        """Run task prioritization and update job status."""
        job_id = 'task_prioritization'
        self.job_status[job_id]['last_run'] = datetime.now()
        
        try:
            result = run_task_prioritization()
            
            self.job_status[job_id]['last_success'] = True
            self.job_status[job_id]['last_result'] = result
            self.job_status[job_id]['error'] = None
            
            logger.info("Task prioritization completed successfully")
        except Exception as e:
            self.job_status[job_id]['last_success'] = False
            self.job_status[job_id]['error'] = str(e)
            
            logger.error(f"Error in task prioritization: {str(e)}")
    
    def _run_data_processing(self):
        """Run full data processing and update job status."""
        job_id = 'data_processing'
        self.job_status[job_id]['last_run'] = datetime.now()
        
        try:
            # Run data processing without LLM by default (to save API costs)
            result = run_data_processing(use_llm=False)
            
            self.job_status[job_id]['last_success'] = True
            self.job_status[job_id]['last_result'] = result
            self.job_status[job_id]['error'] = None
            
            logger.info(f"Data processing completed successfully: {result}")
        except Exception as e:
            self.job_status[job_id]['last_success'] = False
            self.job_status[job_id]['error'] = str(e)
            
            logger.error(f"Error in data processing: {str(e)}")
    
    def _run_llm_enhanced_processing(self):
        """Run LLM-enhanced data processing and update job status."""
        job_id = 'llm_enhanced_processing'
        self.job_status[job_id]['last_run'] = datetime.now()
        
        try:
            # Check if LLM is available
            if not os.getenv("ANTHROPIC_API_KEY"):
                error_msg = "ANTHROPIC_API_KEY is not set. Cannot run LLM-enhanced processing."
                logger.error(error_msg)
                self.job_status[job_id]['last_success'] = False
                self.job_status[job_id]['error'] = error_msg
                return
            
            # First run status overview generation with LLM
            logger.info("Running LLM-enhanced status overview generation...")
            status_result = run_status_overview_generation(use_llm=True)
            
            # Then run task prioritization with LLM
            logger.info("Running LLM-enhanced task prioritization...")
            priority_result = run_task_prioritization(use_llm=True)
            
            # Prepare the combined result
            result = {
                "status_overview": status_result,
                "task_prioritization": priority_result
            }
            
            self.job_status[job_id]['last_success'] = True
            self.job_status[job_id]['last_result'] = result
            self.job_status[job_id]['error'] = None
            
            logger.info("LLM-enhanced processing completed successfully")
        except Exception as e:
            self.job_status[job_id]['last_success'] = False
            self.job_status[job_id]['error'] = str(e)
            
            logger.error(f"Error in LLM-enhanced processing: {str(e)}")


# Singleton instance
_scheduler_instance = None

def get_scheduler() -> IngestionScheduler:
    """
    Get the singleton ingestion scheduler instance.
    
    Returns:
        IngestionScheduler instance
    """
    global _scheduler_instance
    if _scheduler_instance is None:
        _scheduler_instance = IngestionScheduler()
    return _scheduler_instance


if __name__ == "__main__":
    # Configure logging for standalone use
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    )
    
    # Test the scheduler
    scheduler = get_scheduler()
    
    # Add ingestion jobs
    scheduler.add_email_ingestion_job(interval_minutes=1440)  # Once per day
    scheduler.add_calendar_ingestion_job(interval_minutes=60)  # Once per hour
    scheduler.add_todoist_ingestion_job(interval_minutes=30)  # Every 30 minutes
    
    # Add processing jobs
    scheduler.add_status_overview_job(interval_hours=12)  # Every 12 hours
    scheduler.add_task_prioritization_job(interval_minutes=30)  # Every 30 minutes
    scheduler.add_data_processing_job(interval_hours=6)  # Every 6 hours
    
    # Add LLM-enhanced processing job (runs less frequently to save API costs)
    scheduler.add_llm_enhanced_processing_job(interval_hours=24)  # Once per day
    
    # Start the scheduler
    scheduler.start()
    
    # Wait for jobs to run
    try:
        import time
        print("Scheduler running. Press Ctrl+C to exit.")
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        print("Shutting down scheduler...")
        scheduler.shutdown()