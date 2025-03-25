"""
Tests for data processing functionality in kairoslms.

This module tests the status_overview, task_prioritization, and data_processor modules.
"""
import unittest
from unittest.mock import patch, MagicMock
import datetime
import os
import sys

# Add parent directory to path to allow importing module
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from src.status_overview import StatusOverview, run_status_overview_generation
from src.task_prioritization import TaskPrioritizer, run_task_prioritization
from src.data_processor import DataProcessor, run_data_processing


class TestStatusOverview(unittest.TestCase):
    """Tests for the StatusOverview class and related functions."""
    
    @patch('src.status_overview.db.Database')
    def setUp(self, mock_db):
        """Set up test environment."""
        self.mock_db = mock_db
        self.status_overview = StatusOverview()
    
    def test_read_current_goals(self):
        """Test reading current goals from the database."""
        # Configure mock
        self.status_overview.db.get_goals.side_effect = [
            [{"id": "1", "title": "Goal 1", "type": "high_level"}],
            [{"id": "2", "title": "Goal 2", "type": "project"}]
        ]
        
        # Call the method
        goals = self.status_overview.read_current_goals()
        
        # Assertions
        self.assertEqual(len(goals), 2)
        self.assertEqual(len(goals["high_level"]), 1)
        self.assertEqual(len(goals["project"]), 1)
        self.assertEqual(goals["high_level"][0]["title"], "Goal 1")
        self.assertEqual(goals["project"][0]["title"], "Goal 2")
        
        # Verify get_goals was called with the correct parameters
        self.status_overview.db.get_goals.assert_any_call(goal_type="high_level")
        self.status_overview.db.get_goals.assert_any_call(goal_type="project")
    
    def test_process_new_inputs(self):
        """Test processing new inputs from various sources."""
        # Configure mocks
        self.status_overview.db.get_emails.return_value = [{"id": "1", "subject": "Test Email"}]
        self.status_overview.db.get_calendar_events.return_value = [{"id": "1", "title": "Test Event"}]
        self.status_overview.db.get_tasks.return_value = [{"id": "1", "title": "Test Task"}]
        
        # Call the method
        inputs = self.status_overview.process_new_inputs(days_back=2)
        
        # Assertions
        self.assertEqual(len(inputs), 3)
        self.assertEqual(len(inputs["emails"]), 1)
        self.assertEqual(len(inputs["calendar_events"]), 1)
        self.assertEqual(len(inputs["tasks"]), 1)
        
        # Verify the db methods were called
        self.assertTrue(self.status_overview.db.get_emails.called)
        self.assertTrue(self.status_overview.db.get_calendar_events.called)
        self.assertTrue(self.status_overview.db.get_tasks.called)
    
    def test_generate_goal_description(self):
        """Test generating a goal description."""
        # Configure mocks
        self.status_overview.db.get_goal_by_id.return_value = {
            "id": "1",
            "title": "Test Goal",
            "description": "This is a test goal",
            "status": "in_progress",
            "progress": 50
        }
        self.status_overview.db.get_tasks_by_goal_id.return_value = [
            {"title": "Task 1", "status": "completed"},
            {"title": "Task 2", "status": "pending"}
        ]
        
        # Call the method
        description = self.status_overview.generate_goal_description("1")
        
        # Assertions
        self.assertIn("Test Goal", description)
        self.assertIn("in_progress", description)
        self.assertIn("50%", description)
        self.assertIn("This is a test goal", description)
        self.assertIn("Task 1", description)
        self.assertIn("Task 2", description)
        
        # Verify db methods were called with correct parameters
        self.status_overview.db.get_goal_by_id.assert_called_with("1")
        self.status_overview.db.get_tasks_by_goal_id.assert_called_with("1")
    
    @patch('src.status_overview.run_status_overview_generation')
    def test_run_status_overview_generation(self, mock_run):
        """Test the run_status_overview_generation function."""
        # Configure mock
        mock_run.return_value = True
        
        # Call the function
        result = run_status_overview_generation()
        
        # Assertions
        self.assertTrue(result)
        self.assertTrue(mock_run.called)


