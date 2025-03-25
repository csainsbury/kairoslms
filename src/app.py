#!/usr/bin/env python3
"""
Main application entry point for kairoslms.
"""
import os
import sys
import logging
from fastapi import FastAPI, Request, HTTPException
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from fastapi.responses import HTMLResponse
from fastapi.middleware.cors import CORSMiddleware
from fastapi.exception_handlers import http_exception_handler
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException
from dotenv import load_dotenv

from src.api import api_router
from src.db import create_tables
from src.ingestion.scheduler import get_scheduler
from src.middlewares import configure_middlewares
from src.utils.logging import configure_logging, get_logger
from src.utils.error_handling import handle_exception, KairosError, ErrorResponse
from src.utils.backup import schedule_backup, clean_old_backups
from src.utils.security import validate_required_env_vars

# Load environment variables
config_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), "config")
env_path = os.path.join(config_dir, ".env")

if os.path.exists(env_path):
    load_dotenv(env_path)
else:
    print(f"Warning: .env file not found at {env_path}")

# Configure logging
log_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), "logs")
os.makedirs(log_dir, exist_ok=True)
log_file = os.path.join(log_dir, "kairoslms.log")

configure_logging(
    log_level=os.getenv("LOG_LEVEL", "INFO"),
    log_file=log_file,
    max_bytes=10 * 1024 * 1024,  # 10 MB
    backup_count=5,
    json_format=True,
    console_output=True
)

# Get logger for this module
logger = get_logger(__name__)

# Validate required environment variables
try:
    validate_required_env_vars([
        "SECRET_KEY",
        "DB_USER",
        "DB_PASSWORD",
        "DB_NAME",
        "DB_HOST",
        "DB_PORT"
    ])
except Exception as e:
    logger.error(f"Environment validation failed: {str(e)}")
    # Continue anyway for development purposes, but log the error

# Create FastAPI app
app = FastAPI(
    title="Kairos Life Management System",
    description="A system to help users set and track strategic goals across multiple life domains.",
    version="0.1.0",
)

# Configure middlewares
configure_middlewares(app)

# Set up static files directory
static_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), "static")
os.makedirs(static_dir, exist_ok=True)
app.mount("/static", StaticFiles(directory=static_dir), name="static")

# Set up Jinja2 templates
templates_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), "templates")
os.makedirs(templates_dir, exist_ok=True)
templates = Jinja2Templates(directory=templates_dir)

# Include API router
app.include_router(api_router, prefix="/api")

# Custom exception handlers
@app.exception_handler(StarletteHTTPException)
async def custom_http_exception_handler(request: Request, exc: StarletteHTTPException):
    """
    Handle HTTP exceptions.
    
    Args:
        request: The request that triggered the exception
        exc: The exception
        
    Returns:
        JSONResponse: Formatted error response
    """
    error_response = handle_exception(exc, request)
    
    if request.headers.get("accept") == "application/json":
        return JSONResponse(
            status_code=exc.status_code,
            content=error_response.dict()
        )
    
    return await http_exception_handler(request, exc)

@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError):
    """
    Handle validation errors.
    
    Args:
        request: The request that triggered the exception
        exc: The exception
        
    Returns:
        JSONResponse: Formatted error response
    """
    errors = exc.errors()
    error_details = {}
    
    # Format validation errors
    for error in errors:
        loc = ".".join([str(l) for l in error["loc"] if l != "body"])
        error_details[loc] = error["msg"]
    
    error_response = ErrorResponse(
        error="Validation error",
        status_code=422,
        details=error_details,
        timestamp=logging.Formatter.formatTime(logging.LogRecord("", 0, "", 0, None, None, None, None, None), "%Y-%m-%d %H:%M:%S"),
        path=request.url.path
    )
    
    return JSONResponse(
        status_code=422,
        content=error_response.dict()
    )

