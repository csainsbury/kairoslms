"""
Security utilities for kairoslms.

This module provides security-related functionality, including:
- Data encryption/decryption
- Password hashing and verification
- Token generation and validation
- Google OAuth authentication
"""
import os
import base64
import logging
import time
import json
from typing import Dict, Any, Optional, Union, Tuple
from datetime import datetime, timedelta

import jwt
from passlib.context import CryptContext
from cryptography.fernet import Fernet
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
from cryptography.hazmat.backends import default_backend
from fastapi import Request, HTTPException, Depends, status
from fastapi.security import OAuth2PasswordBearer
from pydantic import BaseModel

# Import error handling
from src.utils.error_handling import AuthenticationError, AuthorizationError, ConfigurationError

# Configure module logger
logger = logging.getLogger(__name__)

# Define models
class Token(BaseModel):
    """Token response model."""
    access_token: str
    token_type: str
    expires_at: int  # Expiration timestamp


class TokenData(BaseModel):
    """Token data model."""
    sub: str
    exp: int
    roles: list = []


class User(BaseModel):
    """User model."""
    username: str
    email: Optional[str] = None
    full_name: Optional[str] = None
    disabled: bool = False
    roles: list = []


# Initialize password context
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="api/auth/token")

# Initialize encryption key from environment
def get_encryption_key() -> bytes:
    """
    Get or generate a Fernet encryption key.
    
    Returns:
        bytes: The encryption key
    """
    # Get key from environment or generate a new one
    key = os.getenv("ENCRYPTION_KEY")
    
    if not key:
        # If no key is set, generate a warning
        logger.warning("No encryption key found in environment. Using a derived key from secret.")
        
        # Derive key from secret
        secret = os.getenv("SECRET_KEY")
        if not secret:
            raise ConfigurationError("Neither ENCRYPTION_KEY nor SECRET_KEY found in environment")
        
        # Use PBKDF2 to derive a key from the secret
        salt = b"kairoslms_static_salt"  # In production, this should be stored securely
        kdf = PBKDF2HMAC(
            algorithm=hashes.SHA256(),
            length=32,
            salt=salt,
            iterations=100000,
            backend=default_backend()
        )
        key = base64.urlsafe_b64encode(kdf.derive(secret.encode()))
    else:
        # Ensure key is in the correct format
        if not isinstance(key, bytes):
            key = key.encode()
        
        # Ensure key is a valid Fernet key (32 bytes, base64-encoded)
        try:
            key = base64.urlsafe_b64encode(base64.urlsafe_b64decode(key))
        except Exception:
            logger.error("Invalid encryption key format")
            raise ConfigurationError("Invalid encryption key format")
    
    return key


# Initialize Fernet cipher
try:
    ENCRYPTION_KEY = get_encryption_key()
    cipher = Fernet(ENCRYPTION_KEY)
except Exception as e:
    logger.error(f"Failed to initialize encryption: {str(e)}")
    cipher = None


def encrypt_data(data: Union[str, bytes, Dict[str, Any]]) -> str:
    """
    Encrypt data using Fernet symmetric encryption.
    
    Args:
        data: Data to encrypt (string, bytes, or dict)
        
    Returns:
        str: Base64-encoded encrypted data
        
    Raises:
        ConfigurationError: If encryption is not configured
    """
    if cipher is None:
        raise ConfigurationError("Encryption is not configured properly")
    
    # Convert data to bytes if it's not already
    if isinstance(data, dict):
        data = json.dumps(data).encode()
    elif isinstance(data, str):
        data = data.encode()
    
    # Encrypt and encode as base64
    encrypted = cipher.encrypt(data)
    return base64.urlsafe_b64encode(encrypted).decode()


def decrypt_data(encrypted_data: str) -> Union[str, Dict[str, Any]]:
    """
    Decrypt Fernet-encrypted data.
    
    Args:
        encrypted_data: Base64-encoded encrypted data
        
    Returns:
        Union[str, Dict[str, Any]]: Decrypted data
        
    Raises:
        ConfigurationError: If encryption is not configured
        ValueError: If data cannot be decrypted
    """
    if cipher is None:
        raise ConfigurationError("Encryption is not configured properly")
    
    try:
        # Decode base64 and decrypt
        decoded = base64.urlsafe_b64decode(encrypted_data)
        decrypted = cipher.decrypt(decoded)
        
        # Try to parse as JSON, otherwise return as string
        try:
            return json.loads(decrypted.decode())
        except json.JSONDecodeError:
            return decrypted.decode()
    except Exception as e:
        logger.error(f"Failed to decrypt data: {str(e)}")
        raise ValueError("Failed to decrypt data") from e


