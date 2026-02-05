"""EAM Cognitive OS - Security module."""

from app.security.hitl import (
    create_hitl_request,
    get_pending_hitl_requests,
    review_hitl_request,
    resume_after_hitl,
)
from app.security.zero_trust import (
    ZeroTrustValidator,
    get_current_user,
    build_security_context,
    require_access_level,
    require_auth,
)
from app.security.audit import (
    log_access,
    log_security_event,
    AuditContext,
)

__all__ = [
    "create_hitl_request",
    "get_pending_hitl_requests",
    "review_hitl_request",
    "resume_after_hitl",
    "ZeroTrustValidator",
    "get_current_user",
    "build_security_context",
    "require_access_level",
    "require_auth",
    "log_access",
    "log_security_event",
    "AuditContext",
]
