"""
Runs API Routes - Agent execution tracking
"""

from typing import Any, Optional
from uuid import UUID

import structlog
from fastapi import APIRouter, Depends, HTTPException

from app.db.supabase import get_supabase_admin_client
from app.security.zero_trust import require_auth

logger = structlog.get_logger(__name__)

router = APIRouter(prefix="/runs", tags=["Runs"])


@router.get("")
async def list_runs(
    limit: int = 20,
    status: Optional[str] = None,
    user = Depends(require_auth())
) -> list[dict[str, Any]]:
    """Get recent agent runs."""
    client = get_supabase_admin_client()
    
    query = client.table("agent_runs").select(
        "*, agents(name, avatar)"
    )
    
    if status:
        query = query.eq("status", status)
    
    result = query.order("created_at", desc=True).limit(limit).execute()
    
    return result.data or []


@router.get("/{run_id}")
async def get_run(
    run_id: UUID,
    user = Depends(require_auth())
) -> dict[str, Any]:
    """Get a specific run by ID."""
    client = get_supabase_admin_client()
    
    result = client.table("agent_runs").select(
        "*, agents(name, avatar, department)"
    ).eq("id", str(run_id)).single().execute()
    
    if not result.data:
        raise HTTPException(status_code=404, detail="Ejecución no encontrada")
    
    return result.data


@router.get("/{run_id}/brain-log")
async def get_run_brain_log(
    run_id: UUID,
    user = Depends(require_auth())
) -> dict[str, Any]:
    """Get the brain log (thinking steps) for a run."""
    client = get_supabase_admin_client()
    
    result = client.table("brain_log").select("*").eq(
        "run_id", str(run_id)
    ).order("created_at").execute()
    
    return {
        "run_id": run_id,
        "entries": result.data or [],
        "total": len(result.data) if result.data else 0
    }


@router.post("/{run_id}/cancel")
async def cancel_run(
    run_id: UUID,
    user = Depends(require_auth())
) -> dict[str, Any]:
    """Cancel a running execution."""
    client = get_supabase_admin_client()
    
    # Check current status
    check_result = client.table("agent_runs").select("status").eq(
        "id", str(run_id)
    ).single().execute()
    
    if not check_result.data:
        raise HTTPException(status_code=404, detail="Ejecución no encontrada")
    
    current_status = check_result.data["status"]
    
    if current_status not in ["queued", "running"]:
        raise HTTPException(
            status_code=400,
            detail=f"No se puede cancelar una ejecución con estado: {current_status}"
        )
    
    # Update status
    from datetime import datetime
    result = client.table("agent_runs").update({
        "status": "cancelled",
        "completed_at": datetime.utcnow().isoformat()
    }).eq("id", str(run_id)).execute()
    
    logger.info("Run cancelled", run_id=str(run_id))
    
    return {
        "run_id": run_id,
        "status": "cancelled",
        "message": "Ejecución cancelada exitosamente"
    }