class TestTaskPrioritization(unittest.TestCase):
    """Tests for the TaskPrioritizer class and related functions."""
    
    @patch('src.task_prioritization.db.Database')
    def setUp(self, mock_db):
        """Set up test environment."""
        self.mock_db = mock_db
        self.task_prioritizer = TaskPrioritizer()
    
    def test_get_tasks_to_prioritize(self):
        """Test getting tasks to prioritize."""
        # Configure mock
        self.task_prioritizer.db.get_active_tasks.return_value = [
            {"id": "1", "title": "Task 1"},
            {"id": "2", "title": "Task 2"}
        ]
        
        # Call the method
        tasks = self.task_prioritizer.get_tasks_to_prioritize(days_ahead=7)
        
        # Assertions
        self.assertEqual(len(tasks), 2)
        self.assertEqual(tasks[0]["title"], "Task 1")
        self.assertEqual(tasks[1]["title"], "Task 2")
        
        # Verify get_active_tasks was called
        self.assertTrue(self.task_prioritizer.db.get_active_tasks.called)
    
    def test_calculate_goal_importance_score(self):
        """Test calculating goal importance score."""
        # Configure mock
        self.task_prioritizer.db.get_goal_by_id.return_value = {
            "id": "1",
            "priority": "high",
            "type": "high_level"
        }
        
        # Call the method with a task linked to a goal
        score = self.task_prioritizer.calculate_goal_importance_score({"goal_id": "1"})
        
        # Assertions
        self.assertGreaterEqual(score, 0.0)
        self.assertLessEqual(score, 1.0)
        self.assertGreaterEqual(score, 0.8)  # High priority high-level goal should have high score
        
        # Test with different goal parameters
        self.task_prioritizer.db.get_goal_by_id.return_value = {
            "id": "2",
            "priority": "low",
            "type": "project"
        }
        score = self.task_prioritizer.calculate_goal_importance_score({"goal_id": "2"})
        self.assertLessEqual(score, 0.5)  # Low priority project goal should have lower score
    
    def test_calculate_deadline_score(self):
        """Test calculating deadline score."""
        # Test overdue task
        yesterday = (datetime.datetime.now() - datetime.timedelta(days=1)).isoformat()
        score = self.task_prioritizer.calculate_deadline_score({"due_date": yesterday})
        self.assertEqual(score, 1.0)  # Overdue tasks should have highest score
        
        # Test task due today
        today = datetime.datetime.now().replace(hour=23, minute=59).isoformat()
        score = self.task_prioritizer.calculate_deadline_score({"due_date": today})
        self.assertEqual(score, 1.0)
        
        # Test task due in a week
        next_week = (datetime.datetime.now() + datetime.timedelta(days=7)).isoformat()
        score = self.task_prioritizer.calculate_deadline_score({"due_date": next_week})
        self.assertLessEqual(score, 0.7)
        self.assertGreaterEqual(score, 0.3)
    
    def test_calculate_priority_score(self):
        """Test calculating overall priority score."""
        # Configure mocks for component scores
        task = {"id": "1", "title": "Test Task", "goal_id": "1", "due_date": datetime.datetime.now().isoformat()}
        
        # Mock the individual scoring methods
        self.task_prioritizer.calculate_goal_importance_score = MagicMock(return_value=0.8)
        self.task_prioritizer.calculate_deadline_score = MagicMock(return_value=0.9)
        self.task_prioritizer.calculate_wellbeing_score = MagicMock(return_value=0.6)
        
        # Call the method
        score = self.task_prioritizer.calculate_priority_score(task)
        
        # Assertions
        self.assertGreaterEqual(score, 0.0)
        self.assertLessEqual(score, 1.0)
        
        # Verify scoring methods were called
        self.task_prioritizer.calculate_goal_importance_score.assert_called_with(task)
        self.task_prioritizer.calculate_deadline_score.assert_called_with(task)
        self.task_prioritizer.calculate_wellbeing_score.assert_called_with(task)
    
    @patch('src.task_prioritization.run_task_prioritization')
    def test_run_task_prioritization(self, mock_run):
        """Test the run_task_prioritization function."""
        # Configure mock
        mock_run.return_value = True
        
        # Call the function
        result = run_task_prioritization()
        
        # Assertions
        self.assertTrue(result)
        self.assertTrue(mock_run.called)


