"""
Development Authentication Module
This module provides authentication bypass for local testing.
NEVER USE IN PRODUCTION!
"""

import os
from typing import Dict, Any, Optional
from datetime import datetime, timedelta
from jose import jwt
import logging

logger = logging.getLogger(__name__)

# Test user for development
TEST_USER = {
    "user_id": "test-user-123",
    "email": "test@example.com",
    "role": "admin",
    "api_usage_quota": 10000,
    "storage_quota_mb": 5000
}

class DevAuthService:
    """Development authentication service for local testing."""

    def __init__(self):
        self.is_dev_mode = os.getenv('TESTING_MODE', 'false').lower() == 'true'
        self.secret_key = os.getenv('SECRET_KEY', 'dev-secret-key-for-testing-only')

    def create_test_token(self, user_id: str = None) -> str:
        """Create a test JWT token for development."""
        if not self.is_dev_mode:
            raise RuntimeError("Test tokens can only be created in development mode")

        payload = {
            "user_id": user_id or TEST_USER["user_id"],
            "email": TEST_USER["email"],
            "role": TEST_USER["role"],
            "exp": datetime.utcnow() + timedelta(hours=24),  # 24 hour expiry
            "iat": datetime.utcnow(),
            "testing": True
        }

        return jwt.encode(payload, self.secret_key, algorithm="HS256")

    def verify_test_token(self, token: str) -> Dict[str, Any]:
        """Verify a test token."""
        try:
            # In dev mode, accept any token starting with 'test-token-'
            if self.is_dev_mode and token.startswith('test-token-'):
                return TEST_USER

            # Try to decode as JWT
            payload = jwt.decode(token, self.secret_key, algorithms=["HS256"])

            # In dev mode, don't validate expiry
            if self.is_dev_mode:
                return {
                    "user_id": payload.get("user_id", TEST_USER["user_id"]),
                    "email": payload.get("email", TEST_USER["email"]),
                    "role": payload.get("role", "user")
                }

            return payload

        except Exception as e:
            logger.warning(f"Token verification failed: {e}")

            # In dev mode, return test user for any token
            if self.is_dev_mode:
                logger.info("Using test user for development")
                return TEST_USER

            raise

    def get_test_user(self, user_id: str = None) -> Dict[str, Any]:
        """Get test user data."""
        if not self.is_dev_mode:
            raise RuntimeError("Test users are only available in development mode")

        test_user = TEST_USER.copy()
        if user_id:
            test_user["user_id"] = user_id

        return test_user

    def check_rate_limit(self, user_id: str) -> bool:
        """Check rate limit for test user (always returns True in dev mode)."""
        if self.is_dev_mode:
            return True

        # Implement actual rate limiting for non-dev mode
        return False


# Development middleware for auth bypass
async def get_current_user_dev(token: Optional[str] = None) -> Dict[str, Any]:
    """
    Get current user for development mode.
    This bypasses actual authentication when TESTING_MODE=true.
    """
    dev_auth = DevAuthService()

    if dev_auth.is_dev_mode:
        logger.info("Development mode: bypassing authentication")
        return dev_auth.get_test_user()

    # In production, this should never be called
    raise RuntimeError("Development auth called in production mode")


async def check_rate_limit_dev(user_id: str = None) -> Dict[str, Any]:
    """
    Check rate limit for development mode.
    Always returns success in dev mode.
    """
    dev_auth = DevAuthService()

    if dev_auth.is_dev_mode:
        return {
            "user_id": user_id or TEST_USER["user_id"],
            "rate_limit_ok": True,
            "remaining_requests": 9999
        }

    raise RuntimeError("Development rate limit called in production mode")


class DevPermissionChecker:
    """Development permission checker that always allows everything."""

    @staticmethod
    async def check_document_access(user_id: str, document_id: str) -> bool:
        """Always allow document access in dev mode."""
        if os.getenv('TESTING_MODE', 'false').lower() == 'true':
            return True
        return False

    @staticmethod
    async def check_storage_quota(user_id: str, file_size: int) -> bool:
        """Always allow uploads in dev mode."""
        if os.getenv('TESTING_MODE', 'false').lower() == 'true':
            return True
        return False


def init_dev_database():
    """Initialize database with test data for development."""
    if os.getenv('TESTING_MODE', 'false').lower() != 'true':
        raise RuntimeError("Dev database initialization only in testing mode")

    logger.info("Initializing development database with test data...")

    # This would create test users, documents, etc. in the database
    # For now, we'll just log that it would happen
    logger.info("Development database ready")


# Monkey patch for development mode
def patch_auth_for_development():
    """
    Patch authentication functions for development mode.
    This should be called in main.py when TESTING_MODE=true.
    """
    if os.getenv('TESTING_MODE', 'false').lower() != 'true':
        return

    logger.warning("=" * 60)
    logger.warning("DEVELOPMENT MODE ACTIVE - AUTHENTICATION BYPASSED")
    logger.warning("DO NOT USE IN PRODUCTION!")
    logger.warning("=" * 60)

    # Import the actual auth module
    import src.core.auth as auth

    # Replace auth functions with dev versions
    original_get_current_user = auth.get_current_user
    original_check_rate_limit = auth.check_rate_limit

    from fastapi.security import HTTPAuthorizationCredentials
    from typing import Optional

    async def dev_get_current_user(credentials: Optional[HTTPAuthorizationCredentials] = None):
        """Development version of get_current_user."""
        logger.debug(f"Dev auth: returning test user {TEST_USER['user_id']}")
        return TEST_USER

    async def dev_check_rate_limit(credentials: Optional[HTTPAuthorizationCredentials] = None):
        """Development version of check_rate_limit."""
        logger.debug(f"Dev auth: bypassing rate limit for {TEST_USER['user_id']}")
        return TEST_USER

    # Monkey patch
    auth.get_current_user = dev_get_current_user
    auth.check_rate_limit = dev_check_rate_limit

    logger.info("Authentication functions patched for development")

    # Also patch PermissionChecker
    if hasattr(auth, 'PermissionChecker'):
        auth.PermissionChecker.check_document_access = DevPermissionChecker.check_document_access
        auth.PermissionChecker.check_storage_quota = DevPermissionChecker.check_storage_quota

    logger.info("Permission checker patched for development")