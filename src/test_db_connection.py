#!/usr/bin/env python3
"""
Test script to verify database connection and basic CRUD operations.
This is a utility script for development purposes, not a formal test.
"""
import os
import sys
import logging
from dotenv import load_dotenv

# Add parent directory to path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Import database functions
from src.db import (
    create_tables, create_context_document, get_context_document,
    get_context_documents_by_type, update_context_document
)

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)

def test_db_operations():
    """Test basic database operations."""
    # Create tables
    try:
        create_tables()
        logger.info("Database tables created successfully")
    except Exception as e:
        logger.error(f"Error creating database tables: {str(e)}")
        sys.exit(1)
    
    # Create a test context document
    try:
        doc = create_context_document(
            title="Test Biography",
            content="This is a test biography for database connection testing.",
            document_type="biography"
        )
        logger.info(f"Created test document with ID: {doc.id}")
    except Exception as e:
        logger.error(f"Error creating test document: {str(e)}")
        sys.exit(1)
    
    # Retrieve the document by ID
    try:
        retrieved_doc = get_context_document(doc.id)
        if retrieved_doc:
            logger.info(f"Retrieved document by ID: {retrieved_doc.id}, Title: {retrieved_doc.title}")
        else:
            logger.error("Failed to retrieve document by ID")
            sys.exit(1)
    except Exception as e:
        logger.error(f"Error retrieving document: {str(e)}")
        sys.exit(1)
    
    # Retrieve documents by type
    try:
        documents = get_context_documents_by_type("biography")
        logger.info(f"Retrieved {len(documents)} biography documents")
    except Exception as e:
        logger.error(f"Error retrieving documents by type: {str(e)}")
        sys.exit(1)
    
    # Update the document
    try:
        updated_doc = update_context_document(
            doc_id=doc.id,
            title="Updated Test Biography",
            content="This biography has been updated for testing purposes."
        )
        if updated_doc:
            logger.info(f"Updated document: {updated_doc.title}")
        else:
            logger.error("Failed to update document")
            sys.exit(1)
    except Exception as e:
        logger.error(f"Error updating document: {str(e)}")
        sys.exit(1)
    
    logger.info("All database operations completed successfully")

if __name__ == "__main__":
    # Load environment variables
    load_dotenv(os.path.join(os.path.dirname(os.path.dirname(__file__)), "config", ".env"))
    
    logger.info("Starting database connection test")
    test_db_operations()