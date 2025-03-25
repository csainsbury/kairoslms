"""
Unit tests for the LLM integration module.
"""

import os
import unittest
from unittest.mock import patch, MagicMock
import json

# Import the module to test
from src.llm_integration import LLMIntegration, get_llm


class TestLLMIntegration(unittest.TestCase):
    """Test cases for the LLM integration module."""
    
    def setUp(self):
        """Set up test fixtures."""
        # Mock environment variables
        self.env_patcher = patch.dict('os.environ', {'ANTHROPIC_API_KEY': 'test_api_key'})
        self.env_patcher.start()
        
        # Create a mock Anthropic client
        self.mock_client_patcher = patch('anthropic.Anthropic')
        self.mock_client = self.mock_client_patcher.start()
        
        # Set up mock response
        self.mock_response = MagicMock()
        self.mock_response.content = [MagicMock(text="Test response from LLM")]
        self.mock_response.usage.input_tokens = 100
        self.mock_response.usage.output_tokens = 50
        
        # Configure the mock client
        self.mock_client.return_value.messages.create.return_value = self.mock_response
        
        # Create the LLM integration instance
        self.llm = LLMIntegration(api_key='test_api_key')
    
    def tearDown(self):
        """Tear down test fixtures."""
        self.env_patcher.stop()
        self.mock_client_patcher.stop()
    
    def test_init_with_api_key(self):
        """Test initialization with explicit API key."""
        llm = LLMIntegration(api_key='explicit_key')
        self.assertEqual(llm.api_key, 'explicit_key')
        self.assertEqual(llm.model, 'claude-3-opus-20240229')  # Default model
    
    def test_init_with_env_var(self):
        """Test initialization with API key from environment."""
        llm = LLMIntegration()  # Should use env var
        self.assertEqual(llm.api_key, 'test_api_key')
    
    def test_init_with_custom_model(self):
        """Test initialization with custom model."""
        llm = LLMIntegration(model='claude-3-haiku-20240229')
        self.assertEqual(llm.model, 'claude-3-haiku-20240229')
    
    def test_query_llm_basic(self):
        """Test basic LLM query functionality."""
        response = self.llm.query_llm(prompt="Test prompt")
        
        # Verify client was called correctly
        self.mock_client.return_value.messages.create.assert_called_once()
        args, kwargs = self.mock_client.return_value.messages.create.call_args
        
        # Check that the model and prompt were passed correctly
        self.assertEqual(kwargs['model'], 'claude-3-opus-20240229')
        self.assertEqual(kwargs['messages'][0]['content'], "Test prompt")
        
        # Check response handling
        self.assertEqual(response, "Test response from LLM")
    
    def test_query_llm_with_system_prompt(self):
        """Test LLM query with custom system prompt."""
        custom_system = "Custom system prompt"
        self.llm.query_llm(prompt="Test prompt", system_prompt=custom_system)
        
        args, kwargs = self.mock_client.return_value.messages.create.call_args
        self.assertEqual(kwargs['system'], custom_system)
    
    def test_export_logs_to_string(self):
        """Test exporting logs as a string."""
        # Create a log entry
        self.llm.query_llm(prompt="Log test")
        
        # Export logs
        logs = self.llm.export_logs()
        
        # Verify logs format
        log_data = json.loads(logs)
        self.assertTrue(isinstance(log_data, list))
        self.assertEqual(len(log_data), 1)
        self.assertEqual(log_data[0]['prompt'], "Log test")
        self.assertTrue('success' in log_data[0])
        self.assertTrue('elapsed_time' in log_data[0])
    
    @patch('builtins.open', new_callable=unittest.mock.mock_open)
    def test_export_logs_to_file(self, mock_open):
        """Test exporting logs to a file."""
        # Create a log entry
        self.llm.query_llm(prompt="File log test")
        
        # Export logs to file
        result = self.llm.export_logs(file_path="test_logs.json")
        
        # Verify file operations
        mock_open.assert_called_once_with("test_logs.json", "w")
        self.assertTrue(result)  # Should return True for successful file write
    
    def test_generate_goal_analysis(self):
        """Test goal analysis generation."""
        # Mock data
        goal = {"title": "Test Goal", "description": "Goal description"}
        tasks = [{"title": "Task 1"}, {"title": "Task 2"}]
        context = {"biography": "Test bio"}
        
        # Set up mock response for structured data
        self.mock_response.content[0].text = """
        Here's my analysis of the goal:
        
        The goal is progressing well. There are a few tasks to complete.
        
        Next steps:
        - Complete Task 1
        - Start on Task 2
        - Plan for the next phase
        
        Potential obstacles:
        - Time constraints
        - Resource limitations
        """
        
        # Call the method
        analysis = self.llm.generate_goal_analysis(goal, tasks, context)
        
        # Verify the analysis was parsed correctly
        self.assertTrue('summary' in analysis)
        self.assertTrue('next_steps' in analysis)
        self.assertTrue('raw_response' in analysis)
    
    def test_prioritize_tasks(self):
        """Test task prioritization."""
        # Mock data
        tasks = [
            {"id": 1, "title": "Task 1", "deadline": "2023-12-31"},
            {"id": 2, "title": "Task 2"}
        ]
        goals = [{"title": "Parent Goal", "importance": 8}]
        context = {"wellbeing_priorities": "Health comes first"}
        
        # Set up mock response for prioritization
        self.mock_response.content[0].text = """
        1. Priority: 8, Critical task with upcoming deadline
        2. Priority: 5, Less urgent but still important
        """
        
        # Call the method
        prioritized = self.llm.prioritize_tasks(tasks, goals, context)
        
        # Verify priorities were assigned
        self.assertEqual(len(prioritized), 2)
        self.assertEqual(prioritized[0]['llm_priority'], 8)
        self.assertEqual(prioritized[1]['llm_priority'], 5)
    
    def test_identify_obstacles(self):
        """Test obstacle identification."""
        # Mock data
        goal = {"title": "Test Goal", "description": "Goal description"}
        tasks = [{"title": "Task 1", "completed": False}]
        context = {"time_constraints": "Busy week ahead"}
        
        # Set up mock response for obstacles
        self.mock_response.content[0].text = """
        Obstacle 1: Time constraints (High)
        - Allocate specific time blocks for work
        - Delegate less critical tasks
        
        Obstacle 2: Lack of resources (Medium)
        - Identify alternative resources
        - Adjust scope as needed
        """
        
        # Call the method
        obstacles = self.llm.identify_obstacles(goal, tasks, context)
        
        # Verify obstacles were identified
        self.assertTrue('obstacles' in obstacles)
        self.assertTrue('remedial_tasks' in obstacles)
        self.assertTrue(len(obstacles['obstacles']) > 0)
        self.assertTrue(len(obstacles['remedial_tasks']) > 0)
    
    def test_get_llm_factory_function(self):
        """Test the get_llm factory function."""
        with patch('src.llm_integration.LLMIntegration') as mock_llm:
            mock_llm.return_value = "llm_instance"
            result = get_llm()
            self.assertEqual(result, "llm_instance")
            mock_llm.assert_called_once()


if __name__ == '__main__':
    unittest.main()