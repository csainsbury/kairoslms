"""
Authentication API for kairoslms.
"""
from typing import Optional
from datetime import datetime, timedelta
import os

from fastapi import APIRouter, Depends, HTTPException, status, Request, Response
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
from pydantic import BaseModel

from src.utils.security import (
    User, Token, verify_password, create_access_token,
    get_current_user, get_google_auth_url
)
from src.utils.error_handling import AuthenticationError, AuthorizationError
from src.utils.logging import get_logger

# Configure module logger
logger = get_logger(__name__)

router = APIRouter(prefix="/auth", tags=["authentication"])

# Define token URL
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="api/auth/token")


@router.post("/token", response_model=Token)
async def login_for_access_token(form_data: OAuth2PasswordRequestForm = Depends()):
    """
    OAuth2 compatible token login endpoint.
    """
    # In a real application, check against database
    # For demo purposes, use a hardcoded user
    if form_data.username != "demo" or form_data.password != "password":
        logger.warning(f"Authentication failed for user: {form_data.username}")
        raise AuthenticationError("Incorrect username or password")
    
    # Create access token
    access_token_expires = timedelta(
        minutes=int(os.getenv("ACCESS_TOKEN_EXPIRE_MINUTES", "30"))
    )
    
    access_token, expires_at = create_access_token(
        data={"sub": form_data.username, "roles": ["user"]},
        expires_delta=access_token_expires
    )
    
    logger.info(f"Login successful for user: {form_data.username}")
    
    return Token(
        access_token=access_token,
        token_type="bearer",
        expires_at=expires_at
    )


@router.get("/google/login")
async def google_login():
    """
    Initiate Google OAuth login flow.
    """
    try:
        auth_url = get_google_auth_url()
        return {"auth_url": auth_url}
    except Exception as e:
        logger.error(f"Failed to generate Google auth URL: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to initiate Google login flow"
        )


@router.get("/google/callback")
async def google_callback(code: str, request: Request):
    """
    Handle Google OAuth callback.
    """
    # In a real application, this would exchange the authorization code for tokens
    # and verify the user's identity with Google
    # For demo purposes, just create a token
    
    # Create a dummy user ID - in real app, this would come from Google profile
    user_id = "google_user_123"
    
    access_token_expires = timedelta(
        minutes=int(os.getenv("ACCESS_TOKEN_EXPIRE_MINUTES", "30"))
    )
    
    access_token, expires_at = create_access_token(
        data={"sub": user_id, "roles": ["user"]},
        expires_delta=access_token_expires
    )
    
    logger.info(f"Google login successful for user ID: {user_id}")
    
    # In a real app, you would want to redirect to the frontend with the token,
    # or set the token in a secure HTTP-only cookie
    return {
        "access_token": access_token,
        "token_type": "bearer",
        "expires_at": expires_at
    }


@router.get("/me", response_model=User)
async def read_users_me(current_user: User = Depends(get_current_user)):
    """
    Get the current authenticated user.
    """
    return current_user


@router.post("/logout")
async def logout(response: Response):
    """
    Logout the current user.
    
    In a stateless API using JWT, there's no server-side session to invalidate.
    The client should discard the token.
    
    This endpoint is mainly for logging purposes.
    """
    logger.info("User logged out")
    
    # In a real application with refresh tokens, you would invalidate them here
    return {"message": "Successfully logged out"}