@app.exception_handler(KairosError)
async def kairos_error_handler(request: Request, exc: KairosError):
    """
    Handle custom KairosLMS errors.
    
    Args:
        request: The request that triggered the exception
        exc: The exception
        
    Returns:
        JSONResponse: Formatted error response
    """
    error_response = handle_exception(exc, request)
    
    return JSONResponse(
        status_code=exc.status_code,
        content=error_response.dict()
    )

@app.exception_handler(Exception)
async def general_exception_handler(request: Request, exc: Exception):
    """
    Handle all other exceptions.
    
    Args:
        request: The request that triggered the exception
        exc: The exception
        
    Returns:
        JSONResponse: Formatted error response
    """
    error_response = handle_exception(exc, request)
    
    return JSONResponse(
        status_code=500,
        content=error_response.dict()
    )

@app.get("/", response_class=HTMLResponse)
async def root(request: Request):
    """Serve the main dashboard page."""
    return templates.TemplateResponse(
        "dashboard.html", 
        {"request": request, "title": "Kairos LMS - Dashboard"}
    )

@app.get("/chat", response_class=HTMLResponse)
async def chat_page(request: Request):
    """Serve the chat interface page."""
    return templates.TemplateResponse(
        "chat.html", 
        {"request": request, "title": "Kairos LMS - Chat"}
    )

@app.get("/settings", response_class=HTMLResponse)
async def settings_page(request: Request):
    """Serve the settings page."""
    return templates.TemplateResponse(
        "settings.html", 
        {"request": request, "title": "Kairos LMS - Settings"}
    )

@app.get("/health")
async def health_check():
    """Health check endpoint."""
    return {"status": "healthy"}

