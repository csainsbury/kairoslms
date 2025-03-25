"""
Backup utilities for kairoslms.

This module provides functionality for backing up and restoring data:
- Database backups
- Configuration backups
- Scheduled backup jobs
"""
import os
import time
import logging
import shutil
import json
import gzip
import sqlite3
import tarfile
from datetime import datetime
from typing import Dict, Any, Optional, List, Union, Tuple
import subprocess
from pathlib import Path
import threading

# Configure module logger
logger = logging.getLogger(__name__)

# Default backup directory
DEFAULT_BACKUP_DIR = os.getenv("BACKUP_DIR", "backups")


def ensure_backup_directory(backup_dir: Optional[str] = None) -> str:
    """
    Ensure the backup directory exists.
    
    Args:
        backup_dir: Backup directory path
        
    Returns:
        str: Path to the backup directory
    """
    backup_dir = backup_dir or DEFAULT_BACKUP_DIR
    
    try:
        os.makedirs(backup_dir, exist_ok=True)
        logger.debug(f"Backup directory ensured: {backup_dir}")
        return backup_dir
    except Exception as e:
        logger.error(f"Failed to create backup directory {backup_dir}: {str(e)}")
        raise


def generate_backup_filename(prefix: str, extension: str = "backup") -> str:
    """
    Generate a timestamped backup filename.
    
    Args:
        prefix: Prefix for the filename
        extension: File extension
        
    Returns:
        str: Generated backup filename
    """
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    return f"{prefix}_{timestamp}.{extension}"


def backup_database(
    connection_string: str,
    backup_dir: Optional[str] = None,
    compress: bool = True
) -> Tuple[bool, str]:
    """
    Back up a PostgreSQL database.
    
    Args:
        connection_string: PostgreSQL connection string
        backup_dir: Directory to store the backup
        compress: Whether to compress the backup
        
    Returns:
        Tuple[bool, str]: Success status and backup file path
    """
    backup_dir = ensure_backup_directory(backup_dir)
    backup_file = os.path.join(backup_dir, generate_backup_filename("db", "sql"))
    
    # Extract database name and connection details from connection string
    # Example: "postgresql://user:password@host:port/dbname"
    try:
        # Very basic parsing - in a real implementation, use a proper URL parser
        parts = connection_string.split("/")
        dbname = parts[-1].split("?")[0]
        host_part = parts[2].split("@")[-1].split(":")[0]
        user_part = parts[2].split("@")[0].split(":")[0].split("//")[1]
        
        # Command to dump the database
        cmd = [
            "pg_dump",
            "-h", host_part,
            "-U", user_part,
            "-d", dbname,
            "-f", backup_file
        ]
        
        # Set PGPASSWORD environment variable
        env = os.environ.copy()
        if ":" in parts[2].split("@")[0]:
            env["PGPASSWORD"] = parts[2].split("@")[0].split(":")[1]
        
        # Execute the dump command
        logger.info(f"Backing up database to {backup_file}")
        process = subprocess.run(
            cmd,
            env=env,
            check=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE
        )
        
        # Compress the file if requested
        if compress and os.path.exists(backup_file):
            compressed_file = f"{backup_file}.gz"
            with open(backup_file, 'rb') as f_in:
                with gzip.open(compressed_file, 'wb') as f_out:
                    shutil.copyfileobj(f_in, f_out)
            
            # Remove the uncompressed file
            os.remove(backup_file)
            backup_file = compressed_file
            logger.info(f"Compressed database backup to {backup_file}")
        
        logger.info(f"Database backup completed: {backup_file}")
        return True, backup_file
    
    except Exception as e:
        logger.error(f"Failed to back up database: {str(e)}")
        return False, ""


