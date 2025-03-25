"""
API package for kairoslms.
"""

from fastapi import APIRouter
from src.api.context_documents import router as context_documents_router
from src.api.ingestion import router as ingestion_router
from src.api.dashboard import router as dashboard_router
from src.api.chat import router as chat_router
from src.api.settings import router as settings_router
from src.api.auth import router as auth_router

# Create main API router
api_router = APIRouter()

# Include routers
api_router.include_router(auth_router)  # Auth router first for security
api_router.include_router(context_documents_router)
api_router.include_router(ingestion_router)
api_router.include_router(dashboard_router)
api_router.include_router(chat_router)
api_router.include_router(settings_router)