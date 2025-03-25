#!/usr/bin/env python
"""
Data Processor Module for KairosLMS

This module coordinates the processing of ingested data, generating status overviews,
and prioritizing tasks. It serves as the central processing script that integrates
the functionality from the status_overview and task_prioritization modules.
"""

import logging
import time
from datetime import datetime
from typing import Dict, Any, Optional

import status_overview
import task_prioritization

logger = logging.getLogger(__name__)

class DataProcessor:
    """Class to coordinate data processing activities."""
    
    def __init__(self):
        """Initialize the DataProcessor class."""
        self.status_generator = status_overview.StatusOverview()
        self.task_prioritizer = task_prioritization.TaskPrioritizer()
    
    def process_all_data(self) -> Dict[str, Any]:
        """
        Process all data by generating status overviews and prioritizing tasks.
        
        Returns:
            Dict[str, Any]: Processing results summary
        """
        start_time = time.time()
        results = {
            "status_overview_success": False,
            "tasks_prioritized": 0,
            "goals_processed": 0,
            "timestamp": datetime.now().isoformat(),
            "errors": []
        }
        
        try:
            # Step 1: Generate status overviews for all goals
            logger.info("Starting status overview generation...")
            overviews = self.status_generator.generate_status_overview()
            
            if "error" in overviews:
                error_msg = f"Error in status overview generation: {overviews['error']}"
                logger.error(error_msg)
                results["errors"].append(error_msg)
            else:
                results["status_overview_success"] = True
                
                if "overviews" in overviews:
                    results["goals_processed"] = len(overviews["overviews"])
                    logger.info(f"Generated status overviews for {results['goals_processed']} goals")
            
            # Step 2: Prioritize all tasks
            logger.info("Starting task prioritization...")
            prioritized_tasks = self.task_prioritizer.prioritize_tasks()
            
            results["tasks_prioritized"] = len(prioritized_tasks)
            logger.info(f"Prioritized {results['tasks_prioritized']} tasks")
            
            # Record processing time
            end_time = time.time()
            processing_time = end_time - start_time
            results["processing_time_seconds"] = processing_time
            
            logger.info(f"Data processing completed in {processing_time:.2f} seconds")
            return results
            
        except Exception as e:
            error_msg = f"Error in data processing: {str(e)}"
            logger.error(error_msg)
            
            results["errors"].append(error_msg)
            results["processing_time_seconds"] = time.time() - start_time
            
            return results
    
    def process_specific_goal(self, goal_id: str) -> Dict[str, Any]:
        """
        Process data for a specific goal.
        
        Args:
            goal_id (str): ID of the goal to process
            
        Returns:
            Dict[str, Any]: Processing results for the goal
        """
        start_time = time.time()
        results = {
            "goal_id": goal_id,
            "status_overview_success": False,
            "related_tasks_prioritized": 0,
            "timestamp": datetime.now().isoformat(),
            "errors": []
        }
        
        try:
            # Step 1: Generate status overview for this goal
            logger.info(f"Generating status overview for goal {goal_id}...")
            overview = self.status_generator.generate_status_overview(goal_id)
            
            if "error" in overview:
                error_msg = f"Error generating status overview for goal {goal_id}: {overview['error']}"
                logger.error(error_msg)
                results["errors"].append(error_msg)
            else:
                results["status_overview_success"] = True
                logger.info(f"Generated status overview for goal {goal_id}")
            
            # Step 2: Prioritize related tasks
            # First, we need to get all tasks related to this goal
            logger.info(f"Prioritizing tasks for goal {goal_id}...")
            
            # The task_prioritizer already handles prioritization of all tasks
            # including those for this goal, so just run the full prioritization
            prioritized_tasks = self.task_prioritizer.prioritize_tasks()
            
            # Count how many of the prioritized tasks are related to this goal
            related_tasks = [task for task in prioritized_tasks if task.get('goal_id') == goal_id]
            results["related_tasks_prioritized"] = len(related_tasks)
            
            logger.info(f"Prioritized {len(related_tasks)} tasks for goal {goal_id}")
            
            # Record processing time
            end_time = time.time()
            processing_time = end_time - start_time
            results["processing_time_seconds"] = processing_time
            
            logger.info(f"Data processing for goal {goal_id} completed in {processing_time:.2f} seconds")
            return results
            
        except Exception as e:
            error_msg = f"Error processing data for goal {goal_id}: {str(e)}"
            logger.error(error_msg)
            
            results["errors"].append(error_msg)
            results["processing_time_seconds"] = time.time() - start_time
            
            return results


def run_data_processing(goal_id: Optional[str] = None) -> Dict[str, Any]:
    """
    Run the data processing as a standalone function.
    
    Args:
        goal_id (Optional[str]): If provided, process only this specific goal
        
    Returns:
        Dict[str, Any]: Processing results
    """
    processor = DataProcessor()
    
    if goal_id:
        logger.info(f"Running data processing for goal {goal_id}...")
        return processor.process_specific_goal(goal_id)
    else:
        logger.info("Running data processing for all goals and tasks...")
        return processor.process_all_data()


if __name__ == "__main__":
    # Configure logging
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    )
    
    # Run the data processing
    results = run_data_processing()
    
    if results.get("errors"):
        print(f"Data processing completed with {len(results['errors'])} errors:")
        for error in results["errors"]:
            print(f" - {error}")
    else:
        print(f"Data processing completed successfully:")
        print(f" - Processed {results.get('goals_processed', 0)} goals")
        print(f" - Prioritized {results.get('tasks_prioritized', 0)} tasks")
        print(f" - Processing time: {results.get('processing_time_seconds', 0):.2f} seconds")