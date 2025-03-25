"""
Email ingestion module for kairoslms.

This module connects to a Gmail account using the Gmail API to fetch
email headers and text content in daily batches.
"""
import os
import base64
import logging
import email
from datetime import datetime, timedelta
from typing import List, Dict, Any, Optional, Tuple
from email.utils import parsedate_to_datetime

import google.auth
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google.oauth2 import service_account
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

from src.db import store_email, Email

# Configure logging
logger = logging.getLogger(__name__)

# Gmail API scopes
SCOPES = ['https://www.googleapis.com/auth/gmail.readonly']

class GmailClient:
    """Client for interacting with Gmail API."""
    
    def __init__(self, credentials_file: Optional[str] = None, token_file: Optional[str] = None, 
                 service_account_file: Optional[str] = None, delegated_email: Optional[str] = None):
        """
        Initialize the Gmail client.
        
        Args:
            credentials_file: Path to the client secrets file (for OAuth)
            token_file: Path to the token file (for OAuth)
            service_account_file: Path to service account credentials (for service account auth)
            delegated_email: Email to impersonate with service account
        """
        self.credentials_file = credentials_file or os.getenv("GMAIL_CREDENTIALS_FILE")
        self.token_file = token_file or os.getenv("GMAIL_TOKEN_FILE")
        self.service_account_file = service_account_file or os.getenv("GMAIL_SERVICE_ACCOUNT_FILE")
        self.delegated_email = delegated_email or os.getenv("GMAIL_DELEGATED_EMAIL")
        self.service = None
        self.auth_method = os.getenv("GMAIL_AUTH_METHOD", "oauth")  # 'oauth' or 'service_account'
    
    def authenticate(self) -> None:
        """Authenticate to Gmail API using either OAuth or Service Account."""
        # Check if we should use service account authentication
        if self.auth_method == "service_account" and self.service_account_file and os.path.exists(self.service_account_file):
            self._authenticate_service_account()
        else:
            self._authenticate_oauth()
    
    def _authenticate_service_account(self) -> None:
        """Authenticate using a service account."""
        try:
            # Create credentials from service account file
            creds = service_account.Credentials.from_service_account_file(
                self.service_account_file, scopes=SCOPES
            )
            
            # If delegated email is provided, create delegated credentials
            if self.delegated_email:
                creds = creds.with_subject(self.delegated_email)
            
            # Create Gmail API service
            self.service = build('gmail', 'v1', credentials=creds)
            logger.info("Gmail API authentication with service account successful")
        except Exception as e:
            logger.error(f"Error authenticating with service account: {str(e)}")
            raise
    
    def _authenticate_oauth(self) -> None:
        """Authenticate using OAuth 2.0."""
        creds = None
        
        # Check if token file exists
        if os.path.exists(self.token_file):
            try:
                with open(self.token_file, 'r') as token:
                    creds = Credentials.from_authorized_user_info(
                        info=eval(token.read()), scopes=SCOPES
                    )
            except Exception as e:
                logger.error(f"Error loading token file: {str(e)}")
        
        # If there are no valid credentials, let the user log in
        if not creds or not creds.valid:
            if creds and creds.expired and creds.refresh_token:
                try:
                    creds.refresh(Request())
                except Exception as e:
                    logger.error(f"Error refreshing token: {str(e)}")
                    creds = None
            
            if not creds:
                if not os.path.exists(self.credentials_file):
                    raise FileNotFoundError(f"Credentials file not found: {self.credentials_file}")
                
                try:
                    flow = InstalledAppFlow.from_client_secrets_file(
                        self.credentials_file, SCOPES
                    )
                    creds = flow.run_local_server(port=0)
                except Exception as e:
                    logger.error(f"Error in OAuth flow: {str(e)}")
                    raise
            
            # Save the credentials for the next run
            try:
                with open(self.token_file, 'w') as token:
                    token.write(str(creds.to_json()))
            except Exception as e:
                logger.error(f"Error saving token file: {str(e)}")
        
        # Create Gmail API service
        self.service = build('gmail', 'v1', credentials=creds)
        logger.info("Gmail API authentication with OAuth successful")
    
    def fetch_emails(self, days: int = 1, max_results: int = 100) -> List[Dict[str, Any]]:
        """
        Fetch emails from the last specified number of days.
        
        Args:
            days: Number of days to look back
            max_results: Maximum number of emails to retrieve
            
        Returns:
            List of email dictionaries
        """
        if not self.service:
            logger.error("Gmail service not initialized. Call authenticate() first.")
            return []
        
        try:
            # Calculate the date range
            after_date = (datetime.now() - timedelta(days=days)).strftime('%Y/%m/%d')
            
            # Fetch messages matching the criteria
            query = f"after:{after_date}"
            results = self.service.users().messages().list(
                userId='me', q=query, maxResults=max_results
            ).execute()
            
            messages = results.get('messages', [])
            if not messages:
                logger.info(f"No emails found for the last {days} days")
                return []
            
            logger.info(f"Found {len(messages)} emails")
            
            # Fetch full message details for each message
            emails = []
            for message in messages:
                msg_id = message['id']
                msg = self.service.users().messages().get(userId='me', id=msg_id).execute()
                email_data = self._parse_message(msg)
                emails.append(email_data)
            
            return emails
            
        except HttpError as error:
            logger.error(f"Error fetching emails: {error}")
            return []
    
    def _parse_message(self, message: Dict[str, Any]) -> Dict[str, Any]:
        """
        Parse a Gmail message into a structured format.
        
        Args:
            message: The Gmail API message object
            
        Returns:
            Dictionary with parsed email data
        """
        headers = message['payload']['headers']
        
        # Extract headers
        subject = next((h['value'] for h in headers if h['name'].lower() == 'subject'), "No Subject")
        from_header = next((h['value'] for h in headers if h['name'].lower() == 'from'), "")
        to_header = next((h['value'] for h in headers if h['name'].lower() == 'to'), "")
        date_header = next((h['value'] for h in headers if h['name'].lower() == 'date'), "")
        
        # Parse date
        try:
            received_at = parsedate_to_datetime(date_header)
        except:
            received_at = datetime.now()
        
        # Extract text content
        body = ""
        if 'parts' in message['payload']:
            for part in message['payload']['parts']:
                if part['mimeType'] == 'text/plain':
                    if 'data' in part['body']:
                        body_data = part['body']['data']
                        try:
                            body = base64.urlsafe_b64decode(body_data).decode('utf-8')
                            break
                        except Exception as e:
                            logger.error(f"Error decoding email body: {e}")
        elif 'body' in message['payload'] and 'data' in message['payload']['body']:
            body_data = message['payload']['body']['data']
            try:
                body = base64.urlsafe_b64decode(body_data).decode('utf-8')
            except Exception as e:
                logger.error(f"Error decoding email body: {e}")
        
        return {
            'message_id': message['id'],
            'subject': subject,
            'sender': from_header,
            'recipients': to_header,
            'received_at': received_at,
            'content': body
        }