class TestDataProcessor(unittest.TestCase):
    """Tests for the DataProcessor class and related functions."""
    
    def setUp(self):
        """Set up test environment."""
        # Patch the imported modules
        patcher1 = patch('src.data_processor.status_overview.StatusOverview')
        patcher2 = patch('src.data_processor.task_prioritization.TaskPrioritizer')
        
        self.mock_status_overview = patcher1.start()
        self.mock_task_prioritizer = patcher2.start()
        
        # Add cleanup to stop patchers
        self.addCleanup(patcher1.stop)
        self.addCleanup(patcher2.stop)
        
        # Initialize processor
        self.data_processor = DataProcessor()
    
    def test_process_all_data(self):
        """Test processing all data."""
        # Configure mocks
        self.data_processor.status_generator.generate_status_overview.return_value = {
            "overviews": [{"goal_id": "1"}, {"goal_id": "2"}]
        }
        self.data_processor.task_prioritizer.prioritize_tasks.return_value = [
            {"id": "1"}, {"id": "2"}, {"id": "3"}
        ]
        
        # Call the method
        results = self.data_processor.process_all_data()
        
        # Assertions
        self.assertTrue(results["status_overview_success"])
        self.assertEqual(results["goals_processed"], 2)
        self.assertEqual(results["tasks_prioritized"], 3)
        self.assertEqual(len(results["errors"]), 0)
        
        # Verify methods were called
        self.assertTrue(self.data_processor.status_generator.generate_status_overview.called)
        self.assertTrue(self.data_processor.task_prioritizer.prioritize_tasks.called)
    
    def test_process_specific_goal(self):
        """Test processing a specific goal."""
        # Configure mocks
        self.data_processor.status_generator.generate_status_overview.return_value = {
            "goal_id": "1",
            "description": "Test description"
        }
        self.data_processor.task_prioritizer.prioritize_tasks.return_value = [
            {"id": "1", "goal_id": "1"}, 
            {"id": "2", "goal_id": "1"},
            {"id": "3", "goal_id": "2"}  # Different goal
        ]
        
        # Call the method
        results = self.data_processor.process_specific_goal("1")
        
        # Assertions
        self.assertTrue(results["status_overview_success"])
        self.assertEqual(results["related_tasks_prioritized"], 2)
        self.assertEqual(len(results["errors"]), 0)
        
        # Verify methods were called with correct parameters
        self.data_processor.status_generator.generate_status_overview.assert_called_with("1")
        self.assertTrue(self.data_processor.task_prioritizer.prioritize_tasks.called)
    
    @patch('src.data_processor.run_data_processing')
    def test_run_data_processing(self, mock_run):
        """Test the run_data_processing function."""
        # Configure mock
        mock_run.return_value = {"status_overview_success": True, "tasks_prioritized": 3}
        
        # Call the function without goal_id
        result = run_data_processing()
        
        # Assertions
        self.assertEqual(result["status_overview_success"], True)
        self.assertEqual(result["tasks_prioritized"], 3)
        
        # Call the function with goal_id
        result = run_data_processing(goal_id="1")
        
        # Ensure function was called with the goal_id
        mock_run.assert_called_with(goal_id="1")


if __name__ == '__main__':
    unittest.main()