def backup_sqlite_database(
    db_path: str,
    backup_dir: Optional[str] = None,
    compress: bool = True
) -> Tuple[bool, str]:
    """
    Back up a SQLite database.
    
    Args:
        db_path: Path to the SQLite database file
        backup_dir: Directory to store the backup
        compress: Whether to compress the backup
        
    Returns:
        Tuple[bool, str]: Success status and backup file path
    """
    backup_dir = ensure_backup_directory(backup_dir)
    backup_file = os.path.join(backup_dir, generate_backup_filename("sqlite", "db"))
    
    try:
        # Check if the source database exists
        if not os.path.exists(db_path):
            logger.error(f"Source database does not exist: {db_path}")
            return False, ""
        
        # Use SQLite's backup API to create a consistent backup
        source = sqlite3.connect(db_path)
        dest = sqlite3.connect(backup_file)
        
        source.backup(dest)
        
        # Close the connections
        source.close()
        dest.close()
        
        # Compress the file if requested
        if compress and os.path.exists(backup_file):
            compressed_file = f"{backup_file}.gz"
            with open(backup_file, 'rb') as f_in:
                with gzip.open(compressed_file, 'wb') as f_out:
                    shutil.copyfileobj(f_in, f_out)
            
            # Remove the uncompressed file
            os.remove(backup_file)
            backup_file = compressed_file
            logger.info(f"Compressed SQLite backup to {backup_file}")
        
        logger.info(f"SQLite database backup completed: {backup_file}")
        return True, backup_file
    
    except Exception as e:
        logger.error(f"Failed to back up SQLite database: {str(e)}")
        return False, ""


def backup_config_files(
    config_dir: str,
    backup_dir: Optional[str] = None,
    exclude_patterns: Optional[List[str]] = None
) -> Tuple[bool, str]:
    """
    Back up configuration files.
    
    Args:
        config_dir: Directory containing configuration files
        backup_dir: Directory to store the backup
        exclude_patterns: List of file patterns to exclude
        
    Returns:
        Tuple[bool, str]: Success status and backup file path
    """
    backup_dir = ensure_backup_directory(backup_dir)
    backup_file = os.path.join(backup_dir, generate_backup_filename("config", "tar.gz"))
    
    try:
        # Check if the source directory exists
        if not os.path.exists(config_dir):
            logger.error(f"Source config directory does not exist: {config_dir}")
            return False, ""
        
        # Default exclude patterns if none provided
        exclude_patterns = exclude_patterns or [
            "*.pyc", "__pycache__", "*.log", "*.tmp", "*.bak",
            "venv", "env", ".env", ".git", ".gitignore", "node_modules"
        ]
        
        # Create a tar.gz archive
        with tarfile.open(backup_file, "w:gz") as tar:
            # Walk through the directory structure
            for root, dirs, files in os.walk(config_dir):
                # Skip directories based on exclude patterns
                dirs[:] = [d for d in dirs if not any(Path(d).match(pattern) for pattern in exclude_patterns)]
                
                # Add files to the archive
                for file in files:
                    # Skip files based on exclude patterns
                    if any(Path(file).match(pattern) for pattern in exclude_patterns):
                        continue
                    
                    file_path = os.path.join(root, file)
                    arcname = os.path.relpath(file_path, os.path.dirname(config_dir))
                    
                    try:
                        tar.add(file_path, arcname=arcname)
                    except Exception as e:
                        logger.warning(f"Failed to add file to backup: {file_path} - {str(e)}")
        
        logger.info(f"Configuration backup completed: {backup_file}")
        return True, backup_file
    
    except Exception as e:
        logger.error(f"Failed to back up configuration files: {str(e)}")
        return False, ""