def ingest_emails(days: int = 1) -> Tuple[int, int]:
    """
    Ingest emails from Gmail and store them in the database.
    
    Args:
        days: Number of days to look back
        
    Returns:
        Tuple of (total emails found, emails stored)
    """
    # Create Gmail client
    gmail_client = GmailClient()
    
    try:
        # Authenticate to Gmail API
        gmail_client.authenticate()
        
        # Fetch emails
        emails = gmail_client.fetch_emails(days=days)
        
        # Store emails in the database
        stored_count = 0
        for email_data in emails:
            try:
                store_email(
                    subject=email_data['subject'],
                    sender=email_data['sender'],
                    recipients=email_data['recipients'],
                    received_at=email_data['received_at'],
                    content=email_data['content'],
                    message_id=email_data['message_id']
                )
                stored_count += 1
            except Exception as e:
                logger.error(f"Error storing email {email_data['message_id']}: {str(e)}")
                continue
        
        logger.info(f"Stored {stored_count} out of {len(emails)} emails")
        return len(emails), stored_count
        
    except Exception as e:
        logger.error(f"Error in email ingestion process: {str(e)}")
        return 0, 0


if __name__ == "__main__":
    # Configure logging for standalone use
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    )
    
    # Ingest emails from the last day
    total, stored = ingest_emails(days=1)
    print(f"Email ingestion complete. Found {total} emails, stored {stored}.")