@app.on_event("startup")
async def startup_event():
    """Run on application startup."""
    logger.info("Starting KairosLMS application")
    
    # Initialize database tables
    logger.info("Initializing database tables...")
    try:
        create_tables()
        logger.info("Database tables initialized successfully")
    except Exception as e:
        logger.error(f"Error initializing database tables: {str(e)}", exc_info=True)
        # Continue anyway, as tables might already exist
    
    # Set up backup schedule
    if os.getenv("ENABLE_BACKUPS", "false").lower() == "true":
        try:
            # Schedule daily database backup
            db_backup_days = int(os.getenv("DB_BACKUP_INTERVAL_DAYS", "1"))
            connection_string = f"postgresql://{os.getenv('DB_USER')}:{os.getenv('DB_PASSWORD')}@{os.getenv('DB_HOST')}:{os.getenv('DB_PORT')}/{os.getenv('DB_NAME')}"
            
            from src.utils.backup import backup_database, clean_old_backups
            
            # Schedule backup
            schedule_backup(
                days=db_backup_days,
                backup_func=backup_database,
                backup_kwargs={"connection_string": connection_string}
            )
            
            # Clean old backups
            clean_old_backups(keep_days=int(os.getenv("KEEP_BACKUPS_DAYS", "30")))
            
            logger.info(f"Database backups scheduled every {db_backup_days} days")
        except Exception as e:
            logger.error(f"Failed to set up backup schedule: {str(e)}", exc_info=True)
    
    # Start the ingestion scheduler
    logger.info("Starting ingestion scheduler...")
    try:
        scheduler = get_scheduler()
        
        # Set up ingestion jobs based on environment variables
        email_interval = int(os.getenv("EMAIL_INGESTION_INTERVAL_MINUTES", "1440"))  # Default to daily
        calendar_interval = int(os.getenv("CALENDAR_INGESTION_INTERVAL_MINUTES", "60"))  # Default to hourly
        todoist_interval = int(os.getenv("TODOIST_INGESTION_INTERVAL_MINUTES", "30"))  # Default to every 30 minutes
        
        # Add ingestion jobs with proper error handling
        try:
            scheduler.add_email_ingestion_job(days=1, interval_minutes=email_interval)
            logger.info(f"Email ingestion scheduled every {email_interval} minutes")
        except Exception as e:
            logger.error(f"Failed to schedule email ingestion: {str(e)}", exc_info=True)
        
        try:
            scheduler.add_calendar_ingestion_job(days_past=0, days_future=30, interval_minutes=calendar_interval)
            logger.info(f"Calendar ingestion scheduled every {calendar_interval} minutes")
        except Exception as e:
            logger.error(f"Failed to schedule calendar ingestion: {str(e)}", exc_info=True)
        
        try:
            scheduler.add_todoist_ingestion_job(interval_minutes=todoist_interval)
            logger.info(f"Todoist ingestion scheduled every {todoist_interval} minutes")
        except Exception as e:
            logger.error(f"Failed to schedule todoist ingestion: {str(e)}", exc_info=True)
        
        # Add processing jobs
        status_interval = int(os.getenv("STATUS_OVERVIEW_INTERVAL_HOURS", "12"))  # Default to every 12 hours
        task_interval = int(os.getenv("TASK_PRIORITIZATION_INTERVAL_MINUTES", "30"))  # Default to every 30 minutes
        llm_interval = int(os.getenv("LLM_ENHANCED_PROCESSING_INTERVAL_HOURS", "24"))  # Default to daily
        
        try:
            scheduler.add_status_overview_job(interval_hours=status_interval)
            logger.info(f"Status overview generation scheduled every {status_interval} hours")
        except Exception as e:
            logger.error(f"Failed to schedule status overview: {str(e)}", exc_info=True)
        
        try:
            scheduler.add_task_prioritization_job(interval_minutes=task_interval)
            logger.info(f"Task prioritization scheduled every {task_interval} minutes")
        except Exception as e:
            logger.error(f"Failed to schedule task prioritization: {str(e)}", exc_info=True)
        
        # Add LLM-enhanced processing if API key is available
        if os.getenv("ANTHROPIC_API_KEY"):
            try:
                scheduler.add_llm_enhanced_processing_job(interval_hours=llm_interval)
                logger.info(f"LLM-enhanced processing scheduled every {llm_interval} hours")
            except Exception as e:
                logger.error(f"Failed to schedule LLM processing: {str(e)}", exc_info=True)
        else:
            logger.warning("ANTHROPIC_API_KEY not set. LLM-enhanced processing will not be available.")
        
        # Start the scheduler
        scheduler.start()
        logger.info("Scheduler started with all jobs")
    except Exception as e:
        logger.error(f"Failed to start scheduler: {str(e)}", exc_info=True)
    
    logger.info("KairosLMS application startup complete")


@app.on_event("shutdown")
async def shutdown_event():
    """Run on application shutdown."""
    logger.info("Shutting down KairosLMS application")
    
    # Shutdown the scheduler
    try:
        logger.info("Shutting down ingestion scheduler...")
        scheduler = get_scheduler()
        scheduler.shutdown()
        logger.info("Scheduler shutdown complete")
    except Exception as e:
        logger.error(f"Error shutting down scheduler: {str(e)}", exc_info=True)
    
    # Perform final backup if enabled
    if os.getenv("BACKUP_ON_SHUTDOWN", "false").lower() == "true":
        try:
            logger.info("Performing final backup on shutdown...")
            connection_string = f"postgresql://{os.getenv('DB_USER')}:{os.getenv('DB_PASSWORD')}@{os.getenv('DB_HOST')}:{os.getenv('DB_PORT')}/{os.getenv('DB_NAME')}"
            from src.utils.backup import backup_database
            success, backup_file = backup_database(connection_string)
            
            if success:
                logger.info(f"Final backup completed: {backup_file}")
            else:
                logger.error("Final backup failed")
        except Exception as e:
            logger.error(f"Error performing final backup: {str(e)}", exc_info=True)
    
    logger.info("KairosLMS application shutdown complete")

if __name__ == "__main__":
    import uvicorn
    
    logger.info("Starting Kairos LMS")
    uvicorn.run("src.app:app", host="0.0.0.0", port=8000, reload=True)