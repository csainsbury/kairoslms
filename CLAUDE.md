# CLAUDE.md - kairoslms Development Guide

## Build & Run Commands
- Setup: `python -m venv venv && source venv/bin/activate && pip install -r requirements.txt`
- Run development server: `python src/app.py`
- Docker build & run: `docker-compose up --build`
- Deploy to production: `docker-compose -f docker-compose.prod.yml up -d`

## Test Commands
- Run all tests: `pytest tests/`
- Run single test: `pytest tests/path/to/test_file.py::TestClass::test_function`
- Run with coverage: `pytest --cov=src tests/`

## Lint & Format Commands
- Lint code: `flake8 src/ tests/`
- Format code: `black src/ tests/`
- Type check: `mypy src/`

## Code Style Guidelines
- Python: Follow PEP 8 style guide
- Module imports: Standard library → third-party → local modules, alphabetically within each group
- Naming: snake_case for functions/variables, CamelCase for classes
- Type annotations required for function parameters and return values
- Error handling: Use try/except blocks with specific exceptions
- Docstrings: Use Google-style docstrings for functions and classes
- Log errors with appropriate severity levels
- Security: Never hardcode credentials; use environment variables

## Project Structure
- `/src`: Application source code organized by module
- `/tests`: Unit and integration tests
- `/config`: Configuration files
- `/docs`: Documentation files