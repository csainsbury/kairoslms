"""
Unit tests for calendar ingestion module.
"""
import os
import pytest
from unittest.mock import patch, MagicMock
from datetime import datetime, timedelta

from src.ingestion.calendar_ingestion import CalendarClient, ingest_calendar_events


@pytest.fixture
def mock_calendar_service():
    """Fixture for mocking Calendar service."""
    mock_service = MagicMock()
    
    # Mock events list method
    mock_list = MagicMock()
    mock_list.execute.return_value = {
        'items': [
            {
                'id': 'event1',
                'summary': 'Test Event 1',
                'location': 'Test Location',
                'description': 'Test Description',
                'start': {
                    'dateTime': '2023-01-01T10:00:00Z',
                },
                'end': {
                    'dateTime': '2023-01-01T11:00:00Z',
                },
                'attendees': [
                    {'email': 'person1@example.com'},
                    {'email': 'person2@example.com'}
                ]
            },
            {
                'id': 'event2',
                'summary': 'Test Event 2',
                'start': {
                    'date': '2023-01-02',
                },
                'end': {
                    'date': '2023-01-03',
                }
            },
            {
                'id': 'event3',
                'summary': 'Test Event 3',
                'start': {
                    'dateTime': '2023-01-03T15:00:00Z',
                },
                'end': {
                    'dateTime': '2023-01-03T16:00:00Z',
                }
            }
        ]
    }
    
    mock_service.events().list.return_value = mock_list
    
    return mock_service


@pytest.fixture
def calendar_client():
    """Fixture for creating a CalendarClient instance with mocked credentials."""
    with patch('os.path.exists', return_value=True), \
         patch('builtins.open', MagicMock()), \
         patch('google.oauth2.credentials.Credentials.from_authorized_user_info', MagicMock()):
        client = CalendarClient(
            credentials_file="dummy_credentials.json",
            token_file="dummy_token.json"
        )
        yield client