def restore_database(
    backup_file: str,
    connection_string: str
) -> bool:
    """
    Restore a PostgreSQL database from a backup.
    
    Args:
        backup_file: Path to the backup file
        connection_string: PostgreSQL connection string
        
    Returns:
        bool: Success status
    """
    try:
        # Check if the backup file exists
        if not os.path.exists(backup_file):
            logger.error(f"Backup file does not exist: {backup_file}")
            return False
        
        # Extract database name and connection details from connection string
        # Example: "postgresql://user:password@host:port/dbname"
        parts = connection_string.split("/")
        dbname = parts[-1].split("?")[0]
        host_part = parts[2].split("@")[-1].split(":")[0]
        user_part = parts[2].split("@")[0].split(":")[0].split("//")[1]
        
        # Decompress if needed
        if backup_file.endswith(".gz"):
            decompressed_file = backup_file[:-3]
            with gzip.open(backup_file, 'rb') as f_in:
                with open(decompressed_file, 'wb') as f_out:
                    shutil.copyfileobj(f_in, f_out)
            backup_file = decompressed_file
            logger.info(f"Decompressed backup file to {backup_file}")
        
        # Command to restore the database
        cmd = [
            "psql",
            "-h", host_part,
            "-U", user_part,
            "-d", dbname,
            "-f", backup_file
        ]
        
        # Set PGPASSWORD environment variable
        env = os.environ.copy()
        if ":" in parts[2].split("@")[0]:
            env["PGPASSWORD"] = parts[2].split("@")[0].split(":")[1]
        
        # Execute the restore command
        logger.info(f"Restoring database from {backup_file}")
        process = subprocess.run(
            cmd,
            env=env,
            check=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE
        )
        
        # Clean up decompressed file if we created one
        if backup_file.endswith(".gz"):
            os.remove(backup_file)
        
        logger.info(f"Database restore completed from {backup_file}")
        return True
    
    except Exception as e:
        logger.error(f"Failed to restore database: {str(e)}")
        return False


def restore_sqlite_database(
    backup_file: str,
    db_path: str
) -> bool:
    """
    Restore a SQLite database from a backup.
    
    Args:
        backup_file: Path to the backup file
        db_path: Path to the target SQLite database
        
    Returns:
        bool: Success status
    """
    try:
        # Check if the backup file exists
        if not os.path.exists(backup_file):
            logger.error(f"Backup file does not exist: {backup_file}")
            return False
        
        # Decompress if needed
        if backup_file.endswith(".gz"):
            decompressed_file = backup_file[:-3]
            with gzip.open(backup_file, 'rb') as f_in:
                with open(decompressed_file, 'wb') as f_out:
                    shutil.copyfileobj(f_in, f_out)
            backup_file = decompressed_file
            logger.info(f"Decompressed backup file to {backup_file}")
        
        # Make sure the target directory exists
        os.makedirs(os.path.dirname(db_path), exist_ok=True)
        
        # Simply copy the backup file to the target location
        shutil.copy2(backup_file, db_path)
        
        # Clean up decompressed file if we created one
        if backup_file.endswith(".gz"):
            os.remove(backup_file)
        
        logger.info(f"SQLite database restore completed to {db_path}")
        return True
    
    except Exception as e:
        logger.error(f"Failed to restore SQLite database: {str(e)}")
        return False


def restore_config_files(
    backup_file: str,
    target_dir: str,
    overwrite: bool = False
) -> bool:
    """
    Restore configuration files from a backup.
    
    Args:
        backup_file: Path to the backup archive
        target_dir: Directory to restore to
        overwrite: Whether to overwrite existing files
        
    Returns:
        bool: Success status
    """
    try:
        # Check if the backup file exists
        if not os.path.exists(backup_file):
            logger.error(f"Backup file does not exist: {backup_file}")
            return False
        
        # Make sure the target directory exists
        os.makedirs(target_dir, exist_ok=True)
        
        # Extract the archive
        with tarfile.open(backup_file, "r:gz") as tar:
            # If overwrite is False, only extract files that don't exist
            if not overwrite:
                # Get list of members in the archive
                members = tar.getmembers()
                
                # Filter out files that already exist
                extract_members = []
                for member in members:
                    target_path = os.path.join(target_dir, member.name)
                    if not os.path.exists(target_path) or member.isdir():
                        extract_members.append(member)
                
                # Extract only the filtered members
                tar.extractall(path=target_dir, members=extract_members)
                logger.info(f"Extracted {len(extract_members)} of {len(members)} files (skipped existing files)")
            else:
                # Extract all files
                tar.extractall(path=target_dir)
                logger.info(f"Extracted all files (overwriting existing)")
        
        logger.info(f"Configuration restore completed to {target_dir}")
        return True
    
    except Exception as e:
        logger.error(f"Failed to restore configuration files: {str(e)}")
        return False


