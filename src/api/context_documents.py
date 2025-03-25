"""
API endpoints for managing context documents.
"""
from typing import List, Optional
from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from src.db import (
    get_db, get_context_document, get_context_documents_by_type,
    create_context_document, update_context_document
)

# Create router
router = APIRouter(prefix="/context-documents", tags=["context-documents"])

# Pydantic models for request and response
class ContextDocumentBase(BaseModel):
    """Base model for context document data."""
    title: str = Field(..., title="Document title", max_length=255)
    content: str = Field(..., title="Document content")
    document_type: str = Field(..., title="Type of document (e.g., 'biography', 'project_doc')")

class ContextDocumentCreate(ContextDocumentBase):
    """Model for creating a context document."""
    pass

class ContextDocumentUpdate(BaseModel):
    """Model for updating a context document."""
    title: Optional[str] = Field(None, title="Document title", max_length=255)
    content: Optional[str] = Field(None, title="Document content")

class ContextDocumentResponse(ContextDocumentBase):
    """Model for context document response."""
    id: int
    created_at: str
    updated_at: Optional[str] = None

    class Config:
        orm_mode = True

# API endpoints
@router.post("/", response_model=ContextDocumentResponse, status_code=201)
def create_document(document: ContextDocumentCreate, db: Session = Depends(get_db)):
    """Create a new context document."""
    try:
        db_document = create_context_document(
            title=document.title,
            content=document.content,
            document_type=document.document_type
        )
        return db_document
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to create document: {str(e)}")

@router.get("/{document_id}", response_model=ContextDocumentResponse)
def get_document(document_id: int, db: Session = Depends(get_db)):
    """Get a specific context document by ID."""
    document = get_context_document(document_id)
    if document is None:
        raise HTTPException(status_code=404, detail="Document not found")
    return document

@router.get("/", response_model=List[ContextDocumentResponse])
def get_documents_by_type(document_type: str, db: Session = Depends(get_db)):
    """Get all context documents of a specific type."""
    documents = get_context_documents_by_type(document_type)
    return documents

@router.put("/{document_id}", response_model=ContextDocumentResponse)
def update_document(document_id: int, document: ContextDocumentUpdate, db: Session = Depends(get_db)):
    """Update a context document."""
    db_document = get_context_document(document_id)
    if db_document is None:
        raise HTTPException(status_code=404, detail="Document not found")
    
    try:
        updated_document = update_context_document(
            doc_id=document_id,
            title=document.title,
            content=document.content
        )
        return updated_document
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to update document: {str(e)}")

@router.get("/biography/latest", response_model=ContextDocumentResponse)
def get_latest_biography(db: Session = Depends(get_db)):
    """Get the most recent biography document."""
    biographies = get_context_documents_by_type("biography")
    if not biographies:
        raise HTTPException(status_code=404, detail="No biography document found")
    # Return the most recently updated biography
    return sorted(biographies, key=lambda doc: doc.updated_at or doc.created_at, reverse=True)[0]