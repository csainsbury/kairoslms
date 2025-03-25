#!/usr/bin/env python
"""
LLM Integration Module for KairosLMS

This module interfaces with the deepseek R1 API (using the Anthropic client) to provide
reasoning capabilities for goal achievement, status overviews, and task prioritization.
"""

import os
import logging
import time
from typing import Dict, List, Any, Optional, Union, Tuple
import json

import anthropic
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type

logger = logging.getLogger(__name__)

# Default system prompt template for reasoning tasks
DEFAULT_SYSTEM_PROMPT = """
You are an expert assistant helping to analyze and reason about life management tasks, goals, 
and projects. Your purpose is to help the user achieve their personal and professional goals.

You should:
1. Analyze the provided context thoughtfully
2. Identify connections between different goals and tasks
3. Provide clear, actionable insights
4. Be objective and focused on what would be most beneficial
5. Consider wellbeing impacts alongside productivity

Provide your reasoning and insights in a structured, clear format.
"""

class LLMIntegration:
    """Class to handle integration with deepseek R1 LLM via Anthropic's API."""
    
    def __init__(self, api_key: Optional[str] = None, model: str = "claude-3-opus-20240229"):
        """
        Initialize the LLM integration.
        
        Args:
            api_key: Anthropic API key. If None, uses the ANTHROPIC_API_KEY environment variable.
            model: Model name to use. Defaults to claude-3-opus, which is the most powerful model.
        """
        self.api_key = api_key or os.getenv("ANTHROPIC_API_KEY")
        if not self.api_key:
            raise ValueError("Anthropic API key is required either as a parameter or as ANTHROPIC_API_KEY environment variable")
        
        self.model = model
        self.client = anthropic.Anthropic(api_key=self.api_key)
        
        # Initialize interaction logs
        self.interaction_logs = []
    
    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=2, max=30),
        retry=retry_if_exception_type((anthropic.APIError, anthropic.APITimeoutError, anthropic.RateLimitError)),
        reraise=True
    )
    def query_llm(self, 
                 prompt: str, 
                 system_prompt: Optional[str] = None,
                 max_tokens: int = 4000,
                 temperature: float = 0.5,
                 timeout: int = 60) -> str:
        """
        Send a prompt to the LLM and get the response.
        
        Args:
            prompt: The user prompt to send to the LLM
            system_prompt: Optional custom system prompt. If None, uses the default.
            max_tokens: Maximum number of tokens to generate in the response
            temperature: Controls randomness in the response (0.0=deterministic, 1.0=creative)
            timeout: Request timeout in seconds
            
        Returns:
            str: The LLM's response text
        """
        start_time = time.time()
        log_entry = {
            "timestamp": start_time,
            "prompt": prompt,
            "system_prompt": system_prompt or DEFAULT_SYSTEM_PROMPT,
            "model": self.model,
            "max_tokens": max_tokens,
            "temperature": temperature,
        }
        
        try:
            # Send the request to the LLM
            response = self.client.messages.create(
                model=self.model,
                max_tokens=max_tokens,
                temperature=temperature,
                system=system_prompt or DEFAULT_SYSTEM_PROMPT,
                messages=[
                    {"role": "user", "content": prompt}
                ],
                timeout=timeout
            )
            
            # Extract the response text
            response_text = response.content[0].text
            
            # Log the successful interaction
            elapsed_time = time.time() - start_time
            log_entry.update({
                "success": True,
                "elapsed_time": elapsed_time,
                "response": response_text[:500] + "..." if len(response_text) > 500 else response_text,
                "tokens": {
                    "prompt_tokens": response.usage.input_tokens,
                    "completion_tokens": response.usage.output_tokens,
                    "total_tokens": response.usage.input_tokens + response.usage.output_tokens
                }
            })
            self.interaction_logs.append(log_entry)
            
            # Log a summary of the interaction
            logger.info(
                f"LLM query successful: model={self.model}, "
                f"prompt_tokens={response.usage.input_tokens}, "
                f"completion_tokens={response.usage.output_tokens}, "
                f"time={elapsed_time:.2f}s"
            )
            
            return response_text
        
        except Exception as e:
            # Log the error
            elapsed_time = time.time() - start_time
            log_entry.update({
                "success": False,
                "elapsed_time": elapsed_time,
                "error": str(e)
            })
            self.interaction_logs.append(log_entry)
            
            logger.error(f"LLM query failed: {str(e)}")
            raise
    
    def export_logs(self, file_path: Optional[str] = None) -> Union[str, bool]:
        """
        Export interaction logs to a JSON file or return as a string.
        
        Args:
            file_path: Path to export logs to. If None, returns as a string.
            
        Returns:
            Union[str, bool]: JSON string of logs or True if successfully written to file
        """
        log_json = json.dumps(self.interaction_logs, indent=2, default=str)
        
        if file_path:
            try:
                with open(file_path, "w") as f:
                    f.write(log_json)
                logger.info(f"Interaction logs exported to {file_path}")
                return True
            except Exception as e:
                logger.error(f"Failed to export logs to {file_path}: {str(e)}")
                return False
        else:
            return log_json
    
    def generate_goal_analysis(self, 
                              goal: Dict[str, Any], 
                              related_tasks: List[Dict[str, Any]], 
                              context: Dict[str, Any]) -> Dict[str, Any]:
        """
        Generate a comprehensive analysis of a goal using LLM reasoning.
        
        Args:
            goal: The goal data dictionary
            related_tasks: List of tasks related to this goal
            context: Additional context data (biography, calendar events, etc.)
            
        Returns:
            Dict[str, Any]: Analysis results
        """
        # Format the prompt with all the relevant context
        prompt = self._format_goal_analysis_prompt(goal, related_tasks, context)
        
        # Query the LLM
        response = self.query_llm(
            prompt=prompt,
            system_prompt=DEFAULT_SYSTEM_PROMPT,
            temperature=0.3  # Lower temperature for more factual analysis
        )
        
        # Parse and structure the response
        try:
            analysis = self._parse_goal_analysis_response(response)
            
            logger.info(f"Generated goal analysis for '{goal.get('title', 'Untitled goal')}'")
            return analysis
        except Exception as e:
            logger.error(f"Error parsing goal analysis response: {str(e)}")
            # Return a basic analysis with the raw response
            return {
                "summary": "Error parsing structured response",
                "raw_response": response,
                "error": str(e)
            }
    
    def prioritize_tasks(self, 
                        tasks: List[Dict[str, Any]], 
                        goals: List[Dict[str, Any]], 
                        context: Dict[str, Any]) -> List[Dict[str, Any]]:
        """
        Use LLM reasoning to prioritize tasks based on goals, deadlines, and wellbeing.
        
        Args:
            tasks: List of tasks to prioritize
            goals: List of relevant goals
            context: Additional context data
            
        Returns:
            List[Dict[str, Any]]: Prioritized tasks with reasoning
        """
        # Format the prompt for task prioritization
        prompt = self._format_task_prioritization_prompt(tasks, goals, context)
        
        # Query the LLM
        response = self.query_llm(
            prompt=prompt,
            temperature=0.2  # Even lower temperature for consistent prioritization
        )
        
        # Parse and structure the response
        try:
            prioritized_tasks = self._parse_task_prioritization_response(response, tasks)
            
            logger.info(f"Generated task prioritization for {len(tasks)} tasks")
            return prioritized_tasks
        except Exception as e:
            logger.error(f"Error parsing task prioritization response: {str(e)}")
            # Return the original tasks with an error flag
            for task in tasks:
                task["llm_priority_error"] = True
                task["llm_reasoning"] = f"Error: {str(e)}"
            return tasks
    
    def identify_obstacles(self, 
                          goal: Dict[str, Any], 
                          tasks: List[Dict[str, Any]], 
                          context: Dict[str, Any]) -> Dict[str, Any]:
        """
        Use LLM reasoning to identify obstacles and suggest remedial actions.
        
        Args:
            goal: The goal to analyze
            tasks: Tasks related to the goal
            context: Additional context data
            
        Returns:
            Dict[str, Any]: Identified obstacles and remedial task suggestions
        """
        # Format the prompt for obstacle identification
        prompt = self._format_obstacle_identification_prompt(goal, tasks, context)
        
        # Query the LLM
        response = self.query_llm(
            prompt=prompt,
            temperature=0.4  # Slightly higher temperature to encourage creative problem-solving
        )
        
        # Parse and structure the response
        try:
            obstacles_analysis = self._parse_obstacle_identification_response(response)
            
            logger.info(f"Identified obstacles for goal '{goal.get('title', 'Untitled goal')}'")
            return obstacles_analysis
        except Exception as e:
            logger.error(f"Error parsing obstacle identification response: {str(e)}")
            # Return a basic analysis with the raw response
            return {
                "obstacles": [],
                "remedial_tasks": [],
                "raw_response": response,
                "error": str(e)
            }
    
    def _format_goal_analysis_prompt(self, 
                                    goal: Dict[str, Any], 
                                    related_tasks: List[Dict[str, Any]], 
                                    context: Dict[str, Any]) -> str:
        """
        Format the prompt for goal analysis.
        
        Args:
            goal: The goal data dictionary
            related_tasks: List of tasks related to this goal
            context: Additional context data
            
        Returns:
            str: Formatted prompt
        """
        prompt = f"""
Please analyze the following goal and provide insights to help achieve it effectively.

## GOAL DETAILS
Title: {goal.get('title', 'Untitled')}
Description: {goal.get('description', 'No description provided')}
Type: {goal.get('goal_type', 'Unknown')}
Importance (0-10): {goal.get('importance', 'Not specified')}

## RELATED TASKS
"""
        
        if related_tasks:
            for i, task in enumerate(related_tasks, 1):
                status = "✓" if task.get('completed', False) else "☐"
                deadline = f"Due: {task.get('deadline', 'No deadline')}" if task.get('deadline') else "No deadline"
                prompt += f"{i}. {status} {task.get('title', 'Untitled task')} - {deadline}\n"
        else:
            prompt += "No related tasks found.\n"
        
        prompt += f"""
## RELEVANT CONTEXT
Biography excerpts: {context.get('biography', 'No biography provided')}
Recent calendar: {len(context.get('calendar_events', []))} upcoming events
Recent emails: {len(context.get('emails', []))} relevant emails

## REQUESTED ANALYSIS
1. Provide an assessment of the current state of this goal (250 words)
2. Break down the goal into 3-5 concrete next steps or subtasks
3. Identify any potential obstacles and how to overcome them
4. Suggest what success would look like for this goal
5. Assess how this goal connects to other aspects of life/work

Please structure your response clearly with headings and keep it concise and actionable.
"""
        return prompt
    
    def _parse_goal_analysis_response(self, response: str) -> Dict[str, Any]:
        """
        Parse the goal analysis response into a structured format.
        
        Args:
            response: The raw LLM response
            
        Returns:
            Dict[str, Any]: Structured analysis
        """
        # Basic parsing - in a production system this could be more sophisticated
        # to extract structured data from the response
        sections = response.split('\n\n')
        
        analysis = {
            "summary": sections[0] if sections else "",
            "next_steps": [],
            "obstacles": [],
            "success_criteria": "",
            "connections": "",
            "raw_response": response
        }
        
        # Extract basic next steps (tasks)
        for section in sections:
            if "next steps" in section.lower() or "subtasks" in section.lower():
                tasks = []
                for line in section.split('\n'):
                    if line.strip().startswith(('- ', '• ', '* ', '1. ', '2. ', '3. ', '4. ', '5. ')):
                        task = line.strip().lstrip('- •*123456789. ')
                        if task:
                            tasks.append(task)
                if tasks:
                    analysis["next_steps"] = tasks
        
        return analysis
    
    def _format_task_prioritization_prompt(self, 
                                          tasks: List[Dict[str, Any]], 
                                          goals: List[Dict[str, Any]], 
                                          context: Dict[str, Any]) -> str:
        """
        Format the prompt for task prioritization.
        
        Args:
            tasks: List of tasks to prioritize
            goals: List of relevant goals
            context: Additional context data
            
        Returns:
            str: Formatted prompt
        """
        prompt = """
Please prioritize the following tasks based on their importance, urgency, and impact on wellbeing.
Consider the goals they relate to, deadlines, and overall context.

## TASKS TO PRIORITIZE
"""
        
        for i, task in enumerate(tasks, 1):
            deadline = f"Due: {task.get('deadline')}" if task.get('deadline') else "No deadline"
            goal_id = task.get('goal_id', 'No goal')
            prompt += f"{i}. {task.get('title', 'Untitled task')} - {deadline} - Goal: {goal_id}\n"
        
        prompt += "\n## RELATED GOALS\n"
        for goal in goals:
            prompt += f"- {goal.get('title', 'Untitled')} (Importance: {goal.get('importance', 'N/A')}): {goal.get('description', 'No description')[:100]}...\n"
        
        prompt += f"""
## CONTEXT INFORMATION
Calendar: {len(context.get('calendar_events', []))} upcoming events in the next 7 days
Wellbeing priorities: {context.get('wellbeing_priorities', 'No specific wellbeing priorities mentioned')}

## INSTRUCTIONS
For each task, please:
1. Assign a priority score (1-10)
2. Provide brief reasoning (max 50 words per task)
3. Consider the following weights:
   - Parent goal importance: 40%
   - Deadline urgency: 30%
   - Wellbeing impact: 30%

Format your response as a numbered list that matches the input task order.
For each task include: Priority score (1-10), brief reasoning, and any suggested modifications.
"""
        return prompt
    
    def _parse_task_prioritization_response(self, 
                                          response: str, 
                                          original_tasks: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        Parse the task prioritization response and merge with original tasks.
        
        Args:
            response: The raw LLM response
            original_tasks: The original tasks to update with priorities
            
        Returns:
            List[Dict[str, Any]]: Updated tasks with LLM-derived priorities
        """
        tasks = original_tasks.copy()
        
        # Split the response into lines
        lines = response.strip().split('\n')
        
        # Track the current task index
        current_task_idx = 0
        current_priority = None
        current_reasoning = []
        
        # Process each line
        for line in lines:
            line = line.strip()
            
            # Look for numbered lines that might start a new task
            if line and line[0].isdigit() and '. ' in line[:5]:
                # If we were processing a previous task, save its data
                if current_priority is not None and current_task_idx < len(tasks):
                    tasks[current_task_idx]["llm_priority"] = current_priority
                    tasks[current_task_idx]["llm_reasoning"] = " ".join(current_reasoning)
                
                # Move to the next task
                current_task_idx = int(line.split('.')[0]) - 1
                if current_task_idx < len(tasks):
                    # Reset for the new task
                    current_reasoning = []
                    
                    # Try to extract the priority score
                    try:
                        # Look for patterns like "Priority: 8" or "Score: 8/10"
                        if "priority:" in line.lower():
                            priority_part = line.lower().split("priority:")[1]
                            current_priority = int(priority_part.strip().split()[0])
                        elif "score:" in line.lower():
                            priority_part = line.lower().split("score:")[1]
                            current_priority = int(priority_part.strip().split()[0].split('/')[0])
                        else:
                            # Look for any number that could be a score
                            import re
                            numbers = re.findall(r'\b(\d{1,2})(?:/10)?\b', line)
                            if numbers:
                                current_priority = int(numbers[0])
                            else:
                                current_priority = None
                    except (ValueError, IndexError):
                        current_priority = None
                    
                    # Add the rest of the line as reasoning
                    reasoning_part = line.split(':', 1)[1] if ':' in line else line
                    current_reasoning.append(reasoning_part.strip())
            
            # If not a new task, add to current reasoning
            elif current_task_idx < len(tasks):
                current_reasoning.append(line)
        
        # Don't forget the last task
        if current_priority is not None and current_task_idx < len(tasks):
            tasks[current_task_idx]["llm_priority"] = current_priority
            tasks[current_task_idx]["llm_reasoning"] = " ".join(current_reasoning)
        
        # Set priorities for any tasks that didn't get processed
        for task in tasks:
            if "llm_priority" not in task:
                task["llm_priority"] = task.get("priority", 5)  # Use existing priority or default
                task["llm_reasoning"] = "No specific reasoning provided by LLM"
        
        return tasks
    
    def _format_obstacle_identification_prompt(self, 
                                             goal: Dict[str, Any], 
                                             tasks: List[Dict[str, Any]], 
                                             context: Dict[str, Any]) -> str:
        """
        Format the prompt for obstacle identification.
        
        Args:
            goal: The goal to analyze
            tasks: Tasks related to the goal
            context: Additional context data
            
        Returns:
            str: Formatted prompt
        """
        prompt = f"""
Please analyze the following goal and identify potential obstacles that might prevent its successful completion.
Also suggest specific remedial tasks to overcome each obstacle.

## GOAL DETAILS
Title: {goal.get('title', 'Untitled')}
Description: {goal.get('description', 'No description provided')}
Type: {goal.get('goal_type', 'Unknown')}
Importance (0-10): {goal.get('importance', 'Not specified')}

## CURRENT PROGRESS
"""
        
        if tasks:
            completed = sum(1 for task in tasks if task.get('completed', False))
            total = len(tasks)
            completion_rate = (completed / total) * 100 if total > 0 else 0
            
            prompt += f"Progress: {completed}/{total} tasks completed ({completion_rate:.1f}%)\n\n"
            prompt += "Tasks:\n"
            
            for i, task in enumerate(tasks, 1):
                status = "✓" if task.get('completed', False) else "☐"
                deadline = f"Due: {task.get('deadline', 'No deadline')}" if task.get('deadline') else "No deadline"
                prompt += f"{i}. {status} {task.get('title', 'Untitled task')} - {deadline}\n"
        else:
            prompt += "No tasks created yet for this goal.\n"
        
        prompt += f"""
## RELEVANT CONTEXT
Time constraints: {context.get('time_constraints', 'No specific time constraints mentioned')}
Resources available: {context.get('resources', 'No specific resources mentioned')}
Past obstacles: {context.get('past_obstacles', 'No past obstacles recorded')}

## REQUESTED ANALYSIS
1. Identify 3-5 potential obstacles that might prevent achieving this goal
2. For each obstacle, suggest 1-2 specific remedial tasks that could help overcome it
3. Categorize each obstacle by severity (High, Medium, Low)

Please format your response with clear headings for each obstacle and bullet points for remedial tasks.
"""
        return prompt
    
    def _parse_obstacle_identification_response(self, response: str) -> Dict[str, Any]:
        """
        Parse the obstacle identification response into a structured format.
        
        Args:
            response: The raw LLM response
            
        Returns:
            Dict[str, Any]: Structured obstacles and remedial tasks
        """
        # Basic parsing - could be more sophisticated in production
        obstacles = []
        remedial_tasks = []
        
        # Split the response into sections based on obstacles
        sections = response.split('\n\n')
        
        for section in sections:
            # Look for sections that might describe obstacles
            if "obstacle" in section.lower() or "barrier" in section.lower() or "challenge" in section.lower():
                obstacle_lines = section.split('\n')
                
                # First line is likely the obstacle title/description
                obstacle_title = obstacle_lines[0].strip()
                if ":" in obstacle_title:
                    obstacle_title = obstacle_title.split(":", 1)[1].strip()
                
                # Extract severity if present
                severity = "Medium"  # Default
                if "high" in section.lower():
                    severity = "High"
                elif "medium" in section.lower():
                    severity = "Medium"
                elif "low" in section.lower():
                    severity = "Low"
                
                # Add the obstacle
                obstacle = {
                    "title": obstacle_title,
                    "severity": severity
                }
                obstacles.append(obstacle)
                
                # Look for remedial tasks in the section
                for line in obstacle_lines[1:]:
                    line = line.strip()
                    if line.startswith(('- ', '• ', '* ')):
                        task_desc = line.lstrip('- •* ')
                        if task_desc:
                            task = {
                                "title": f"Remedial: {task_desc}",
                                "for_obstacle": obstacle_title,
                                "priority": 7 if severity == "High" else 5 if severity == "Medium" else 3
                            }
                            remedial_tasks.append(task)
        
        result = {
            "obstacles": obstacles,
            "remedial_tasks": remedial_tasks,
            "raw_response": response
        }
        
        return result


def get_llm() -> LLMIntegration:
    """
    Get an instance of the LLM integration.
    
    Returns:
        LLMIntegration: An initialized LLM integration instance
    """
    api_key = os.getenv("ANTHROPIC_API_KEY")
    model = os.getenv("ANTHROPIC_MODEL", "claude-3-opus-20240229")
    
    try:
        return LLMIntegration(api_key=api_key, model=model)
    except Exception as e:
        logger.error(f"Failed to initialize LLM integration: {str(e)}")
        raise


if __name__ == "__main__":
    # Configure logging
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    )
    
    # Test the LLM integration
    try:
        llm = get_llm()
        
        # Simple test prompt
        response = llm.query_llm(
            prompt="How can setting specific, measurable, achievable, relevant, and time-bound (SMART) goals improve goal achievement? Give a concise explanation."
        )
        
        print("LLM Response:")
        print(response)
        
        print("\nExporting logs...")
        logs = llm.export_logs()
        print(logs)
        
    except Exception as e:
        logger.error(f"Error testing LLM integration: {str(e)}")