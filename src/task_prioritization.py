#!/usr/bin/env python
"""
Task Prioritization Module for KairosLMS

This module handles the prioritization of tasks and subtasks based on various criteria:
- Parent goal importance
- Imminent deadlines
- Impact on wellbeing

It also integrates with the LLM to enhance prioritization with reasoning.
"""

import logging
import os
from datetime import datetime, timedelta
from typing import Dict, List, Any, Tuple, Optional

import db
from src.llm_integration import get_llm

logger = logging.getLogger(__name__)

class TaskPrioritizer:
    """Class to handle the prioritization of tasks and subtasks."""
    
    def __init__(self):
        """Initialize the TaskPrioritizer class."""
        self.db = db.Database()
        
        # Define weight factors for prioritization
        self.weights = {
            "goal_importance": 0.4,  # Weight for parent goal importance
            "deadline": 0.3,         # Weight for deadline urgency
            "wellbeing": 0.3,        # Weight for wellbeing impact
        }
    
    def get_tasks_to_prioritize(self, days_ahead: int = 7) -> List[Dict[str, Any]]:
        """
        Get all tasks that need prioritization within the specified timeframe.
        
        Args:
            days_ahead (int): Number of days ahead to consider for task prioritization
            
        Returns:
            List[Dict[str, Any]]: List of tasks to prioritize
        """
        try:
            # Calculate date range
            today = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
            end_date = today + timedelta(days=days_ahead)
            
            # Get active tasks due within the date range or with no due date
            tasks = self.db.get_active_tasks(end_date=end_date)
            
            logger.info(f"Retrieved {len(tasks)} tasks for prioritization")
            return tasks
            
        except Exception as e:
            logger.error(f"Error retrieving tasks for prioritization: {str(e)}")
            return []
    
    def calculate_goal_importance_score(self, task: Dict[str, Any]) -> float:
        """
        Calculate a score based on the importance of the parent goal.
        
        Args:
            task (Dict[str, Any]): Task to calculate score for
            
        Returns:
            float: Goal importance score (0 to 1)
        """
        try:
            goal_id = task.get('goal_id')
            
            if not goal_id:
                return 0.0
            
            # Get the parent goal
            goal = self.db.get_goal_by_id(goal_id)
            
            if not goal:
                return 0.0
            
            # Calculate score based on goal priority and goal type
            goal_priority = goal.get('priority', 'medium').lower()
            goal_type = goal.get('type', 'project').lower()
            
            # Priority score: high (1.0), medium (0.6), low (0.3)
            priority_scores = {
                'high': 1.0,
                'medium': 0.6,
                'low': 0.3
            }
            
            # Type multiplier: high-level (1.2), project (1.0), other (0.8)
            type_multipliers = {
                'high_level': 1.2,
                'project': 1.0,
                'other': 0.8
            }
            
            # Calculate the score
            priority_score = priority_scores.get(goal_priority, 0.5)
            type_multiplier = type_multipliers.get(goal_type, 0.8)
            
            return min(priority_score * type_multiplier, 1.0)  # Cap at 1.0
            
        except Exception as e:
            logger.error(f"Error calculating goal importance score: {str(e)}")
            return 0.5  # Default to mid-priority
    
    def calculate_deadline_score(self, task: Dict[str, Any]) -> float:
        """
        Calculate a score based on the urgency of the task deadline.
        
        Args:
            task (Dict[str, Any]): Task to calculate score for
            
        Returns:
            float: Deadline urgency score (0 to 1)
        """
        try:
            due_date_str = task.get('due_date')
            
            # If no due date, assign a neutral score
            if not due_date_str:
                return 0.5
            
            # Parse the due date
            due_date = datetime.fromisoformat(due_date_str)
            now = datetime.now()
            
            # If already overdue, assign highest score
            if due_date < now:
                return 1.0
            
            # Calculate days until deadline
            days_until_deadline = (due_date - now).days
            
            # Calculate score: closer deadlines get higher scores
            # Scale: same day (1.0) to 14+ days away (0.1)
            if days_until_deadline == 0:  # Due today
                return 1.0
            elif days_until_deadline <= 1:  # Due tomorrow
                return 0.9
            elif days_until_deadline <= 2:  # Due in 2 days
                return 0.8
            elif days_until_deadline <= 3:  # Due in 3 days
                return 0.7
            elif days_until_deadline <= 5:  # Due within a work week
                return 0.6
            elif days_until_deadline <= 7:  # Due within a week
                return 0.5
            elif days_until_deadline <= 10:  # Due within 10 days
                return 0.3
            elif days_until_deadline <= 14:  # Due within 2 weeks
                return 0.2
            else:  # Due more than 2 weeks away
                return 0.1
                
        except Exception as e:
            logger.error(f"Error calculating deadline score: {str(e)}")
            return 0.5  # Default to mid-priority
    
    def calculate_wellbeing_score(self, task: Dict[str, Any]) -> float:
        """
        Calculate a score based on the task's impact on wellbeing.
        
        Args:
            task (Dict[str, Any]): Task to calculate score for
            
        Returns:
            float: Wellbeing impact score (0 to 1)
        """
        try:
            # Check if the task has an explicit wellbeing tag or category
            wellbeing_impact = task.get('wellbeing_impact', 'neutral').lower()
            
            # Assign scores based on wellbeing impact tags
            wellbeing_scores = {
                'high_positive': 1.0,  # High positive impact on wellbeing
                'positive': 0.8,       # Positive impact
                'neutral': 0.5,        # Neutral impact
                'negative': 0.3,       # Tasks that might have negative impact
                'high_negative': 0.1   # Tasks with high negative impact
            }
            
            # Keyword-based scoring for tasks without explicit tags
            if wellbeing_impact == 'neutral':
                task_title = task.get('title', '').lower()
                task_description = task.get('description', '').lower()
                
                # Keywords suggesting positive wellbeing impact
                positive_keywords = [
                    'health', 'exercise', 'meditate', 'relax', 'break', 
                    'rest', 'hobby', 'enjoy', 'fun', 'family', 'friend'
                ]
                
                # Keywords suggesting high priority/stress
                stress_keywords = [
                    'urgent', 'critical', 'deadline', 'overdue',
                    'late', 'priority', 'emergency'
                ]
                
                # Check for positive wellbeing keywords
                for keyword in positive_keywords:
                    if keyword in task_title or keyword in task_description:
                        return 0.8  # Positive impact
                
                # Reduce priority for potentially stressful tasks
                for keyword in stress_keywords:
                    if keyword in task_title or keyword in task_description:
                        return 0.3  # Could have negative impact
            
            return wellbeing_scores.get(wellbeing_impact, 0.5)
            
        except Exception as e:
            logger.error(f"Error calculating wellbeing score: {str(e)}")
            return 0.5  # Default to neutral
    
    def calculate_priority_score(self, task: Dict[str, Any]) -> float:
        """
        Calculate the overall priority score for a task.
        
        Args:
            task (Dict[str, Any]): Task to calculate priority for
            
        Returns:
            float: Overall priority score (0 to 1)
        """
        try:
            # Calculate individual component scores
            goal_score = self.calculate_goal_importance_score(task)
            deadline_score = self.calculate_deadline_score(task)
            wellbeing_score = self.calculate_wellbeing_score(task)
            
            # Calculate weighted sum
            weighted_score = (
                goal_score * self.weights["goal_importance"] +
                deadline_score * self.weights["deadline"] +
                wellbeing_score * self.weights["wellbeing"]
            )
            
            # Ensure score is within 0-1 range
            return max(0.0, min(weighted_score, 1.0))
            
        except Exception as e:
            logger.error(f"Error calculating priority score: {str(e)}")
            return 0.5  # Default to mid-priority
    
    def categorize_priority(self, score: float) -> str:
        """
        Convert a numerical priority score to a category.
        
        Args:
            score (float): Priority score between 0 and 1
            
        Returns:
            str: Priority category ('high', 'medium', or 'low')
        """
        if score >= 0.7:
            return 'high'
        elif score >= 0.4:
            return 'medium'
        else:
            return 'low'
    
    def prioritize_tasks(self, use_llm: bool = True) -> List[Dict[str, Any]]:
        """
        Prioritize all tasks based on the calculated scores and LLM reasoning.
        
        Args:
            use_llm (bool): Whether to use LLM for enhanced prioritization
            
        Returns:
            List[Dict[str, Any]]: Prioritized list of tasks with updated priorities
        """
        try:
            # Get tasks to prioritize
            tasks = self.get_tasks_to_prioritize()
            
            if not tasks:
                logger.info("No tasks to prioritize")
                return []
            
            # First pass: Calculate priority scores using our algorithm
            for task in tasks:
                # Skip tasks with manual_priority flag set
                if not task.get('manual_priority_set', False):
                    # Calculate priority score
                    priority_score = self.calculate_priority_score(task)
                    task['priority_score'] = priority_score
                    task['priority_category'] = self.categorize_priority(priority_score)
            
            # Second pass: Enhance prioritization with LLM (if enabled)
            if use_llm and os.getenv("ANTHROPIC_API_KEY"):
                try:
                    # Get relevant goals for context
                    goal_ids = list(set(task.get('goal_id') for task in tasks if task.get('goal_id')))
                    goals = [self.db.get_goal_by_id(goal_id) for goal_id in goal_ids]
                    goals = [goal for goal in goals if goal]  # Filter out None values
                    
                    # Get wellbeing context
                    wellbeing_doc = self.db.get_context_document_by_type("wellbeing_priorities")
                    wellbeing_priorities = wellbeing_doc.get('content', '') if wellbeing_doc else "No wellbeing priorities set"
                    
                    # Get calendar context
                    calendar_events = self.db.get_upcoming_calendar_events(days=7)
                    
                    # Prepare context for LLM
                    context = {
                        "wellbeing_priorities": wellbeing_priorities,
                        "calendar_events": calendar_events
                    }
                    
                    # Get LLM instance
                    llm = get_llm()
                    
                    # Get LLM-enhanced prioritization
                    llm_prioritized_tasks = llm.prioritize_tasks(tasks, goals, context)
                    
                    # Merge LLM priorities with our algorithm's priorities
                    for i, task in enumerate(tasks):
                        if i < len(llm_prioritized_tasks) and not task.get('manual_priority_set', False):
                            llm_task = llm_prioritized_tasks[i]
                            
                            # Get the LLM priority score (1-10 scale converted to 0-1)
                            llm_score = llm_task.get('llm_priority', 5) / 10
                            
                            # Get algorithm score
                            algo_score = task.get('priority_score', 0.5)
                            
                            # Blend the scores (60% LLM, 40% algorithm)
                            blended_score = (llm_score * 0.6) + (algo_score * 0.4)
                            
                            # Update task with blended score and LLM reasoning
                            task['priority_score'] = blended_score
                            task['priority_category'] = self.categorize_priority(blended_score)
                            task['llm_reasoning'] = llm_task.get('llm_reasoning', '')
                    
                    logger.info("Enhanced task prioritization with LLM reasoning")
                    
                except Exception as e:
                    logger.error(f"Error using LLM for task prioritization: {str(e)}")
                    logger.info("Falling back to algorithm-only prioritization")
            
            # Final pass: Update the database and prepare the return value
            prioritized_tasks = []
            
            for task in tasks:
                # Skip tasks with manual_priority flag set
                if task.get('manual_priority_set', False):
                    logger.debug(f"Skipping task {task.get('id')} as manual priority is set")
                    prioritized_tasks.append(task)
                    continue
                
                # Get the final priority data
                priority_score = task.get('priority_score', 0.5)
                priority_category = task.get('priority_category', 'medium')
                
                # Update task with new priority info for return
                updated_task = {
                    **task,
                    'priority': priority_category,
                    'priority_score': priority_score,
                    'last_prioritized': datetime.now().isoformat()
                }
                
                if 'llm_reasoning' in task:
                    updated_task['llm_reasoning'] = task['llm_reasoning']
                
                # Update in database
                update_data = {
                    'priority': priority_category,
                    'priority_score': priority_score,
                    'last_prioritized': datetime.now().isoformat()
                }
                
                if 'llm_reasoning' in task:
                    update_data['llm_reasoning'] = task['llm_reasoning']
                
                self.db.update_task(task.get('id'), update_data)
                
                prioritized_tasks.append(updated_task)
            
            # Sort tasks by priority score (descending)
            prioritized_tasks.sort(key=lambda x: x.get('priority_score', 0), reverse=True)
            
            logger.info(f"Successfully prioritized {len(prioritized_tasks)} tasks")
            return prioritized_tasks
            
        except Exception as e:
            logger.error(f"Error prioritizing tasks: {str(e)}")
            return []
    
    def update_task_priority_manually(self, task_id: str, priority: str) -> bool:
        """
        Manually update a task's priority.
        
        Args:
            task_id (str): ID of the task to update
            priority (str): New priority ('high', 'medium', 'low')
            
        Returns:
            bool: True if successful, False otherwise
        """
        try:
            if priority not in ['high', 'medium', 'low']:
                logger.error(f"Invalid priority value: {priority}")
                return False
            
            # Convert priority to score for consistency
            priority_scores = {
                'high': 0.9,
                'medium': 0.5,
                'low': 0.1
            }
            
            # Update task
            update_data = {
                'priority': priority,
                'priority_score': priority_scores.get(priority, 0.5),
                'manual_priority_set': True,
                'last_prioritized': datetime.now().isoformat()
            }
            
            self.db.update_task(task_id, update_data)
            logger.info(f"Manually updated priority for task {task_id} to {priority}")
            
            return True
            
        except Exception as e:
            logger.error(f"Error updating task priority manually: {str(e)}")
            return False


def run_task_prioritization(use_llm: bool = True):
    """
    Function to execute task prioritization as a scheduled task.
    
    Args:
        use_llm (bool): Whether to use LLM for enhanced prioritization
    
    Returns:
        bool: True if successful, False otherwise
    """
    try:
        logger.info("Starting task prioritization...")
        prioritizer = TaskPrioritizer()
        
        # Run prioritization
        prioritized_tasks = prioritizer.prioritize_tasks(use_llm=use_llm)
        
        # Log whether LLM was used
        if use_llm and os.getenv("ANTHROPIC_API_KEY"):
            logger.info(f"Task prioritization with LLM completed for {len(prioritized_tasks)} tasks")
        else:
            logger.info(f"Task prioritization (algorithm-only) completed for {len(prioritized_tasks)} tasks")
        
        return True
    
    except Exception as e:
        logger.error(f"Error in task prioritization: {str(e)}")
        return False


if __name__ == "__main__":
    # Configure logging
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    )
    
    # Run the task prioritization
    success = run_task_prioritization()
    if success:
        print("Task prioritization completed successfully")
    else:
        print("Task prioritization failed")