def hash_password(password: str) -> str:
    """
    Hash a password using bcrypt.
    
    Args:
        password: The password to hash
        
    Returns:
        str: Hashed password
    """
    return pwd_context.hash(password)


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """
    Verify a password against a hash.
    
    Args:
        plain_password: The plain text password
        hashed_password: The hashed password
        
    Returns:
        bool: True if the password matches the hash
    """
    return pwd_context.verify(plain_password, hashed_password)


def create_access_token(data: Dict[str, Any], expires_delta: Optional[timedelta] = None) -> Tuple[str, int]:
    """
    Create a JWT access token.
    
    Args:
        data: Data to encode in the token
        expires_delta: Optional expiration time delta
        
    Returns:
        Tuple[str, int]: The token and its expiration timestamp
    """
    secret_key = os.getenv("SECRET_KEY")
    if not secret_key:
        raise ConfigurationError("SECRET_KEY environment variable is not set")
    
    # Copy the data to avoid modifying the original
    to_encode = data.copy()
    
    # Set expiration
    if expires_delta:
        expire = datetime.utcnow() + expires_delta
    else:
        expire = datetime.utcnow() + timedelta(minutes=30)
    
    # Add expiration to the token
    expiration_timestamp = int(expire.timestamp())
    to_encode.update({"exp": expiration_timestamp})
    
    # Encode the token
    encoded_jwt = jwt.encode(to_encode, secret_key, algorithm="HS256")
    
    return encoded_jwt, expiration_timestamp


async def get_current_user(token: str = Depends(oauth2_scheme)) -> User:
    """
    Validate the token and get the current user.
    
    Args:
        token: JWT token
        
    Returns:
        User: The current user
        
    Raises:
        AuthenticationError: If authentication fails
    """
    credentials_exception = AuthenticationError("Could not validate credentials")
    
    try:
        secret_key = os.getenv("SECRET_KEY")
        if not secret_key:
            raise ConfigurationError("SECRET_KEY environment variable is not set")
        
        # Decode the token
        payload = jwt.decode(token, secret_key, algorithms=["HS256"])
        
        # Extract username (subject) from token
        username = payload.get("sub")
        if username is None:
            raise credentials_exception
        
        # Create token data
        token_data = TokenData(
            sub=username,
            exp=payload.get("exp", 0),
            roles=payload.get("roles", [])
        )
        
        # TODO: In a real application, get the user from the database
        # For now, just return a user with the username from the token
        user = User(
            username=token_data.sub,
            roles=token_data.roles
        )
        
        return user
    except jwt.PyJWTError as e:
        logger.warning(f"JWT validation failed: {str(e)}")
        raise credentials_exception


def authorize(required_roles: Optional[list] = None):
    """
    Dependency for role-based authorization.
    
    Args:
        required_roles: List of required roles
        
    Returns:
        Callable: Dependency that checks if the user has the required roles
    """
    async def authorize_user(user: User = Depends(get_current_user)):
        if required_roles:
            # Check if the user has any of the required roles
            has_role = any(role in user.roles for role in required_roles)
            if not has_role:
                raise AuthorizationError(f"User does not have required roles: {required_roles}")
        return user
    
    return authorize_user


# Google OAuth configuration
GOOGLE_CLIENT_ID = os.getenv("GOOGLE_CLIENT_ID")
GOOGLE_CLIENT_SECRET = os.getenv("GOOGLE_CLIENT_SECRET")
GOOGLE_REDIRECT_URI = os.getenv("GOOGLE_REDIRECT_URI", "http://localhost:8000/api/auth/google/callback")

def get_google_auth_url() -> str:
    """
    Get the Google OAuth authorization URL.
    
    Returns:
        str: Google OAuth authorization URL
    """
    if not GOOGLE_CLIENT_ID:
        raise ConfigurationError("GOOGLE_CLIENT_ID environment variable is not set")
    
    # Define OAuth parameters
    params = {
        "client_id": GOOGLE_CLIENT_ID,
        "redirect_uri": GOOGLE_REDIRECT_URI,
        "response_type": "code",
        "scope": "openid email profile",
        "prompt": "select_account"
    }
    
    # Build the URL
    url = "https://accounts.google.com/o/oauth2/auth"
    query = "&".join(f"{key}={value}" for key, value in params.items())
    
    return f"{url}?{query}"


def generate_backup_filename(prefix: str) -> str:
    """
    Generate a timestamped filename for backups.
    
    Args:
        prefix: Prefix for the filename
        
    Returns:
        str: Generated backup filename
    """
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    return f"{prefix}_{timestamp}.backup"