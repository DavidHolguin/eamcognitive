"""
Audit Logging - Security event tracking
"""

from datetime import datetime
from typing import Any, Optional
from uuid import UUID

import structlog
from fastapi import Request

from app.db.supabase import get_supabase_admin_client
from app.db.models import AccessLog, AccessLevel
from app.core.state import SecurityContext

logger = structlog.get_logger(__name__)


async def log_access(
    action: str,
    security_context: SecurityContext,
    resource_type: Optional[str] = None,
    resource_id: Optional[UUID] = None,
    metadata: Optional[dict[str, Any]] = None
) -> Optional[AccessLog]:
    """
    Log an access event to the audit trail.
    
    Args:
        action: The action performed (e.g., 'chat.send', 'agent.invoke')
        security_context: Security context from the request
        resource_type: Type of resource accessed (optional)
        resource_id: ID of resource accessed (optional)
        metadata: Additional metadata (optional)
        
    Returns:
        Created access log entry or None
    """
    client = get_supabase_admin_client()
    
    log_data = {
        "user_id": str(security_context.user_id) if security_context.user_id != UUID(int=0) else None,
        "action": action,
        "resource_type": resource_type,
        "resource_id": str(resource_id) if resource_id else None,
        "ip_address": security_context.ip_address,
        "user_agent": security_context.user_agent,
        "access_level": security_context.access_level,
        "device_verified": security_context.device_verified,
        "metadata": metadata
    }
    
    try:
        result = client.table("access_logs").insert(log_data).execute()
        
        if result.data:
            logger.debug(
                "Access logged",
                action=action,
                user_id=str(security_context.user_id)
            )
            return AccessLog(**result.data[0])
        
    except Exception as e:
        logger.error(
            "Failed to log access",
            action=action,
            error=str(e)
        )
    
    return None


async def log_security_event(
    event_type: str,
    severity: str,
    description: str,
    request: Request,
    metadata: Optional[dict[str, Any]] = None
) -> None:
    """
    Log a security-related event.
    
    Args:
        event_type: Type of event (auth_failure, suspicious_activity, etc.)
        severity: Event severity (info, warning, critical)
        description: Human-readable description
        request: FastAPI request object
        metadata: Additional data
    """
    client = get_supabase_admin_client()
    
    log_data = {
        "action": f"security.{event_type}",
        "ip_address": request.client.host if request.client else None,
        "user_agent": request.headers.get("User-Agent"),
        "metadata": {
            "severity": severity,
            "description": description,
            **(metadata or {})
        }
    }
    
    try:
        client.table("access_logs").insert(log_data).execute()
        
        # Also log to structured logger
        log_method = getattr(logger, severity, logger.info)
        log_method(
            f"Security event: {event_type}",
            description=description,
            ip=request.client.host if request.client else "unknown"
        )
        
    except Exception as e:
        logger.error(
            "Failed to log security event",
            event_type=event_type,
            error=str(e)
        )


class AuditContext:
    """Context manager for auditing a request."""
    
    def __init__(
        self,
        action: str,
        security_context: SecurityContext,
        resource_type: Optional[str] = None,
        resource_id: Optional[UUID] = None
    ):
        self.action = action
        self.security_context = security_context
        self.resource_type = resource_type
        self.resource_id = resource_id
        self.start_time = None
        self.metadata: dict[str, Any] = {}
    
    async def __aenter__(self):
        self.start_time = datetime.utcnow()
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        duration_ms = int((datetime.utcnow() - self.start_time).total_seconds() * 1000)
        self.metadata["duration_ms"] = duration_ms
        
        if exc_type:
            self.metadata["error"] = str(exc_val)
            self.metadata["success"] = False
        else:
            self.metadata["success"] = True
        
        await log_access(
            action=self.action,
            security_context=self.security_context,
            resource_type=self.resource_type,
            resource_id=self.resource_id,
            metadata=self.metadata
        )
        
        return False  # Don't suppress exceptions
