"""
Unit tests for email ingestion module.
"""
import os
import pytest
from unittest.mock import patch, MagicMock
from datetime import datetime

from src.ingestion.email_ingestion import GmailClient, ingest_emails


@pytest.fixture
def mock_gmail_service():
    """Fixture for mocking Gmail service."""
    mock_service = MagicMock()
    
    # Mock messages list and get methods
    mock_list = MagicMock()
    mock_list.execute.return_value = {
        'messages': [
            {'id': 'msg_1'},
            {'id': 'msg_2'},
            {'id': 'msg_3'}
        ]
    }
    
    mock_service.users().messages().list.return_value = mock_list
    
    # Mock a sample email response
    def mock_get_message(userId, id):
        mock_get = MagicMock()
        mock_get.execute.return_value = {
            'id': id,
            'payload': {
                'headers': [
                    {'name': 'Subject', 'value': f'Test Email {id}'},
                    {'name': 'From', 'value': 'sender@example.com'},
                    {'name': 'To', 'value': 'recipient@example.com'},
                    {'name': 'Date', 'value': 'Mon, 1 Jan 2023 12:00:00 +0000'}
                ],
                'parts': [
                    {
                        'mimeType': 'text/plain',
                        'body': {
                            'data': 'VGhpcyBpcyBhIHRlc3QgZW1haWw='  # "This is a test email" in base64
                        }
                    }
                ]
            }
        }
        return mock_get
    
    mock_service.users().messages().get = mock_get_message
    
    return mock_service


@pytest.fixture
def gmail_client():
    """Fixture for creating a GmailClient instance with mocked credentials."""
    with patch('os.path.exists', return_value=True), \
         patch('builtins.open', MagicMock()), \
         patch('google.oauth2.credentials.Credentials.from_authorized_user_info', MagicMock()):
        client = GmailClient(
            credentials_file="dummy_credentials.json",
            token_file="dummy_token.json"
        )
        yield client


class TestGmailClient:
    """Tests for the GmailClient class."""
    
    def test_init(self):
        """Test initialization of GmailClient."""
        with patch.dict(os.environ, {"GMAIL_CREDENTIALS_FILE": "env_credentials.json", 
                                    "GMAIL_TOKEN_FILE": "env_token.json"}):
            client = GmailClient()
            assert client.credentials_file == "env_credentials.json"
            assert client.token_file == "env_token.json"
            assert client.service is None
        
        client = GmailClient(credentials_file="custom_credentials.json", token_file="custom_token.json")
        assert client.credentials_file == "custom_credentials.json"
        assert client.token_file == "custom_token.json"
    
    def test_authenticate(self, gmail_client):
        """Test authentication process."""
        with patch('google.oauth2.credentials.Credentials.valid', True), \
             patch('googleapiclient.discovery.build', return_value="mock_service"):
            gmail_client.authenticate()
            assert gmail_client.service == "mock_service"
    
    def test_authenticate_refresh_token(self, gmail_client):
        """Test authentication with token refresh."""
        mock_creds = MagicMock()
        mock_creds.valid = False
        mock_creds.expired = True
        mock_creds.refresh_token = True
        
        with patch('google.oauth2.credentials.Credentials.from_authorized_user_info', return_value=mock_creds), \
             patch('googleapiclient.discovery.build', return_value="mock_service"):
            gmail_client.authenticate()
            mock_creds.refresh.assert_called_once()
            assert gmail_client.service == "mock_service"
    
    def test_authenticate_new_flow(self, gmail_client):
        """Test authentication with new flow."""
        mock_flow = MagicMock()
        mock_flow.run_local_server.return_value = MagicMock()
        
        with patch('google.oauth2.credentials.Credentials.from_authorized_user_info', 
                  side_effect=Exception("Invalid token")), \
             patch('google_auth_oauthlib.flow.InstalledAppFlow.from_client_secrets_file', 
                  return_value=mock_flow), \
             patch('googleapiclient.discovery.build', return_value="mock_service"):
            gmail_client.authenticate()
            mock_flow.run_local_server.assert_called_once()
            assert gmail_client.service == "mock_service"
    
    def test_fetch_emails_no_service(self, gmail_client):
        """Test fetching emails without an initialized service."""
        emails = gmail_client.fetch_emails()
        assert emails == []
    
    def test_fetch_emails_success(self, gmail_client, mock_gmail_service):
        """Test successful email fetching."""
        gmail_client.service = mock_gmail_service
        emails = gmail_client.fetch_emails(days=1)
        
        assert len(emails) == 3
        assert emails[0]["message_id"] == "msg_1"
        assert emails[0]["subject"] == "Test Email msg_1"
        assert emails[0]["sender"] == "sender@example.com"
        assert emails[0]["content"] == "This is a test email"
    
    def test_fetch_emails_http_error(self, gmail_client):
        """Test handling of HTTP errors."""
        gmail_client.service = MagicMock()
        gmail_client.service.users().messages().list.side_effect = \
            Exception("HTTP Error")
        
        emails = gmail_client.fetch_emails()
        assert emails == []
    
    def test_fetch_emails_no_messages(self, gmail_client):
        """Test when no emails are found."""
        mock_service = MagicMock()
        mock_list = MagicMock()
        mock_list.execute.return_value = {'messages': []}
        mock_service.users().messages().list.return_value = mock_list
        
        gmail_client.service = mock_service
        emails = gmail_client.fetch_emails()
        assert emails == []
    
    def test_parse_message(self, gmail_client):
        """Test parsing a message."""
        message = {
            'id': 'test_id',
            'payload': {
                'headers': [
                    {'name': 'Subject', 'value': 'Test Subject'},
                    {'name': 'From', 'value': 'test@example.com'},
                    {'name': 'To', 'value': 'recipient@example.com'},
                    {'name': 'Date', 'value': 'Mon, 1 Jan 2023 12:00:00 +0000'}
                ],
                'parts': [
                    {
                        'mimeType': 'text/plain',
                        'body': {
                            'data': 'VGhpcyBpcyBhIHRlc3QgZW1haWw='  # "This is a test email" in base64
                        }
                    }
                ]
            }
        }
        
        result = gmail_client._parse_message(message)
        assert result['message_id'] == 'test_id'
        assert result['subject'] == 'Test Subject'
        assert result['sender'] == 'test@example.com'
        assert result['recipients'] == 'recipient@example.com'
        assert isinstance(result['received_at'], datetime)
        assert result['content'] == "This is a test email"
    
    def test_parse_message_no_parts(self, gmail_client):
        """Test parsing a message with no parts."""
        message = {
            'id': 'test_id',
            'payload': {
                'headers': [
                    {'name': 'Subject', 'value': 'Test Subject'},
                    {'name': 'From', 'value': 'test@example.com'},
                    {'name': 'To', 'value': 'recipient@example.com'},
                    {'name': 'Date', 'value': 'Mon, 1 Jan 2023 12:00:00 +0000'}
                ],
                'body': {
                    'data': 'VGhpcyBpcyBhIHRlc3QgZW1haWw='  # "This is a test email" in base64
                }
            }
        }
        
        result = gmail_client._parse_message(message)
        assert result['message_id'] == 'test_id'
        assert result['subject'] == 'Test Subject'
        assert result['content'] == "This is a test email"


