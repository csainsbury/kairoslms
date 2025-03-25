"""
Notification utilities for kairoslms.

This module provides functionality for sending notifications to users through various channels:
- In-app notifications
- Email notifications
- Browser notifications (via web push)
"""
import os
import json
import logging
import smtplib
import threading
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from typing import Dict, Any, Optional, List, Union
from datetime import datetime

from fastapi import WebSocket
from pydantic import BaseModel, EmailStr

# Local imports
from src.utils.error_handling import ConfigurationError

# Configure module logger
logger = logging.getLogger(__name__)

# Define notification models
class Notification(BaseModel):
    """Base notification model."""
    id: Optional[str] = None
    type: str  # "info", "warning", "error", "success"
    title: str
    message: str
    timestamp: Optional[str] = None
    read: bool = False
    data: Optional[Dict[str, Any]] = None


class EmailNotification(BaseModel):
    """Email notification model."""
    to: Union[EmailStr, List[EmailStr]]
    subject: str
    body: str
    body_html: Optional[str] = None
    from_email: Optional[EmailStr] = None
    reply_to: Optional[EmailStr] = None
    cc: Optional[Union[EmailStr, List[EmailStr]]] = None
    bcc: Optional[Union[EmailStr, List[EmailStr]]] = None
    attachments: Optional[List[Dict[str, Any]]] = None


# Store of active WebSocket connections for real-time notifications
active_connections: Dict[str, WebSocket] = {}

# In-memory store of notifications (in a real app, would use a database)
user_notifications: Dict[str, List[Notification]] = {}


def add_notification(user_id: str, notification: Notification) -> Notification:
    """
    Add a notification for a user.
    
    Args:
        user_id: ID of the user to notify
        notification: The notification to add
        
    Returns:
        Notification: The added notification with ID and timestamp
    """
    # Ensure the user exists in our store
    if user_id not in user_notifications:
        user_notifications[user_id] = []
    
    # Add timestamp and ID if not provided
    if not notification.timestamp:
        notification.timestamp = datetime.utcnow().isoformat()
    
    if not notification.id:
        notification.id = f"notif_{len(user_notifications[user_id]) + 1}_{int(datetime.utcnow().timestamp())}"
    
    # Add to the user's notifications
    user_notifications[user_id].append(notification)
    
    # Log the notification
    logger.info(f"Added notification for user {user_id}: {notification.title}")
    
    # Try to send in real-time if the user is connected
    try:
        if user_id in active_connections:
            asyncio.create_task(send_realtime_notification(user_id, notification))
    except Exception as e:
        logger.error(f"Failed to send real-time notification: {str(e)}")
    
    return notification


def get_user_notifications(user_id: str, unread_only: bool = False) -> List[Notification]:
    """
    Get notifications for a user.
    
    Args:
        user_id: ID of the user
        unread_only: Whether to return only unread notifications
        
    Returns:
        List[Notification]: List of notifications
    """
    if user_id not in user_notifications:
        return []
    
    if unread_only:
        return [n for n in user_notifications[user_id] if not n.read]
    
    return user_notifications[user_id]


def mark_notification_read(user_id: str, notification_id: str) -> bool:
    """
    Mark a notification as read.
    
    Args:
        user_id: ID of the user
        notification_id: ID of the notification
        
    Returns:
        bool: True if the notification was marked as read, False otherwise
    """
    if user_id not in user_notifications:
        return False
    
    for notification in user_notifications[user_id]:
        if notification.id == notification_id:
            notification.read = True
            logger.debug(f"Marked notification {notification_id} as read for user {user_id}")
            return True
    
    return False


def clear_notifications(user_id: str) -> int:
    """
    Clear all notifications for a user.
    
    Args:
        user_id: ID of the user
        
    Returns:
        int: Number of notifications cleared
    """
    if user_id not in user_notifications:
        return 0
    
    count = len(user_notifications[user_id])
    user_notifications[user_id] = []
    
    logger.info(f"Cleared {count} notifications for user {user_id}")
    return count


async def send_realtime_notification(user_id: str, notification: Notification) -> bool:
    """
    Send a real-time notification to a user via WebSocket.
    
    Args:
        user_id: ID of the user
        notification: The notification to send
        
    Returns:
        bool: True if the notification was sent, False otherwise
    """
    if user_id not in active_connections:
        return False
    
    try:
        websocket = active_connections[user_id]
        await websocket.send_text(notification.json())
        logger.debug(f"Sent real-time notification to user {user_id}")
        return True
    except Exception as e:
        logger.error(f"Failed to send real-time notification: {str(e)}")
        return False


def notify_error(user_id: str, error_message: str, error_details: Optional[Dict[str, Any]] = None) -> Notification:
    """
    Create and send an error notification to a user.
    
    Args:
        user_id: ID of the user
        error_message: Error message
        error_details: Optional error details
        
    Returns:
        Notification: The created notification
    """
    notification = Notification(
        type="error",
        title="Error",
        message=error_message,
        data=error_details
    )
    
    return add_notification(user_id, notification)


