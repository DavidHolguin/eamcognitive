"""
Zero Trust Middleware - Security validation for all requests
"""

from datetime import datetime
from typing import Optional
from uuid import UUID

import structlog
from fastapi import Request, HTTPException, Depends
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from supabase import Client

from app.db.supabase import get_supabase_client
from app.db.models import AccessLevel, Profile
from app.core.state import SecurityContext
from app.config import get_settings

logger = structlog.get_logger(__name__)

security = HTTPBearer(auto_error=False)


class ZeroTrustValidator:
    """
    Zero Trust security validator.
    
    Principles:
    1. Never trust, always verify
    2. Assume breach
    3. Verify explicitly
    4. Use least privilege
    """
    
    @staticmethod
    def determine_access_level(request: Request) -> AccessLevel:
        """
        Determine access level based on request origin.
        
        Args:
            request: FastAPI request object
            
        Returns:
            Appropriate access level
        """
        client_host = request.client.host if request.client else "unknown"
        
        # Check for institutional network ranges (mock implementation)
        if client_host.startswith("192.168.") or client_host == "127.0.0.1":
            return AccessLevel.SEDE_PRINCIPAL
        
        # Check for VPN headers
        forwarded = request.headers.get("X-Forwarded-For", "")
        if "vpn.eam.edu.co" in forwarded or "10.0." in client_host:
            return AccessLevel.VPN_INSTITUCIONAL
        
        return AccessLevel.EXTERNO
    
    @staticmethod
    def verify_device(request: Request) -> bool:
        """
        Verify device trust status.
        
        Args:
            request: FastAPI request object
            
        Returns:
            True if device is verified
        """
        # Check for device verification header (set by MDM/device agent)
        device_token = request.headers.get("X-Device-Token")
        
        # Mock verification - in production, validate against device registry
        return device_token is not None and len(device_token) > 10


async def get_current_user(
    request: Request,
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(security)
) -> Optional[Profile]:
    """
    Get current authenticated user from Supabase JWT.
    
    Args:
        request: FastAPI request
        credentials: Bearer token credentials
        
    Returns:
        User profile or None
    """
    if not credentials:
        return None
    
    try:
        settings = get_settings()
        client = get_supabase_client()
        
        # Verify the JWT with Supabase
        user_response = client.auth.get_user(credentials.credentials)
        
        if not user_response or not user_response.user:
            return None
        
        user = user_response.user
        
        # Get profile from database
        profile_result = client.table("profiles").select("*").eq(
            "id", user.id
        ).single().execute()
        
        if profile_result.data:
            return Profile(**profile_result.data)
        
        return None
        
    except Exception as e:
        logger.warning("User authentication failed", error=str(e))
        return None


async def build_security_context(
    request: Request,
    user: Optional[Profile] = None
) -> SecurityContext:
    """
    Build security context for a request.
    
    Args:
        request: FastAPI request
        user: Authenticated user profile
        
    Returns:
        Security context for the request
    """
    validator = ZeroTrustValidator()
    
    # Get or generate session ID
    session_id = request.headers.get("X-Session-ID") or request.cookies.get("session_id") or str(UUID(int=0))
    
    return SecurityContext(
        user_id=UUID(user.id) if user else UUID(int=0),
        access_level=validator.determine_access_level(request).value,
        device_verified=validator.verify_device(request),
        session_id=session_id,
        ip_address=request.client.host if request.client else None,
        user_agent=request.headers.get("User-Agent")
    )


def require_access_level(minimum_level: AccessLevel):
    """
    Dependency that requires minimum access level.
    
    Usage:
        @app.get("/admin", dependencies=[Depends(require_access_level(AccessLevel.SEDE_PRINCIPAL))])
    """
    async def check_access(request: Request):
        validator = ZeroTrustValidator()
        current_level = validator.determine_access_level(request)
        
        level_order = {
            AccessLevel.EXTERNO: 0,
            AccessLevel.VPN_INSTITUCIONAL: 1,
            AccessLevel.SEDE_PRINCIPAL: 2
        }
        
        if level_order[current_level] < level_order[minimum_level]:
            logger.warning(
                "Access denied - insufficient level",
                required=minimum_level.value,
                current=current_level.value,
                ip=request.client.host if request.client else "unknown"
            )
            raise HTTPException(
                status_code=403,
                detail=f"Acceso denegado. Nivel requerido: {minimum_level.value}"
            )
        
        return current_level
    
    return check_access


def require_auth():
    """Dependency that requires authentication."""
    async def check_auth(
        request: Request,
        user: Optional[Profile] = Depends(get_current_user)
    ):
        if not user:
            raise HTTPException(
                status_code=401,
                detail="Autenticación requerida"
            )
        return user
    
    return check_auth