class TestCalendarClient:
    """Tests for the CalendarClient class."""
    
    def test_init(self):
        """Test initialization of CalendarClient."""
        with patch.dict(os.environ, {"CALENDAR_CREDENTIALS_FILE": "env_credentials.json", 
                                    "CALENDAR_TOKEN_FILE": "env_token.json"}):
            client = CalendarClient()
            assert client.credentials_file == "env_credentials.json"
            assert client.token_file == "env_token.json"
            assert client.service is None
        
        client = CalendarClient(credentials_file="custom_credentials.json", token_file="custom_token.json")
        assert client.credentials_file == "custom_credentials.json"
        assert client.token_file == "custom_token.json"
    
    def test_authenticate(self, calendar_client):
        """Test authentication process."""
        with patch('google.oauth2.credentials.Credentials.valid', True), \
             patch('googleapiclient.discovery.build', return_value="mock_service"):
            calendar_client.authenticate()
            assert calendar_client.service == "mock_service"
    
    def test_authenticate_refresh_token(self, calendar_client):
        """Test authentication with token refresh."""
        mock_creds = MagicMock()
        mock_creds.valid = False
        mock_creds.expired = True
        mock_creds.refresh_token = True
        
        with patch('google.oauth2.credentials.Credentials.from_authorized_user_info', return_value=mock_creds), \
             patch('googleapiclient.discovery.build', return_value="mock_service"):
            calendar_client.authenticate()
            mock_creds.refresh.assert_called_once()
            assert calendar_client.service == "mock_service"
    
    def test_fetch_events_no_service(self, calendar_client):
        """Test fetching events without an initialized service."""
        events = calendar_client.fetch_events()
        assert events == []
    
    def test_fetch_events_success(self, calendar_client, mock_calendar_service):
        """Test successful events fetching."""
        calendar_client.service = mock_calendar_service
        events = calendar_client.fetch_events(days_past=1, days_future=30)
        
        assert len(events) == 3
        
        # Check first event
        assert events[0]["event_id"] == "event1"
        assert events[0]["title"] == "Test Event 1"
        assert events[0]["location"] == "Test Location"
        assert events[0]["description"] == "Test Description"
        assert isinstance(events[0]["start_time"], datetime)
        assert isinstance(events[0]["end_time"], datetime)
        assert "person1@example.com" in events[0]["attendees"]
        assert "person2@example.com" in events[0]["attendees"]
        
        # Check all-day event
        assert events[1]["event_id"] == "event2"
        assert events[1]["title"] == "Test Event 2"
        assert isinstance(events[1]["start_time"], datetime)
        assert isinstance(events[1]["end_time"], datetime)
    
    def test_fetch_events_http_error(self, calendar_client):
        """Test handling of HTTP errors."""
        calendar_client.service = MagicMock()
        calendar_client.service.events().list.side_effect = Exception("HTTP Error")
        
        events = calendar_client.fetch_events()
        assert events == []
    
    def test_fetch_events_no_events(self, calendar_client):
        """Test when no events are found."""
        mock_service = MagicMock()
        mock_list = MagicMock()
        mock_list.execute.return_value = {'items': []}
        mock_service.events().list.return_value = mock_list
        
        calendar_client.service = mock_service
        events = calendar_client.fetch_events()
        assert events == []
    
    def test_parse_event_success(self, calendar_client):
        """Test successful event parsing."""
        event = {
            'id': 'test_id',
            'summary': 'Test Event',
            'location': 'Test Location',
            'description': 'Test Description',
            'start': {
                'dateTime': '2023-01-01T10:00:00Z',
            },
            'end': {
                'dateTime': '2023-01-01T11:00:00Z',
            },
            'attendees': [
                {'email': 'person1@example.com'},
                {'email': 'person2@example.com'}
            ]
        }
        
        result = calendar_client._parse_event(event)
        
        assert result['event_id'] == 'test_id'
        assert result['title'] == 'Test Event'
        assert result['location'] == 'Test Location'
        assert result['description'] == 'Test Description'
        assert isinstance(result['start_time'], datetime)
        assert isinstance(result['end_time'], datetime)
        assert 'person1@example.com' in result['attendees']
        assert 'person2@example.com' in result['attendees']
    
    def test_parse_event_all_day(self, calendar_client):
        """Test parsing an all-day event."""
        event = {
            'id': 'test_id',
            'summary': 'All Day Event',
            'start': {
                'date': '2023-01-01',
            },
            'end': {
                'date': '2023-01-02',
            }
        }
        
        result = calendar_client._parse_event(event)
        
        assert result['event_id'] == 'test_id'
        assert result['title'] == 'All Day Event'
        assert result['start_time'].hour == 0
        assert result['start_time'].minute == 0
        assert result['end_time'].hour == 23
        assert result['end_time'].minute == 59
    
    def test_parse_event_invalid_times(self, calendar_client):
        """Test parsing an event with invalid times."""
        event = {
            'id': 'test_id',
            'summary': 'Invalid Event',
            # Missing start and end times
        }
        
        result = calendar_client._parse_event(event)
        assert result is None
    
    def test_parse_event_exception(self, calendar_client):
        """Test exception handling in event parsing."""
        event = {
            'id': 'test_id',
            'summary': 'Bad Event',
            'start': {
                'dateTime': 'not-a-date',  # Invalid date format
            },
            'end': {
                'dateTime': '2023-01-01T11:00:00Z',
            }
        }
        
        result = calendar_client._parse_event(event)
        assert result is None


