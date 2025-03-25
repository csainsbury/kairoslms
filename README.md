# Kairos Life Management System (kairoslms)

A comprehensive life management system designed to help users set and track strategic goals across multiple life domains. The system ingests data from various sources, processes it using a reasoning LLM, and produces actionable status overviews and prioritized task lists.

## Features

- **Data Ingestion**: Emails, Calendar, Todoist, and Biographical Context
- **Status Overviews**: Regular updates on high-level and project-level goals
- **Task Prioritization**: Intelligent ranking of tasks based on importance and deadlines
- **LLM Integration**: Uses Anthropic Claude for reasoning and guidance
- **User Interface**: Dashboard with goals, tasks, and a chat interface
- **Security**: JWT authentication, encryption, and comprehensive error handling
- **Scheduling**: Background jobs for data processing and analysis

## Getting Started

### Prerequisites

- Python 3.8+
- Docker and Docker Compose
- Gmail account for email ingestion
- Google Calendar and Todoist accounts
- Anthropic API key
- PostgreSQL (for local development)

### Installation

1. Clone the repository:
   ```
   git clone https://github.com/yourusername/kairoslms.git
   cd kairoslms
   ```

2. Set up environment variables:
   ```
   cp config/.env.example config/.env
   ```
   Edit the `.env` file with your API keys and configuration.

3. Build and run with Docker:
   ```
   docker-compose -f config/docker-compose.yml up --build
   ```

4. Or set up locally:
   ```
   python -m venv venv
   source venv/bin/activate  # On Windows: venv\Scripts\activate
   pip install -r requirements.txt
   python src/app.py
   ```

### Access the Application

Open your browser and navigate to `http://localhost:8000`.

## Project Structure

- `/src`: Application source code
  - `/api`: API endpoints (auth, dashboard, ingestion, etc.)
  - `/ingestion`: Data ingestion modules (email, calendar, todoist)
  - `/utils`: Utility modules (error handling, logging, security, etc.)
- `/tests`: Unit and integration tests
- `/config`: Configuration files (Docker, environment variables)
- `/templates`: HTML templates for the UI
- `/static`: Static assets (CSS, JavaScript)

## Testing

### Running Tests

```bash
# Run all tests
pytest tests/

# Run specific tests
pytest tests/test_db.py
pytest tests/test_email_ingestion.py

# Run with coverage
pytest --cov=src tests/
```

### Types of Tests

1. **Unit Tests**: Testing individual components in isolation
   - Database operations: `test_db.py`
   - Email ingestion: `test_email_ingestion.py`
   - Calendar ingestion: `test_calendar_ingestion.py`
   - Todoist integration: `test_todoist_ingestion.py`
   - LLM integration: `test_llm_integration.py`
   - Error handling: `test_error_handling.py`

2. **Integration Tests**: Testing how components work together
   - End-to-end workflow: `test_integration.py`
   - Complete data flow: `test_data_processor.py`
   - UI interactions: `test_ui.py`

3. **Deployment Tests**: Testing Docker deployment
   - Docker Compose setup: `test_deployment.py`
   - Container interactions
   - Network connectivity

## Deployment

### Local Deployment

For local development and testing:

```bash
docker-compose -f config/docker-compose.yml up --build
```

### Production Deployment

1. Set up environment variables on your server
2. Clone the repository
3. Run Docker Compose:
   ```bash
   docker-compose -f config/docker-compose.yml up -d
   ```

### CI/CD Pipeline

The project includes GitHub Actions workflows for continuous integration and deployment:

- `ci.yml`: Runs tests, linting, and builds Docker images
- `deploy.yml`: Deploys to staging or production environments

## Security

For security policies, procedures, and best practices, please refer to [security.md](security.md).

## Development

For development guidelines, testing procedures, and code standards, please refer to the [CLAUDE.md](CLAUDE.md) file.

## License

This project is licensed under the MIT License - see the LICENSE file for details.