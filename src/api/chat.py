"""
Chat interface API for kairoslms.
"""
from typing import List, Dict, Any, Optional
from fastapi import APIRouter, HTTPException, Body, Depends
from pydantic import BaseModel
import os
from datetime import datetime

from src.db import get_db, execute_query
from src.llm_integration import LLMIntegration

router = APIRouter(prefix="/chat", tags=["chat"])

class ChatMessage(BaseModel):
    """Model for chat messages."""
    id: Optional[int] = None
    sender: str  # "user" or "system"
    content: str
    timestamp: Optional[str] = None
    
class ChatSession(BaseModel):
    """Model for chat sessions."""
    id: int
    title: str
    created_at: str
    updated_at: str
    
class ChatRequest(BaseModel):
    """Model for chat requests."""
    message: str
    session_id: Optional[int] = None

@router.get("/sessions", response_model=List[ChatSession])
async def get_chat_sessions():
    """Get all chat sessions."""
    try:
        conn = get_db()
        query = "SELECT * FROM chat_sessions ORDER BY updated_at DESC"
        sessions = execute_query(conn, query)
        return sessions
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error fetching chat sessions: {str(e)}")

@router.post("/sessions", response_model=ChatSession)
async def create_chat_session(title: str = Body(..., embed=True)):
    """Create a new chat session."""
    try:
        conn = get_db()
        now = datetime.utcnow().isoformat()
        query = """
        INSERT INTO chat_sessions (title, created_at, updated_at) 
        VALUES (?, ?, ?) 
        RETURNING *
        """
        sessions = execute_query(conn, query, (title, now, now))
        return sessions[0]
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error creating chat session: {str(e)}")

@router.get("/sessions/{session_id}/messages", response_model=List[ChatMessage])
async def get_chat_messages(session_id: int):
    """Get all messages for a specific chat session."""
    try:
        conn = get_db()
        query = """
        SELECT * FROM chat_messages 
        WHERE session_id = ? 
        ORDER BY timestamp ASC
        """
        messages = execute_query(conn, query, (session_id,))
        return messages
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error fetching chat messages: {str(e)}")

@router.post("/messages", response_model=List[ChatMessage])
async def send_message(chat_request: ChatRequest):
    """Send a message and get a response from the LLM."""
    try:
        # Check if LLM integration is available
        if not os.getenv("ANTHROPIC_API_KEY"):
            raise HTTPException(
                status_code=503, 
                detail="LLM integration is not available. Please set ANTHROPIC_API_KEY environment variable."
            )
        
        conn = get_db()
        
        # Create a new session if none is provided
        session_id = chat_request.session_id
        if not session_id:
            now = datetime.utcnow().isoformat()
            query = """
            INSERT INTO chat_sessions (title, created_at, updated_at) 
            VALUES (?, ?, ?) 
            RETURNING id
            """
            title = f"Chat {now}"
            sessions = execute_query(conn, query, (title, now, now))
            session_id = sessions[0]["id"]
        
        # Save user message
        now = datetime.utcnow().isoformat()
        query = """
        INSERT INTO chat_messages (session_id, sender, content, timestamp) 
        VALUES (?, ?, ?, ?) 
        RETURNING *
        """
        user_message = execute_query(
            conn, query, (session_id, "user", chat_request.message, now)
        )[0]
        
        # Process with LLM
        llm = LLMIntegration()
        context = generate_chat_context(session_id)
        
        response_content = llm.query_llm(
            prompt=f"User message: {chat_request.message}\n\nContext: {context}\n\nPlease provide a helpful, concise response.",
            max_tokens=1000,
        )
        
        # Save system response
        now = datetime.utcnow().isoformat()
        system_message = execute_query(
            conn, query, (session_id, "system", response_content, now)
        )[0]
        
        # Update session updated_at timestamp
        query = "UPDATE chat_sessions SET updated_at = ? WHERE id = ?"
        execute_query(conn, query, (now, session_id))
        
        return [user_message, system_message]
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error processing chat message: {str(e)}")

def generate_chat_context(session_id: int) -> str:
    """Generate context for the chat based on session history."""
    try:
        conn = get_db()
        
        # Get recent messages in the session
        query = """
        SELECT * FROM chat_messages 
        WHERE session_id = ? 
        ORDER BY timestamp DESC 
        LIMIT 10
        """
        messages = execute_query(conn, query, (session_id,))
        
        # Get current goals and tasks
        goals_query = "SELECT * FROM goals ORDER BY priority DESC LIMIT 5"
        goals = execute_query(conn, goals_query)
        
        tasks_query = "SELECT * FROM tasks ORDER BY priority DESC LIMIT 10"
        tasks = execute_query(conn, tasks_query)
        
        # Format as context
        context = "Current Goals:\n"
        for goal in goals:
            context += f"- {goal['name']} (Priority: {goal['priority']}): {goal['description']}\n"
        
        context += "\nPrioritized Tasks:\n"
        for task in tasks:
            context += f"- {task['name']} (Priority: {task['priority']})"
            if task.get('deadline'):
                context += f" Due: {task['deadline']}"
            context += "\n"
        
        context += "\nRecent Conversation:\n"
        for message in reversed(messages):
            sender = "User" if message['sender'] == "user" else "System"
            context += f"{sender}: {message['content']}\n"
        
        return context
    except Exception as e:
        print(f"Error generating chat context: {str(e)}")
        return "No context available."