class TestIngestCalendarEvents:
    """Tests for the ingest_calendar_events function."""
    
    @patch('src.ingestion.calendar_ingestion.CalendarClient')
    @patch('src.ingestion.calendar_ingestion.store_calendar_event')
    def test_ingest_calendar_events_success(self, mock_store_event, MockCalendarClient):
        """Test successful calendar events ingestion."""
        # Setup mock client
        mock_client = MagicMock()
        MockCalendarClient.return_value = mock_client
        
        # Mock successful fetch
        mock_client.fetch_events.return_value = [
            {
                'event_id': 'event1',
                'title': 'Test Event 1',
                'location': 'Test Location',
                'description': 'Test Description',
                'start_time': datetime.now(),
                'end_time': datetime.now() + timedelta(hours=1),
                'attendees': 'person1@example.com, person2@example.com'
            },
            {
                'event_id': 'event2',
                'title': 'Test Event 2',
                'location': '',
                'description': '',
                'start_time': datetime.now() + timedelta(days=1),
                'end_time': datetime.now() + timedelta(days=1, hours=1),
                'attendees': ''
            }
        ]
        
        # Call the function
        total, stored = ingest_calendar_events(days_past=0, days_future=30)
        
        # Assertions
        assert total == 2
        assert stored == 2
        assert mock_client.authenticate.call_count == 1
        assert mock_client.fetch_events.call_count == 1
        assert mock_store_event.call_count == 2
    
    @patch('src.ingestion.calendar_ingestion.CalendarClient')
    @patch('src.ingestion.calendar_ingestion.store_calendar_event')
    def test_ingest_calendar_events_partial_storage(self, mock_store_event, MockCalendarClient):
        """Test calendar events ingestion with some storage failures."""
        # Setup mock client
        mock_client = MagicMock()
        MockCalendarClient.return_value = mock_client
        
        # Mock successful fetch
        mock_client.fetch_events.return_value = [
            {
                'event_id': 'event1',
                'title': 'Test Event 1',
                'location': 'Test Location',
                'description': 'Test Description',
                'start_time': datetime.now(),
                'end_time': datetime.now() + timedelta(hours=1),
                'attendees': 'person1@example.com, person2@example.com'
            },
            {
                'event_id': 'event2',
                'title': 'Test Event 2',
                'location': '',
                'description': '',
                'start_time': datetime.now() + timedelta(days=1),
                'end_time': datetime.now() + timedelta(days=1, hours=1),
                'attendees': ''
            }
        ]
        
        # Make the second store_event call fail
        mock_store_event.side_effect = [None, Exception("Database error")]
        
        # Call the function
        total, stored = ingest_calendar_events(days_past=0, days_future=30)
        
        # Assertions
        assert total == 2
        assert stored == 1
        assert mock_client.authenticate.call_count == 1
        assert mock_client.fetch_events.call_count == 1
        assert mock_store_event.call_count == 2
    
    @patch('src.ingestion.calendar_ingestion.CalendarClient')
    def test_ingest_calendar_events_authentication_failure(self, MockCalendarClient):
        """Test calendar events ingestion with authentication failure."""
        # Setup mock client
        mock_client = MagicMock()
        MockCalendarClient.return_value = mock_client
        
        # Make authentication fail
        mock_client.authenticate.side_effect = Exception("Authentication failed")
        
        # Call the function
        total, stored = ingest_calendar_events(days_past=0, days_future=30)
        
        # Assertions
        assert total == 0
        assert stored == 0
        assert mock_client.authenticate.call_count == 1
        assert mock_client.fetch_events.call_count == 0
    
    @patch('src.ingestion.calendar_ingestion.CalendarClient')
    def test_ingest_calendar_events_fetch_failure(self, MockCalendarClient):
        """Test calendar events ingestion with fetch failure."""
        # Setup mock client
        mock_client = MagicMock()
        MockCalendarClient.return_value = mock_client
        
        # Make fetch fail
        mock_client.fetch_events.side_effect = Exception("Fetch failed")
        
        # Call the function
        total, stored = ingest_calendar_events(days_past=0, days_future=30)
        
        # Assertions
        assert total == 0
        assert stored == 0
        assert mock_client.authenticate.call_count == 1
        assert mock_client.fetch_events.call_count == 1