def notify_critical_error(error_message: str, error_details: Optional[Dict[str, Any]] = None) -> None:
    """
    Send a critical error notification to all admin users and log it.
    
    Args:
        error_message: Error message
        error_details: Optional error details
    """
    # Log the critical error
    logger.critical(f"CRITICAL ERROR: {error_message}", extra={"details": error_details})
    
    # TODO: In a real application, we would query for admin users
    # For now, just use a default admin ID
    admin_id = os.getenv("ADMIN_USER_ID", "admin")
    
    # Create the notification
    notification = Notification(
        type="error",
        title="CRITICAL ERROR",
        message=error_message,
        data=error_details
    )
    
    # Add the notification for the admin
    add_notification(admin_id, notification)
    
    # Also send an email if configured
    try:
        if os.getenv("SMTP_HOST"):
            send_email_notification(
                EmailNotification(
                    to=os.getenv("ADMIN_EMAIL", "admin@example.com"),
                    subject=f"CRITICAL ERROR - KairosLMS",
                    body=f"Critical error occurred: {error_message}\n\nDetails: {json.dumps(error_details or {}, indent=2)}",
                )
            )
    except Exception as e:
        logger.error(f"Failed to send critical error email: {str(e)}")


def send_email_notification(email: EmailNotification) -> bool:
    """
    Send an email notification.
    
    Args:
        email: The email notification to send
        
    Returns:
        bool: True if the email was sent, False otherwise
    """
    # Get email configuration from environment
    smtp_host = os.getenv("SMTP_HOST")
    smtp_port = int(os.getenv("SMTP_PORT", "587"))
    smtp_user = os.getenv("SMTP_USER")
    smtp_password = os.getenv("SMTP_PASSWORD")
    default_from = os.getenv("DEFAULT_FROM_EMAIL", "noreply@kairoslms.example.com")
    
    # Check if email is configured
    if not all([smtp_host, smtp_user, smtp_password]):
        logger.warning("Email not configured, skipping email notification")
        return False
    
    try:
        # Create message
        msg = MIMEMultipart("alternative")
        msg["Subject"] = email.subject
        msg["From"] = email.from_email or default_from
        
        # Handle multiple recipients
        if isinstance(email.to, list):
            msg["To"] = ", ".join(email.to)
        else:
            msg["To"] = email.to
        
        # Add reply-to if provided
        if email.reply_to:
            msg["Reply-To"] = email.reply_to
        
        # Add CC if provided
        if email.cc:
            if isinstance(email.cc, list):
                msg["Cc"] = ", ".join(email.cc)
            else:
                msg["Cc"] = email.cc
        
        # Add text part
        msg.attach(MIMEText(email.body, "plain"))
        
        # Add HTML part if provided
        if email.body_html:
            msg.attach(MIMEText(email.body_html, "html"))
        
        # TODO: Handle attachments
        
        # Send the email in a separate thread to avoid blocking
        def send_mail():
            try:
                with smtplib.SMTP(smtp_host, smtp_port) as server:
                    server.ehlo()
                    server.starttls()
                    server.login(smtp_user, smtp_password)
                    
                    # Get all recipients
                    recipients = []
                    if isinstance(email.to, list):
                        recipients.extend(email.to)
                    else:
                        recipients.append(email.to)
                    
                    if email.cc:
                        if isinstance(email.cc, list):
                            recipients.extend(email.cc)
                        else:
                            recipients.append(email.cc)
                    
                    if email.bcc:
                        if isinstance(email.bcc, list):
                            recipients.extend(email.bcc)
                        else:
                            recipients.append(email.bcc)
                    
                    server.sendmail(
                        msg["From"],
                        recipients,
                        msg.as_string()
                    )
                    
                    logger.info(f"Email sent to {msg['To']}: {email.subject}")
                    return True
            except Exception as e:
                logger.error(f"Failed to send email: {str(e)}")
                return False
        
        # Start the thread
        thread = threading.Thread(target=send_mail)
        thread.start()
        
        return True
    except Exception as e:
        logger.error(f"Failed to create email: {str(e)}")
        return False


async def register_websocket(user_id: str, websocket: WebSocket) -> None:
    """
    Register a WebSocket connection for a user.
    
    Args:
        user_id: ID of the user
        websocket: The WebSocket connection
    """
    active_connections[user_id] = websocket
    logger.info(f"Registered WebSocket connection for user {user_id}")
    
    # Send any unread notifications
    unread = get_user_notifications(user_id, unread_only=True)
    if unread:
        await websocket.send_text(json.dumps({
            "type": "init",
            "notifications": [n.dict() for n in unread]
        }))


async def unregister_websocket(user_id: str) -> None:
    """
    Unregister a WebSocket connection for a user.
    
    Args:
        user_id: ID of the user
    """
    if user_id in active_connections:
        del active_connections[user_id]
        logger.info(f"Unregistered WebSocket connection for user {user_id}")


def is_email_configured() -> bool:
    """
    Check if email is configured.
    
    Returns:
        bool: True if email is configured, False otherwise
    """
    return all([
        os.getenv("SMTP_HOST"),
        os.getenv("SMTP_USER"),
        os.getenv("SMTP_PASSWORD")
    ])