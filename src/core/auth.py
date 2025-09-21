from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from jose import JWTError, jwt
from datetime import datetime, timedelta
from typing import Optional, Dict, Any
import logging
from src.config.settings import settings
from src.core.database import supabase

logger = logging.getLogger(__name__)

security = HTTPBearer()


class AuthenticationError(HTTPException):
    def __init__(self, detail: str = "Could not validate credentials"):
        super().__init__(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=detail,
            headers={"WWW-Authenticate": "Bearer"},
        )


def create_access_token(data: dict, expires_delta: Optional[timedelta] = None):
    """
    Create a new JWT access token.
    """
    to_encode = data.copy()
    if expires_delta:
        expire = datetime.utcnow() + expires_delta
    else:
        expire = datetime.utcnow() + timedelta(minutes=settings.access_token_expire_minutes)

    to_encode.update({"exp": expire, "iat": datetime.utcnow()})
    encoded_jwt = jwt.encode(to_encode, settings.secret_key, algorithm=settings.algorithm)
    return encoded_jwt


def decode_token(token: str) -> Dict[str, Any]:
    """
    Decode and validate a JWT token.
    """
    try:
        payload = jwt.decode(token, settings.secret_key, algorithms=[settings.algorithm])
        return payload
    except JWTError as e:
        logger.error(f"JWT decode error: {e}")
        raise AuthenticationError("Invalid token")


async def verify_supabase_token(token: str) -> Dict[str, Any]:
    """
    Verify token with Supabase Auth service.
    """
    try:
        # Verify token with Supabase
        response = supabase.auth.get_user(token)
        if response and response.user:
            return {
                "user_id": response.user.id,
                "email": response.user.email,
                "metadata": response.user.user_metadata,
            }
        raise AuthenticationError("Invalid Supabase token")
    except Exception as e:
        logger.error(f"Supabase token verification failed: {e}")
        raise AuthenticationError("Token verification failed")


async def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(security)
) -> Dict[str, Any]:
    """
    FastAPI dependency to get the current authenticated user.
    """
    token = credentials.credentials

    # Try to decode as JWT first
    try:
        payload = decode_token(token)
        user_id = payload.get("sub") or payload.get("user_id")
        if not user_id:
            raise AuthenticationError("Invalid token payload")

        return {
            "user_id": user_id,
            "email": payload.get("email"),
            "token_type": "jwt",
        }
    except AuthenticationError:
        # If JWT fails, try Supabase token verification
        return await verify_supabase_token(token)


async def get_optional_user(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(security)
) -> Optional[Dict[str, Any]]:
    """
    Optional authentication - returns None if no valid token.
    """
    if not credentials:
        return None

    try:
        return await get_current_user(credentials)
    except AuthenticationError:
        return None


class RateLimiter:
    """
    Simple in-memory rate limiter.
    """
    def __init__(self):
        self.requests = {}
        self.upload_requests = {}

    def check_rate_limit(self, user_id: str, is_upload: bool = False) -> bool:
        """
        Check if user has exceeded rate limit.
        """
        now = datetime.utcnow()
        hour_ago = now - timedelta(hours=1)

        if is_upload:
            # Check upload rate limit
            user_uploads = self.upload_requests.get(user_id, [])
            recent_uploads = [t for t in user_uploads if t > hour_ago]

            if len(recent_uploads) >= settings.rate_limit_upload_per_hour:
                return False

            recent_uploads.append(now)
            self.upload_requests[user_id] = recent_uploads[-100:]  # Keep last 100
        else:
            # Check general rate limit
            user_requests = self.requests.get(user_id, [])
            recent_requests = [t for t in user_requests if t > hour_ago]

            if len(recent_requests) >= settings.rate_limit_requests_per_hour:
                return False

            recent_requests.append(now)
            self.requests[user_id] = recent_requests[-1000:]  # Keep last 1000

        return True


rate_limiter = RateLimiter()


async def check_rate_limit(
    user: Dict[str, Any] = Depends(get_current_user),
    is_upload: bool = False
):
    """
    FastAPI dependency to check rate limits.
    """
    user_id = user["user_id"]

    if not rate_limiter.check_rate_limit(user_id, is_upload):
        limit_type = "upload" if is_upload else "request"
        limit_value = settings.rate_limit_upload_per_hour if is_upload else settings.rate_limit_requests_per_hour

        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail=f"Rate limit exceeded. Maximum {limit_value} {limit_type}s per hour."
        )

    return user


class PermissionChecker:
    """
    Check user permissions for resources.
    """

    @staticmethod
    async def check_document_access(
        document_id: str,
        user_id: str,
        session_id: Optional[str] = None,
        project_id: Optional[str] = None
    ) -> bool:
        """
        Check if user has access to a document.
        """
        from src.core.database import get_db_session
        from src.models.database import Document

        with get_db_session() as db:
            query = db.query(Document).filter(
                Document.id == document_id,
                Document.user_id == user_id
            )

            if session_id:
                query = query.filter(Document.session_id == session_id)

            if project_id:
                query = query.filter(Document.project_id == project_id)

            return query.first() is not None

    @staticmethod
    async def check_storage_quota(user_id: str, file_size_bytes: int) -> bool:
        """
        Check if user has enough storage quota.
        """
        from src.core.database import get_db_session
        from src.models.database import Profile

        with get_db_session() as db:
            profile = db.query(Profile).filter(Profile.user_id == user_id).first()

            if not profile:
                # Create profile if doesn't exist
                profile = Profile(user_id=user_id)
                db.add(profile)
                db.commit()

            # Check quota
            file_size_mb = file_size_bytes / (1024 * 1024)
            available_quota = profile.storage_quota_mb - profile.storage_used_mb

            return file_size_mb <= available_quota