class TestIngestEmails:
    """Tests for the ingest_emails function."""
    
    @patch('src.ingestion.email_ingestion.GmailClient')
    @patch('src.ingestion.email_ingestion.store_email')
    def test_ingest_emails_success(self, mock_store_email, MockGmailClient):
        """Test successful email ingestion."""
        # Setup mock client
        mock_client = MagicMock()
        MockGmailClient.return_value = mock_client
        
        # Mock successful fetch
        mock_client.fetch_emails.return_value = [
            {
                'message_id': 'msg_1',
                'subject': 'Test Email 1',
                'sender': 'sender@example.com',
                'recipients': 'recipient@example.com',
                'received_at': datetime.now(),
                'content': 'Test content 1'
            },
            {
                'message_id': 'msg_2',
                'subject': 'Test Email 2',
                'sender': 'sender@example.com',
                'recipients': 'recipient@example.com',
                'received_at': datetime.now(),
                'content': 'Test content 2'
            }
        ]
        
        # Call the function
        total, stored = ingest_emails(days=1)
        
        # Assertions
        assert total == 2
        assert stored == 2
        assert mock_client.authenticate.call_count == 1
        assert mock_client.fetch_emails.call_count == 1
        assert mock_store_email.call_count == 2
    
    @patch('src.ingestion.email_ingestion.GmailClient')
    @patch('src.ingestion.email_ingestion.store_email')
    def test_ingest_emails_partial_storage(self, mock_store_email, MockGmailClient):
        """Test email ingestion with some storage failures."""
        # Setup mock client
        mock_client = MagicMock()
        MockGmailClient.return_value = mock_client
        
        # Mock successful fetch
        mock_client.fetch_emails.return_value = [
            {
                'message_id': 'msg_1',
                'subject': 'Test Email 1',
                'sender': 'sender@example.com',
                'recipients': 'recipient@example.com',
                'received_at': datetime.now(),
                'content': 'Test content 1'
            },
            {
                'message_id': 'msg_2',
                'subject': 'Test Email 2',
                'sender': 'sender@example.com',
                'recipients': 'recipient@example.com',
                'received_at': datetime.now(),
                'content': 'Test content 2'
            }
        ]
        
        # Make the second store_email call fail
        mock_store_email.side_effect = [None, Exception("Database error")]
        
        # Call the function
        total, stored = ingest_emails(days=1)
        
        # Assertions
        assert total == 2
        assert stored == 1
        assert mock_client.authenticate.call_count == 1
        assert mock_client.fetch_emails.call_count == 1
        assert mock_store_email.call_count == 2
    
    @patch('src.ingestion.email_ingestion.GmailClient')
    def test_ingest_emails_authentication_failure(self, MockGmailClient):
        """Test email ingestion with authentication failure."""
        # Setup mock client
        mock_client = MagicMock()
        MockGmailClient.return_value = mock_client
        
        # Make authentication fail
        mock_client.authenticate.side_effect = Exception("Authentication failed")
        
        # Call the function
        total, stored = ingest_emails(days=1)
        
        # Assertions
        assert total == 0
        assert stored == 0
        assert mock_client.authenticate.call_count == 1
        assert mock_client.fetch_emails.call_count == 0
    
    @patch('src.ingestion.email_ingestion.GmailClient')
    def test_ingest_emails_fetch_failure(self, MockGmailClient):
        """Test email ingestion with fetch failure."""
        # Setup mock client
        mock_client = MagicMock()
        MockGmailClient.return_value = mock_client
        
        # Make fetch fail
        mock_client.fetch_emails.side_effect = Exception("Fetch failed")
        
        # Call the function
        total, stored = ingest_emails(days=1)
        
        # Assertions
        assert total == 0
        assert stored == 0
        assert mock_client.authenticate.call_count == 1
        assert mock_client.fetch_emails.call_count == 1