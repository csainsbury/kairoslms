#!/usr/bin/env python
"""
Status Overview Generation Module for KairosLMS

This module processes data from various sources (emails, calendar events, Todoist tasks)
to generate status overviews for high-level and project-level goals.

It integrates with the LLM to provide enhanced reasoning and insights.
"""

import logging
import os
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any

import db
from src.llm_integration import get_llm

logger = logging.getLogger(__name__)

class StatusOverview:
    """Class to handle the generation and management of status overviews."""
    
    def __init__(self):
        """Initialize the StatusOverview class."""
        self.db = db.Database()
    
    def read_current_goals(self) -> Dict[str, Any]:
        """
        Read current high-level and project-level goals from the database.
        
        Returns:
            Dict[str, Any]: Dictionary containing high-level and project-level goals
        """
        try:
            high_level_goals = self.db.get_goals(goal_type="high_level")
            project_goals = self.db.get_goals(goal_type="project")
            
            return {
                "high_level": high_level_goals,
                "project": project_goals
            }
        except Exception as e:
            logger.error(f"Error reading current goals: {str(e)}")
            return {"high_level": [], "project": []}
    
    def process_new_inputs(self, 
                         days_back: int = 1) -> Dict[str, List[Any]]:
        """
        Process new inputs from emails, tasks, and calendar events.
        
        Args:
            days_back (int): Number of days to look back for new inputs
            
        Returns:
            Dict[str, List[Any]]: Dictionary containing processed inputs by type
        """
        try:
            # Calculate the date range for fetching recent inputs
            end_date = datetime.now()
            start_date = end_date - timedelta(days=days_back)
            
            # Fetch recent emails, calendar events, and tasks
            emails = self.db.get_emails(start_date=start_date, end_date=end_date)
            calendar_events = self.db.get_calendar_events(start_date=start_date, end_date=end_date)
            tasks = self.db.get_tasks(start_date=start_date, end_date=end_date)
            
            return {
                "emails": emails,
                "calendar_events": calendar_events,
                "tasks": tasks
            }
        except Exception as e:
            logger.error(f"Error processing new inputs: {str(e)}")
            return {"emails": [], "calendar_events": [], "tasks": []}
    
    def generate_goal_description(self, goal_id: str, use_llm: bool = True) -> str:
        """
        Generate a detailed description of a goal based on available information.
        
        Args:
            goal_id (str): ID of the goal to describe
            use_llm (bool): Whether to use LLM for enhanced description
            
        Returns:
            str: Generated description of the goal
        """
        try:
            # Get the goal data from the database
            goal = self.db.get_goal_by_id(goal_id)
            
            if not goal:
                return "Goal not found"
            
            # Get related tasks for this goal
            related_tasks = self.db.get_tasks_by_goal_id(goal_id)
            
            # Check if LLM should be used and is available
            if use_llm and os.getenv("ANTHROPIC_API_KEY"):
                try:
                    # Get biography and other context documents
                    biography = self.db.get_context_document_by_type("biography")
                    bio_content = biography.get('content', '') if biography else ''
                    
                    # Get relevant recent emails
                    recent_emails = self.db.get_emails(days=7, limit=10)
                    
                    # Get upcoming calendar events
                    calendar_events = self.db.get_upcoming_calendar_events(days=14)
                    
                    # Prepare context for LLM
                    context = {
                        "biography": bio_content,
                        "emails": recent_emails,
                        "calendar_events": calendar_events
                    }
                    
                    # Get LLM instance
                    llm = get_llm()
                    
                    # Get enhanced analysis from LLM
                    analysis = llm.generate_goal_analysis(goal, related_tasks, context)
                    
                    # Construct a comprehensive description with LLM insights
                    description = f"# Goal: {goal.get('title', 'Untitled')}\n\n"
                    description += f"## Current Status\n{analysis.get('summary', 'No summary available')}\n\n"
                    
                    # Add next steps from LLM
                    next_steps = analysis.get('next_steps', [])
                    if next_steps:
                        description += "## Recommended Next Steps\n"
                        for i, step in enumerate(next_steps, 1):
                            description += f"{i}. {step}\n"
                        description += "\n"
                    
                    # Add obstacles identified by LLM
                    obstacles = analysis.get('obstacles', [])
                    if obstacles:
                        description += "## Potential Obstacles\n"
                        for obstacle in obstacles:
                            description += f"- {obstacle}\n"
                        description += "\n"
                    
                    # Include existing tasks for reference
                    if related_tasks:
                        description += "## Current Tasks\n"
                        completed_tasks = [t for t in related_tasks if t.get('completed', False)]
                        active_tasks = [t for t in related_tasks if not t.get('completed', False)]
                        
                        if active_tasks:
                            description += "Active:\n"
                            for task in active_tasks:
                                deadline = f" (Due: {task.get('deadline')})" if task.get('deadline') else ""
                                description += f"- {task.get('title', 'Untitled task')}{deadline}\n"
                        
                        if completed_tasks:
                            description += "Completed:\n"
                            for task in completed_tasks:
                                description += f"- ✓ {task.get('title', 'Untitled task')}\n"
                    
                    logger.info(f"Generated LLM-enhanced description for goal {goal_id}")
                    return description
                    
                except Exception as e:
                    logger.error(f"Error using LLM for goal description: {str(e)}")
                    logger.info("Falling back to standard description generation")
            
            # Standard description generation (without LLM)
            description = f"Goal: {goal.get('title', 'Untitled')}\n"
            description += f"Status: {goal.get('status', 'Unknown')}\n"
            description += f"Progress: {goal.get('progress', 0)}%\n\n"
            description += f"Description: {goal.get('description', 'No description available')}\n\n"
            
            if related_tasks:
                description += "Related Tasks:\n"
                for task in related_tasks:
                    status = "✓" if task.get('completed', False) else "☐"
                    description += f"- {status} {task.get('title', 'Untitled task')}\n"
            
            return description
        except Exception as e:
            logger.error(f"Error generating goal description for goal {goal_id}: {str(e)}")
            return "Error generating goal description"
    
    def breakdown_into_subtasks(self, goal_id: str) -> List[Dict[str, Any]]:
        """
        Break down a goal into actionable subtasks.
        
        Args:
            goal_id (str): ID of the goal to break down
            
        Returns:
            List[Dict[str, Any]]: List of subtasks
        """
        try:
            # Get the goal data
            goal = self.db.get_goal_by_id(goal_id)
            
            if not goal:
                return []
            
            # Get existing subtasks
            existing_subtasks = self.db.get_tasks_by_goal_id(goal_id)
            
            # This logic will be enhanced with LLM integration in Task 5
            # For now, we're implementing a basic subtask generation logic
            subtasks = []
            
            # Check what subtasks are missing based on the goal type and content
            goal_type = goal.get('type', '')
            goal_title = goal.get('title', '')
            
            # Example of simple rule-based subtask generation
            if goal_type == "project":
                # Standard project subtasks if they don't exist already
                standard_subtasks = [
                    {"title": "Define project scope", "priority": "high"},
                    {"title": "Create project timeline", "priority": "high"},
                    {"title": "Identify key stakeholders", "priority": "medium"},
                    {"title": "Set up project tracking", "priority": "medium"},
                    {"title": "Schedule regular reviews", "priority": "low"}
                ]
                
                # Add standard subtasks if they don't exist
                existing_titles = [task.get('title', '') for task in existing_subtasks]
                for task in standard_subtasks:
                    if task["title"] not in existing_titles:
                        task["goal_id"] = goal_id
                        task["created_at"] = datetime.now().isoformat()
                        task["status"] = "pending"
                        subtasks.append(task)
            
            return subtasks
        except Exception as e:
            logger.error(f"Error breaking down goal {goal_id} into subtasks: {str(e)}")
            return []
    
    def identify_obstacles(self, goal_id: str, use_llm: bool = True) -> List[Dict[str, Any]]:
        """
        Identify potential obstacles for a goal and generate remedial subtasks.
        
        Args:
            goal_id (str): ID of the goal to analyze
            use_llm (bool): Whether to use LLM for enhanced obstacle identification
            
        Returns:
            List[Dict[str, Any]]: List of remedial subtasks
        """
        try:
            # Get the goal data
            goal = self.db.get_goal_by_id(goal_id)
            
            if not goal:
                return []
            
            # Get related tasks and their status
            related_tasks = self.db.get_tasks_by_goal_id(goal_id)
            
            # Check if LLM should be used and is available
            if use_llm and os.getenv("ANTHROPIC_API_KEY"):
                try:
                    # Get past obstacles and other context
                    past_obstacles = self.db.get_past_obstacles(goal_id, limit=5)
                    
                    # Get time constraints from calendar
                    calendar_events = self.db.get_upcoming_calendar_events(days=14)
                    
                    # Prepare context for LLM
                    context = {
                        "time_constraints": f"{len(calendar_events)} upcoming events in the next 14 days",
                        "resources": "Standard resources available",  # This could be customized
                        "past_obstacles": past_obstacles if past_obstacles else "No recorded past obstacles"
                    }
                    
                    # Get LLM instance
                    llm = get_llm()
                    
                    # Get enhanced obstacle analysis from LLM
                    obstacles_analysis = llm.identify_obstacles(goal, related_tasks, context)
                    
                    # Extract remedial tasks from LLM analysis
                    llm_remedial_tasks = obstacles_analysis.get('remedial_tasks', [])
                    
                    # Format the remedial tasks for the database
                    formatted_tasks = []
                    for task in llm_remedial_tasks:
                        remedial_task = {
                            "title": task.get('title', 'Untitled remedial task'),
                            "priority": "high",  # Default to high for remedial tasks
                            "priority_score": task.get('priority', 7) / 10,  # Convert 1-10 scale to 0-1
                            "goal_id": goal_id,
                            "created_at": datetime.now().isoformat(),
                            "status": "pending",
                            "related_to_obstacle": task.get('for_obstacle', 'Unknown obstacle'),
                            "is_remedial": True
                        }
                        formatted_tasks.append(remedial_task)
                    
                    logger.info(f"Identified {len(formatted_tasks)} obstacles using LLM for goal {goal_id}")
                    return formatted_tasks
                    
                except Exception as e:
                    logger.error(f"Error using LLM for obstacle identification: {str(e)}")
                    logger.info("Falling back to basic obstacle detection")
            
            # Basic obstacle detection logic (without LLM)
            remedial_tasks = []
            
            # Check for tasks that are overdue or blocked
            overdue_tasks = [
                task for task in related_tasks 
                if task.get('status') != 'completed' and
                task.get('due_date') and 
                datetime.fromisoformat(task.get('due_date')) < datetime.now()
            ]
            
            blocked_tasks = [
                task for task in related_tasks
                if task.get('status') == 'blocked'
            ]
            
            # Create remedial tasks for overdue tasks
            for task in overdue_tasks:
                remedial_task = {
                    "title": f"Resolve overdue task: {task.get('title', 'Untitled')}",
                    "priority": "high",
                    "priority_score": 0.9,  # High priority score
                    "goal_id": goal_id,
                    "created_at": datetime.now().isoformat(),
                    "status": "pending",
                    "related_to_task_id": task.get('id'),
                    "is_remedial": True
                }
                remedial_tasks.append(remedial_task)
            
            # Create remedial tasks for blocked tasks
            for task in blocked_tasks:
                remedial_task = {
                    "title": f"Unblock task: {task.get('title', 'Untitled')}",
                    "priority": "high",
                    "priority_score": 0.9,  # High priority score
                    "goal_id": goal_id,
                    "created_at": datetime.now().isoformat(),
                    "status": "pending",
                    "related_to_task_id": task.get('id'),
                    "is_remedial": True
                }
                remedial_tasks.append(remedial_task)
            
            return remedial_tasks
        except Exception as e:
            logger.error(f"Error identifying obstacles for goal {goal_id}: {str(e)}")
            return []
    
    def generate_status_overview(self, goal_id: Optional[str] = None, use_llm: bool = True) -> Dict[str, Any]:
        """
        Generate a comprehensive status overview for a specific goal or all goals.
        
        Args:
            goal_id (Optional[str]): Specific goal ID to generate overview for.
                                     If None, generates overview for all goals.
            use_llm (bool): Whether to use LLM for enhanced overview generation
                                     
        Returns:
            Dict[str, Any]: Status overview containing goal descriptions,
                           subtasks, and identified obstacles
        """
        try:
            # If goal_id is provided, generate overview for that specific goal
            if goal_id:
                goal = self.db.get_goal_by_id(goal_id)
                
                if not goal:
                    return {"error": "Goal not found"}
                
                # Check if we should use LLM
                llm_available = use_llm and os.getenv("ANTHROPIC_API_KEY")
                
                # Generate all components for this goal
                description = self.generate_goal_description(goal_id, use_llm=llm_available)
                new_subtasks = self.breakdown_into_subtasks(goal_id)
                remedial_tasks = self.identify_obstacles(goal_id, use_llm=llm_available)
                
                # Create and save the status overview
                overview = {
                    "goal_id": goal_id,
                    "timestamp": datetime.now().isoformat(),
                    "description": description,
                    "new_subtasks": new_subtasks,
                    "remedial_tasks": remedial_tasks,
                    "llm_enhanced": llm_available
                }
                
                # Save the overview to the database
                self.db.save_status_overview(overview)
                
                # Log whether LLM was used
                if llm_available:
                    logger.info(f"Generated LLM-enhanced status overview for goal {goal_id}")
                else:
                    logger.info(f"Generated standard status overview for goal {goal_id}")
                
                return overview
            
            # If no goal_id is provided, generate overviews for all goals
            else:
                # Get all goals
                goals = self.read_current_goals()
                all_goals = goals.get('high_level', []) + goals.get('project', [])
                
                overviews = []
                for goal in all_goals:
                    goal_id = goal.get('id')
                    if goal_id:
                        overview = self.generate_status_overview(goal_id, use_llm=use_llm)
                        overviews.append(overview)
                
                return {"overviews": overviews}
        
        except Exception as e:
            logger.error(f"Error generating status overview: {str(e)}")
            return {"error": f"Failed to generate status overview: {str(e)}"}
    
    def save_new_subtasks(self, subtasks: List[Dict[str, Any]]) -> bool:
        """
        Save new subtasks to the database.
        
        Args:
            subtasks (List[Dict[str, Any]]): List of subtasks to save
            
        Returns:
            bool: True if successful, False otherwise
        """
        try:
            for task in subtasks:
                self.db.create_task(task)
            return True
        except Exception as e:
            logger.error(f"Error saving new subtasks: {str(e)}")
            return False
    
    def update_goal_status(self, goal_id: str, status_update: Dict[str, Any]) -> bool:
        """
        Update the status of a goal based on the latest overview.
        
        Args:
            goal_id (str): ID of the goal to update
            status_update (Dict[str, Any]): Status update information
            
        Returns:
            bool: True if successful, False otherwise
        """
        try:
            self.db.update_goal(goal_id, status_update)
            return True
        except Exception as e:
            logger.error(f"Error updating goal status: {str(e)}")
            return False


