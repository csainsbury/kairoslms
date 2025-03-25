"""
Calendar ingestion module for kairoslms.

This module connects to Google Calendar API to fetch calendar events
and store them in the database.
"""
import os
import logging
from datetime import datetime, timedelta
from typing import List, Dict, Any, Optional, Tuple

import google.auth
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

from src.db import store_calendar_event, CalendarEvent

# Configure logging
logger = logging.getLogger(__name__)

# Google Calendar API scopes
SCOPES = ['https://www.googleapis.com/auth/calendar.readonly']

class CalendarClient:
    """Client for interacting with Google Calendar API."""
    
    def __init__(self, credentials_file: Optional[str] = None, token_file: Optional[str] = None):
        """
        Initialize the Google Calendar client.
        
        Args:
            credentials_file: Path to the client secrets file
            token_file: Path to the token file
        """
        self.credentials_file = credentials_file or os.getenv("CALENDAR_CREDENTIALS_FILE")
        self.token_file = token_file or os.getenv("CALENDAR_TOKEN_FILE")
        self.service = None
    
    def authenticate(self) -> None:
        """Authenticate to Google Calendar API."""
        creds = None
        
        # Check if token file exists
        if os.path.exists(self.token_file):
            creds = Credentials.from_authorized_user_info(
                info=eval(open(self.token_file, 'r').read()), scopes=SCOPES
            )
        
        # If there are no valid credentials, let the user log in
        if not creds or not creds.valid:
            if creds and creds.expired and creds.refresh_token:
                creds.refresh(Request())
            else:
                flow = InstalledAppFlow.from_client_secrets_file(
                    self.credentials_file, SCOPES
                )
                creds = flow.run_local_server(port=0)
            
            # Save the credentials for the next run
            with open(self.token_file, 'w') as token:
                token.write(str(creds.to_json()))
        
        # Create Google Calendar API service
        self.service = build('calendar', 'v3', credentials=creds)
        logger.info("Google Calendar API authentication successful")
    
    def fetch_events(self, days_past: int = 0, days_future: int = 30, max_results: int = 100) -> List[Dict[str, Any]]:
        """
        Fetch calendar events within a time range.
        
        Args:
            days_past: Number of days to look back
            days_future: Number of days to look ahead
            max_results: Maximum number of events to retrieve
            
        Returns:
            List of event dictionaries
        """
        if not self.service:
            logger.error("Calendar service not initialized. Call authenticate() first.")
            return []
        
        try:
            # Calculate the time range
            now = datetime.utcnow()
            time_min = (now - timedelta(days=days_past)).isoformat() + 'Z'  # 'Z' indicates UTC time
            time_max = (now + timedelta(days=days_future)).isoformat() + 'Z'
            
            # Fetch events within the time range
            events_result = self.service.events().list(
                calendarId='primary',
                timeMin=time_min,
                timeMax=time_max,
                maxResults=max_results,
                singleEvents=True,
                orderBy='startTime'
            ).execute()
            
            events = events_result.get('items', [])
            if not events:
                logger.info("No upcoming events found")
                return []
            
            logger.info(f"Found {len(events)} calendar events")
            
            # Parse events into a consistent format
            parsed_events = []
            for event in events:
                event_data = self._parse_event(event)
                if event_data:
                    parsed_events.append(event_data)
            
            return parsed_events
            
        except HttpError as error:
            logger.error(f"Error fetching calendar events: {error}")
            return []
    
    def _parse_event(self, event: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """
        Parse a Google Calendar event into a structured format.
        
        Args:
            event: The Google Calendar API event object
            
        Returns:
            Dictionary with parsed event data, or None if parsing fails
        """
        try:
            # Get event ID
            event_id = event.get('id', '')
            
            # Get event title
            title = event.get('summary', 'Untitled Event')
            
            # Get event location
            location = event.get('location', '')
            
            # Get event description
            description = event.get('description', '')
            
            # Parse start and end times
            start_time = None
            end_time = None
            
            if 'dateTime' in event.get('start', {}):
                # Event has a specific start time
                start_str = event['start']['dateTime']
                start_time = datetime.fromisoformat(start_str.replace('Z', '+00:00'))
            elif 'date' in event.get('start', {}):
                # All-day event, use midnight as start time
                date_str = event['start']['date']
                start_time = datetime.fromisoformat(f"{date_str}T00:00:00")
            
            if 'dateTime' in event.get('end', {}):
                # Event has a specific end time
                end_str = event['end']['dateTime']
                end_time = datetime.fromisoformat(end_str.replace('Z', '+00:00'))
            elif 'date' in event.get('end', {}):
                # All-day event, use midnight as end time
                date_str = event['end']['date']
                end_time = datetime.fromisoformat(f"{date_str}T23:59:59")
            
            if not start_time or not end_time:
                logger.warning(f"Event {title} has invalid start or end time")
                return None
            
            # Get attendees
            attendees = []
            for attendee in event.get('attendees', []):
                attendee_email = attendee.get('email', '')
                if attendee_email:
                    attendees.append(attendee_email)
            
            attendees_str = ', '.join(attendees)
            
            return {
                'title': title,
                'start_time': start_time,
                'end_time': end_time,
                'location': location,
                'description': description,
                'attendees': attendees_str,
                'event_id': event_id
            }
            
        except Exception as e:
            logger.error(f"Error parsing event {event.get('summary', 'Unknown')}: {str(e)}")
            return None


def ingest_calendar_events(days_past: int = 0, days_future: int = 30) -> Tuple[int, int]:
    """
    Ingest calendar events from Google Calendar and store them in the database.
    
    Args:
        days_past: Number of days to look back
        days_future: Number of days to look ahead
        
    Returns:
        Tuple of (total events found, events stored)
    """
    # Create Calendar client
    calendar_client = CalendarClient()
    
    try:
        # Authenticate to Google Calendar API
        calendar_client.authenticate()
        
        # Fetch calendar events
        events = calendar_client.fetch_events(days_past=days_past, days_future=days_future)
        
        # Store events in the database
        stored_count = 0
        for event_data in events:
            try:
                store_calendar_event(
                    title=event_data['title'],
                    start_time=event_data['start_time'],
                    end_time=event_data['end_time'],
                    location=event_data['location'],
                    description=event_data['description'],
                    attendees=event_data['attendees'],
                    event_id=event_data['event_id']
                )
                stored_count += 1
            except Exception as e:
                logger.error(f"Error storing event {event_data['title']}: {str(e)}")
                continue
        
        logger.info(f"Stored {stored_count} out of {len(events)} calendar events")
        return len(events), stored_count
        
    except Exception as e:
        logger.error(f"Error in calendar ingestion process: {str(e)}")
        return 0, 0


if __name__ == "__main__":
    # Configure logging for standalone use
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    )
    
    # Ingest calendar events for the next 30 days
    total, stored = ingest_calendar_events(days_past=0, days_future=30)
    print(f"Calendar ingestion complete. Found {total} events, stored {stored}.")