"""
HITL Manager - Human-in-the-Loop approval system
"""

from datetime import datetime, timedelta
from typing import Any, Optional
from uuid import UUID

import structlog

from app.db.supabase import get_supabase_admin_client
from app.db.models import HITLRequest, HITLStatus
from app.core.state import CognitiveState
from app.config import get_settings

logger = structlog.get_logger(__name__)


async def create_hitl_request(state: CognitiveState) -> Optional[HITLRequest]:
    """
    Create a HITL approval request in the database.
    
    Args:
        state: Current cognitive state with HITL info
        
    Returns:
        Created HITL request or None on failure
    """
    if not state.requires_hitl or not state.hitl_reason:
        return None
    
    settings = get_settings()
    client = get_supabase_admin_client()
    
    # Determine which agent requested (use last visited)
    requested_by = None
    if state.visited_agents:
        # Get agent ID from database by slot name
        agent_slot = state.visited_agents[-1]
        slot_value = agent_slot.value if hasattr(agent_slot, 'value') else agent_slot
        result = client.table("agents").select("id").eq("name", slot_value.capitalize()).single().execute()
        if result.data:
            requested_by = result.data["id"]
    
    if not requested_by:
        # Default to first agent
        result = client.table("agents").select("id").limit(1).single().execute()
        requested_by = result.data["id"] if result.data else None
    
    # Build request data
    request_data = {
        "run_id": str(state.run_id),
        "requested_by": requested_by,
        "reason": state.hitl_reason,
        "context": {
            "user_message": state.user_message,
            "visited_agents": [a.value if hasattr(a, 'value') else a for a in state.visited_agents],
            "current_response": state.current_response,
            "okr_context": state.okr_context.model_dump() if state.okr_context else None
        },
        "proposed_action": {
            "response": state.current_response,
            "brain_log_summary": [e.content for e in state.brain_log[-5:]]
        },
        "status": "pending",
        "expires_at": (datetime.utcnow() + timedelta(hours=settings.hitl_timeout_hours)).isoformat()
    }
    
    try:
        result = client.table("hitl_requests").insert(request_data).execute()
        
        if result.data:
            logger.info(
                "HITL request created",
                request_id=result.data[0]["id"],
                reason=state.hitl_reason
            )
            return HITLRequest(**result.data[0])
        
    except Exception as e:
        logger.error("Failed to create HITL request", error=str(e))
    
    return None


async def get_pending_hitl_requests(limit: int = 10) -> list[HITLRequest]:
    """Get pending HITL requests."""
    client = get_supabase_admin_client()
    
    try:
        result = client.table("hitl_requests").select("*").eq(
            "status", "pending"
        ).gt(
            "expires_at", datetime.utcnow().isoformat()
        ).order("created_at", desc=True).limit(limit).execute()
        
        return [HITLRequest(**r) for r in (result.data or [])]
        
    except Exception as e:
        logger.error("Failed to get pending HITL requests", error=str(e))
        return []


async def review_hitl_request(
    request_id: UUID,
    status: HITLStatus,
    reviewer_id: UUID,
    notes: Optional[str] = None
) -> Optional[HITLRequest]:
    """
    Review a HITL request (approve/reject).
    
    Args:
        request_id: The HITL request ID
        status: New status (approved/rejected)
        reviewer_id: User ID of the reviewer
        notes: Optional review notes
        
    Returns:
        Updated HITL request or None
    """
    client = get_supabase_admin_client()
    
    update_data = {
        "status": status,
        "reviewed_by": str(reviewer_id),
        "review_notes": notes,
        "reviewed_at": datetime.utcnow().isoformat()
    }
    
    try:
        result = client.table("hitl_requests").update(update_data).eq(
            "id", str(request_id)
        ).execute()
        
        if result.data:
            logger.info(
                "HITL request reviewed",
                request_id=str(request_id),
                status=status,
                reviewer=str(reviewer_id)
            )
            return HITLRequest(**result.data[0])
        
    except Exception as e:
        logger.error(
            "Failed to review HITL request",
            request_id=str(request_id),
            error=str(e)
        )
    
    return None


async def resume_after_hitl(request_id: UUID) -> Optional[dict[str, Any]]:
    """
    Resume graph execution after HITL approval.
    
    Args:
        request_id: The approved HITL request ID
        
    Returns:
        Execution result or None
    """
    client = get_supabase_admin_client()
    
    # Get the HITL request
    result = client.table("hitl_requests").select("*").eq(
        "id", str(request_id)
    ).single().execute()
    
    if not result.data:
        logger.error("HITL request not found", request_id=str(request_id))
        return None
    
    request = result.data
    
    if request["status"] != "approved":
        logger.warning("HITL request not approved", request_id=str(request_id))
        return {"error": "Request not approved", "status": request["status"]}
    
    # Resume the graph execution
    # This would normally restore state and continue the graph
    # For now, return the proposed action
    return {
        "resumed": True,
        "run_id": request["run_id"],
        "proposed_action": request["proposed_action"]
    }