def run_status_overview_generation(use_llm: bool = True):
    """
    Function to execute status overview generation as a scheduled task.
    
    Args:
        use_llm (bool): Whether to use LLM for enhanced overview generation
    
    Returns:
        bool: True if successful, False otherwise
    """
    try:
        logger.info("Starting status overview generation...")
        status_overview = StatusOverview()
        
        # Check if LLM is available when requested
        llm_available = use_llm and os.getenv("ANTHROPIC_API_KEY")
        if use_llm and not os.getenv("ANTHROPIC_API_KEY"):
            logger.warning("LLM usage requested but ANTHROPIC_API_KEY is not set. Falling back to standard generation.")
        
        # Process recent inputs
        recent_inputs = status_overview.process_new_inputs()
        logger.info(f"Processed {len(recent_inputs.get('emails', []))} emails, "
                   f"{len(recent_inputs.get('calendar_events', []))} calendar events, "
                   f"{len(recent_inputs.get('tasks', []))} tasks")
        
        # Generate status overviews for all goals
        overviews = status_overview.generate_status_overview(use_llm=llm_available)
        
        if "error" in overviews:
            logger.error(f"Error in status overview generation: {overviews['error']}")
            return False
        
        if "overviews" in overviews:
            # Log whether LLM was used
            if llm_available:
                logger.info(f"Generated {len(overviews['overviews'])} LLM-enhanced status overviews")
            else:
                logger.info(f"Generated {len(overviews['overviews'])} standard status overviews")
        
        logger.info("Status overview generation completed successfully")
        return True
    
    except Exception as e:
        logger.error(f"Error in status overview generation: {str(e)}")
        return False


if __name__ == "__main__":
    # Configure logging
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    )
    
    # Run the status overview generation
    success = run_status_overview_generation()
    if success:
        print("Status overview generation completed successfully")
    else:
        print("Status overview generation failed")