def schedule_backup(
    days: int = 1,
    hours: int = 0,
    minutes: int = 0,
    first_run_delay: int = 5,
    backup_func: Optional[Callable] = None,
    backup_kwargs: Optional[Dict[str, Any]] = None
) -> threading.Timer:
    """
    Schedule a backup job to run periodically.
    
    Args:
        days: Number of days between backups
        hours: Number of hours between backups
        minutes: Number of minutes between backups
        first_run_delay: Delay before first run (minutes)
        backup_func: Function to run for backup
        backup_kwargs: Keyword arguments for backup function
        
    Returns:
        threading.Timer: The timer object
    """
    # Calculate interval in seconds
    interval = (days * 24 * 60 * 60) + (hours * 60 * 60) + (minutes * 60)
    
    # Default to database backup if no function specified
    if backup_func is None:
        backup_func = backup_database
    
    # Default kwargs
    backup_kwargs = backup_kwargs or {}
    
    def run_backup():
        try:
            logger.info(f"Running scheduled backup with {backup_func.__name__}")
            success, path = backup_func(**backup_kwargs)
            
            if success:
                logger.info(f"Scheduled backup completed: {path}")
            else:
                logger.error(f"Scheduled backup failed")
        except Exception as e:
            logger.error(f"Error in scheduled backup: {str(e)}")
        finally:
            # Schedule the next run
            schedule_backup(
                days=days,
                hours=hours,
                minutes=minutes,
                first_run_delay=0,  # Next run uses the full interval
                backup_func=backup_func,
                backup_kwargs=backup_kwargs
            )
    
    # Create and start the timer
    # Convert first_run_delay from minutes to seconds
    timer = threading.Timer(first_run_delay * 60, run_backup)
    timer.daemon = True  # Allow the program to exit even if the timer is still running
    timer.start()
    
    logger.info(f"Scheduled backup job every {days}d {hours}h {minutes}m, first run in {first_run_delay}m")
    return timer


def clean_old_backups(
    backup_dir: Optional[str] = None,
    keep_days: int = 30,
    keep_count: int = 10
) -> int:
    """
    Clean up old backup files.
    
    Args:
        backup_dir: Directory containing backups
        keep_days: Number of days to keep backups
        keep_count: Minimum number of backups to keep regardless of age
        
    Returns:
        int: Number of deleted files
    """
    backup_dir = backup_dir or DEFAULT_BACKUP_DIR
    
    try:
        # Check if the backup directory exists
        if not os.path.exists(backup_dir):
            logger.warning(f"Backup directory does not exist: {backup_dir}")
            return 0
        
        # Get list of backup files
        backup_files = []
        for file in os.listdir(backup_dir):
            file_path = os.path.join(backup_dir, file)
            if os.path.isfile(file_path) and (
                file.endswith(".backup") or
                file.endswith(".sql") or
                file.endswith(".sql.gz") or
                file.endswith(".db") or
                file.endswith(".db.gz") or
                file.endswith(".tar.gz")
            ):
                backup_files.append((file_path, os.path.getmtime(file_path)))
        
        # Sort by modification time (newest first)
        backup_files.sort(key=lambda x: x[1], reverse=True)
        
        # Keep the minimum number of backups
        kept_files = backup_files[:keep_count]
        delete_candidates = backup_files[keep_count:]
        
        # Only delete files older than keep_days
        now = time.time()
        deleted_count = 0
        
        for file_path, mtime in delete_candidates:
            # Check if the file is older than keep_days
            age_days = (now - mtime) / (24 * 60 * 60)
            
            if age_days > keep_days:
                try:
                    os.remove(file_path)
                    logger.info(f"Deleted old backup: {file_path} (age: {age_days:.1f} days)")
                    deleted_count += 1
                except Exception as e:
                    logger.warning(f"Failed to delete backup file {file_path}: {str(e)}")
        
        logger.info(f"Cleaned up {deleted_count} old backup files, kept {len(kept_files)}")
        return deleted_count
    
    except Exception as e:
        logger.error(f"Failed to clean old backups: {str(e)}")
        return 0