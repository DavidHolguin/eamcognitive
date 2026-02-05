"""
Agents API Routes - Agent management and information
"""

from typing import Any, Optional
from uuid import UUID

import structlog
from fastapi import APIRouter, Depends, HTTPException

from app.db.supabase import get_supabase_admin_client
from app.db.models import Agent, AgentStatus
from app.security.zero_trust import require_auth

logger = structlog.get_logger(__name__)

router = APIRouter(prefix="/agents", tags=["Agents"])


@router.get("")
async def list_agents(
    active_only: bool = True,
    user = Depends(require_auth())
) -> list[dict[str, Any]]:
    """Get all available agents."""
    client = get_supabase_admin_client()
    
    query = client.table("agents").select("*")
    if active_only:
        query = query.eq("is_active", True)
    
    result = query.order("name").execute()
    
    return result.data or []


@router.get("/{agent_id}")
async def get_agent(
    agent_id: UUID,
    user = Depends(require_auth())
) -> dict[str, Any]:
    """Get a specific agent by ID."""
    client = get_supabase_admin_client()
    
    result = client.table("agents").select("*").eq("id", str(agent_id)).single().execute()
    
    if not result.data:
        raise HTTPException(status_code=404, detail="Agente no encontrado")
    
    return result.data


@router.get("/{agent_id}/runs")
async def get_agent_runs(
    agent_id: UUID,
    limit: int = 20,
    status: Optional[str] = None,
    user = Depends(require_auth())
) -> dict[str, Any]:
    """Get execution runs for a specific agent."""
    client = get_supabase_admin_client()
    
    query = client.table("agent_runs").select("*").eq("agent_id", str(agent_id))
    
    if status:
        query = query.eq("status", status)
    
    result = query.order("created_at", desc=True).limit(limit).execute()
    
    return {
        "agent_id": agent_id,
        "runs": result.data or [],
        "total": len(result.data) if result.data else 0
    }


@router.get("/{agent_id}/stats")
async def get_agent_stats(
    agent_id: UUID,
    user = Depends(require_auth())
) -> dict[str, Any]:
    """Get statistics for a specific agent."""
    client = get_supabase_admin_client()
    
    # Get all runs for this agent
    runs_result = client.table("agent_runs").select(
        "status, started_at, completed_at"
    ).eq("agent_id", str(agent_id)).execute()
    
    runs = runs_result.data or []
    
    # Calculate stats
    total = len(runs)
    completed = sum(1 for r in runs if r["status"] == "completed")
    failed = sum(1 for r in runs if r["status"] == "failed")
    
    # Calculate average duration for completed runs
    durations = []
    for r in runs:
        if r["completed_at"] and r["started_at"]:
            from datetime import datetime
            start = datetime.fromisoformat(r["started_at"].replace("Z", "+00:00"))
            end = datetime.fromisoformat(r["completed_at"].replace("Z", "+00:00"))
            durations.append((end - start).total_seconds() * 1000)
    
    avg_duration = sum(durations) / len(durations) if durations else 0
    
    return {
        "agent_id": agent_id,
        "stats": {
            "total_runs": total,
            "completed": completed,
            "failed": failed,
            "success_rate": f"{(completed / total * 100):.1f}%" if total > 0 else "N/A",
            "average_duration_ms": int(avg_duration)
        }
    }


@router.patch("/{agent_id}/status")
async def update_agent_status(
    agent_id: UUID,
    status: AgentStatus,
    user = Depends(require_auth())
) -> dict[str, Any]:
    """Update an agent's status."""
    client = get_supabase_admin_client()
    
    result = client.table("agents").update({
        "status": status.value
    }).eq("id", str(agent_id)).execute()
    
    if not result.data:
        raise HTTPException(status_code=404, detail="Agente no encontrado")
    
    logger.info(
        "Agent status updated",
        agent_id=str(agent_id),
        new_status=status.value
    )
    
    return result.data[0]
