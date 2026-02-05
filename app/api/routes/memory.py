"""
Memory API Routes - Long-term memory management
"""

from typing import Any, Optional
from uuid import UUID

import structlog
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from app.db.supabase import get_supabase_admin_client
from app.db.models import MemoryType, MemoryCreate
from app.security.zero_trust import require_auth

logger = structlog.get_logger(__name__)

router = APIRouter(prefix="/memory", tags=["Memory"])


class MemorySearchRequest(BaseModel):
    """Memory search request."""
    query: str
    limit: int = Field(default=10, le=50)
    memory_type: Optional[MemoryType] = None
    agent_id: Optional[UUID] = None


@router.post("/search")
async def search_memories(
    request: MemorySearchRequest,
    user = Depends(require_auth())
) -> dict[str, Any]:
    """Search long-term memory."""
    client = get_supabase_admin_client()
    
    # Simple text search (vector search would use embeddings)
    query = client.table("memories").select("*").ilike(
        "content", f"%{request.query}%"
    )
    
    if request.memory_type:
        query = query.eq("memory_type", request.memory_type.value)
    
    if request.agent_id:
        query = query.eq("agent_id", str(request.agent_id))
    
    result = query.limit(request.limit).execute()
    
    return {
        "query": request.query,
        "results": result.data or [],
        "total": len(result.data) if result.data else 0
    }


@router.post("")
async def create_memory(
    memory: MemoryCreate,
    user = Depends(require_auth())
) -> dict[str, Any]:
    """Create a new memory entry."""
    client = get_supabase_admin_client()
    
    memory_data = {
        "agent_id": str(memory.agent_id) if memory.agent_id else None,
        "content": memory.content,
        "memory_type": memory.memory_type.value,
        "importance": memory.importance,
        "metadata": memory.metadata
    }
    
    # TODO: Generate embedding for vector search
    # memory_data["embedding"] = await generate_embedding(memory.content)
    
    result = client.table("memories").insert(memory_data).execute()
    
    if not result.data:
        raise HTTPException(status_code=500, detail="Error creando memoria")
    
    logger.info(
        "Memory created",
        memory_id=result.data[0]["id"],
        memory_type=memory.memory_type.value
    )
    
    return result.data[0]


@router.get("/{memory_id}")
async def get_memory(
    memory_id: UUID,
    user = Depends(require_auth())
) -> dict[str, Any]:
    """Get a specific memory entry."""
    client = get_supabase_admin_client()
    
    result = client.table("memories").select("*").eq(
        "id", str(memory_id)
    ).single().execute()
    
    if not result.data:
        raise HTTPException(status_code=404, detail="Memoria no encontrada")
    
    # Update access tracking
    client.table("memories").update({
        "access_count": result.data["access_count"] + 1,
        "last_accessed": "now()"
    }).eq("id", str(memory_id)).execute()
    
    return result.data


@router.delete("/{memory_id}")
async def delete_memory(
    memory_id: UUID,
    user = Depends(require_auth())
) -> dict[str, Any]:
    """Delete a memory entry."""
    client = get_supabase_admin_client()
    
    result = client.table("memories").delete().eq(
        "id", str(memory_id)
    ).execute()
    
    if not result.data:
        raise HTTPException(status_code=404, detail="Memoria no encontrada")
    
    logger.info("Memory deleted", memory_id=str(memory_id))
    
    return {"deleted": True, "memory_id": memory_id}
