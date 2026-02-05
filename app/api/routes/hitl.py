"""
HITL API Routes - Human-in-the-Loop approval management
"""

from typing import Any, Optional
from uuid import UUID

import structlog
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from app.db.models import HITLStatus
from app.security.hitl import (
    get_pending_hitl_requests,
    review_hitl_request,
    resume_after_hitl
)
from app.security.zero_trust import require_auth
from app.db.supabase import get_supabase_admin_client

logger = structlog.get_logger(__name__)

router = APIRouter(prefix="/hitl", tags=["HITL"])


class HITLReviewRequest(BaseModel):
    """Request body for reviewing a HITL request."""
    status: HITLStatus
    notes: Optional[str] = None


@router.get("/pending")
async def list_pending_requests(
    limit: int = 10,
    user = Depends(require_auth())
) -> dict[str, Any]:
    """Get pending HITL requests awaiting approval."""
    requests = await get_pending_hitl_requests(limit)
    
    return {
        "requests": [r.model_dump() for r in requests],
        "total": len(requests)
    }


@router.get("/{request_id}")
async def get_request(
    request_id: UUID,
    user = Depends(require_auth())
) -> dict[str, Any]:
    """Get a specific HITL request."""
    client = get_supabase_admin_client()
    
    result = client.table("hitl_requests").select(
        "*, agent_runs(input_params)"
    ).eq("id", str(request_id)).single().execute()
    
    if not result.data:
        raise HTTPException(status_code=404, detail="Solicitud no encontrada")
    
    return result.data


@router.post("/{request_id}/review")
async def review_request(
    request_id: UUID,
    review: HITLReviewRequest,
    user = Depends(require_auth())
) -> dict[str, Any]:
    """Review (approve/reject) a HITL request."""
    if review.status not in [HITLStatus.APPROVED, HITLStatus.REJECTED]:
        raise HTTPException(
            status_code=400,
            detail="El estado debe ser 'approved' o 'rejected'"
        )
    
    updated = await review_hitl_request(
        request_id=request_id,
        status=review.status,
        reviewer_id=UUID(str(user.id)),
        notes=review.notes
    )
    
    if not updated:
        raise HTTPException(status_code=404, detail="Solicitud no encontrada")
    
    logger.info(
        "HITL request reviewed",
        request_id=str(request_id),
        status=review.status.value,
        reviewer=str(user.id)
    )
    
    # If approved, resume execution
    result = {"request": updated.model_dump(), "resumed": False}
    
    if review.status == HITLStatus.APPROVED:
        resume_result = await resume_after_hitl(request_id)
        if resume_result:
            result["resumed"] = True
            result["resume_result"] = resume_result
    
    return result


@router.get("/stats")
async def get_hitl_stats(
    user = Depends(require_auth())
) -> dict[str, Any]:
    """Get HITL request statistics."""
    client = get_supabase_admin_client()
    
    # Get all requests
    result = client.table("hitl_requests").select("status, created_at").execute()
    requests = result.data or []
    
    # Calculate stats
    total = len(requests)
    by_status = {}
    for r in requests:
        status = r["status"]
        by_status[status] = by_status.get(status, 0) + 1
    
    return {
        "stats": {
            "total": total,
            "by_status": by_status,
            "pending": by_status.get("pending", 0),
            "approved": by_status.get("approved", 0),
            "rejected": by_status.get("rejected", 0),
            "expired": by_status.get("expired", 0)
        }
    }
