#!/usr/bin/env python3
"""
Database initialization script for kairoslms.

This script will create all database tables and optionally seed the database with
sample data for development and testing purposes.
"""
import os
import sys
import logging
import argparse
from dotenv import load_dotenv

# Add the parent directory to sys.path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Import the database module
from src.db import (
    create_tables, create_context_document, create_goal, create_task,
    create_status_overview
)

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)

def init_db(seed=False):
    """Initialize the database and optionally seed it with sample data."""
    # Create tables
    try:
        create_tables()
        logger.info("Database tables created successfully")
    except Exception as e:
        logger.error(f"Error creating database tables: {str(e)}")
        sys.exit(1)
    
    if seed:
        seed_db()

def seed_db():
    """Seed the database with sample data for development."""
    try:
        # Create a sample biography context document
        bio_doc = create_context_document(
            title="User Biography",
            content=(
                "Name: John Doe\n"
                "Age: 35\n"
                "Occupation: Software Engineer\n"
                "Hobbies: Hiking, reading, and cooking\n"
                "Family: Married with two children\n"
                "Interests: Machine learning, sustainable living, and personal productivity\n"
            ),
            document_type="biography"
        )
        logger.info(f"Created biography document with ID: {bio_doc.id}")
        
        # Create a sample high-level goal
        career_goal = create_goal(
            title="Career Advancement",
            description="Advance career in software engineering with a focus on machine learning",
            goal_type="high_level",
            importance=9.0
        )
        logger.info(f"Created high-level goal with ID: {career_goal.id}")
        
        # Create a project-level goal as a child of the career goal
        ml_project_goal = create_goal(
            title="Complete ML Certification",
            description="Complete a machine learning certification program within the next 6 months",
            goal_type="project_level",
            importance=8.5,
            parent_id=career_goal.id
        )
        logger.info(f"Created project-level goal with ID: {ml_project_goal.id}")
        
        # Create a task for the ML project goal
        study_task = create_task(
            title="Study for ML certification exam",
            description="Review course materials and practice exercises",
            goal_id=ml_project_goal.id,
            priority=8.0
        )
        logger.info(f"Created task with ID: {study_task.id}")
        
        # Create a subtask for the study task
        subtask = create_task(
            title="Complete practice quiz",
            description="Complete the practice quiz for the first module",
            parent_id=study_task.id,
            priority=7.5
        )
        logger.info(f"Created subtask with ID: {subtask.id}")
        
        # Create a status overview for the ML project goal
        overview = create_status_overview(
            goal_id=ml_project_goal.id,
            overview=(
                "The ML Certification project is on track. The user has completed "
                "40% of the course material and is consistently making progress. "
                "Current focus should be on completing the hands-on exercises."
            ),
            obstacles=(
                "Time constraints due to work commitments. Consider allocating specific "
                "study hours during the weekend to compensate for busy weekdays."
            )
        )
        logger.info(f"Created status overview with ID: {overview.id}")
        
        logger.info("Database seeded successfully with sample data")
    except Exception as e:
        logger.error(f"Error seeding database: {str(e)}")
        sys.exit(1)

if __name__ == "__main__":
    # Load environment variables
    load_dotenv(os.path.join(os.path.dirname(os.path.dirname(__file__)), "config", ".env"))
    
    # Parse command line arguments
    parser = argparse.ArgumentParser(description="Initialize the kairoslms database")
    parser.add_argument("--seed", action="store_true", help="Seed the database with sample data")
    args = parser.parse_args()
    
    init_db(seed=args.seed)