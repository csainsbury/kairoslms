"""
Data ingestion package for kairoslms.

This package contains modules for ingesting data from various sources:
- Email ingestion from Gmail
- Calendar events from Google Calendar
- Tasks and subtasks from Todoist
"""
from src.ingestion.email_ingestion import ingest_emails
from src.ingestion.calendar_ingestion import ingest_calendar_events
from src.ingestion.todoist_ingestion import ingest_todoist_tasks, sync_task_to_todoist