"""
Supabase Checkpointer for LangGraph
Persists graph state to Supabase for durability and recovery.
"""

from datetime import datetime
from typing import Any, Optional, Sequence
from uuid import UUID
import json

import structlog
from langgraph.checkpoint.base import (
    BaseCheckpointSaver,
    Checkpoint,
    CheckpointMetadata,
    CheckpointTuple,
)
from pydantic import BaseModel

from app.db.supabase import get_supabase_admin_client
from app.core.state import CognitiveState, BrainLogEntry

logger = structlog.get_logger(__name__)


class SupabaseCheckpointer(BaseCheckpointSaver):
    """
    LangGraph checkpointer that persists state to Supabase.
    
    Uses the agent_runs table for run metadata and a checkpoints
    table for the actual graph state snapshots.
    """
    
    def __init__(self):
        super().__init__()
        self._client = get_supabase_admin_client()
    
    def get_tuple(self, config: dict[str, Any]) -> Optional[CheckpointTuple]:
        """Get the latest checkpoint for a thread."""
        thread_id = config.get("configurable", {}).get("thread_id")
        if not thread_id:
            return None
        
        try:
            result = self._client.table("graph_checkpoints").select("*").eq(
                "thread_id", str(thread_id)
            ).order(
                "checkpoint_id", desc=True
            ).limit(1).execute()
            
            if not result.data:
                return None
            
            row = result.data[0]
            checkpoint = Checkpoint(
                v=row.get("v", 1),
                id=row["checkpoint_id"],
                ts=row.get("ts", datetime.utcnow().isoformat()),
                channel_values=json.loads(row.get("channel_values", "{}")),
                channel_versions=json.loads(row.get("channel_versions", "{}")),
                versions_seen=json.loads(row.get("versions_seen", "{}")),
                pending_sends=json.loads(row.get("pending_sends", "[]")),
            )
            
            metadata = CheckpointMetadata(
                source=row.get("source", "unknown"),
                step=row.get("step", 0),
                writes=json.loads(row.get("writes", "{}")),
            )
            
            return CheckpointTuple(
                config=config,
                checkpoint=checkpoint,
                metadata=metadata,
                parent_config=None
            )
            
        except Exception as e:
            logger.error("Failed to get checkpoint", thread_id=thread_id, error=str(e))
            return None
    
    def list(
        self,
        config: Optional[dict[str, Any]],
        *,
        filter: Optional[dict[str, Any]] = None,
        before: Optional[dict[str, Any]] = None,
        limit: Optional[int] = None,
    ) -> list[CheckpointTuple]:
        """List checkpoints for a thread."""
        if not config:
            return []
        
        thread_id = config.get("configurable", {}).get("thread_id")
        if not thread_id:
            return []
        
        try:
            query = self._client.table("graph_checkpoints").select("*").eq(
                "thread_id", str(thread_id)
            ).order("checkpoint_id", desc=True)
            
            if limit:
                query = query.limit(limit)
            
            result = query.execute()
            
            checkpoints = []
            for row in result.data:
                checkpoint = Checkpoint(
                    v=row.get("v", 1),
                    id=row["checkpoint_id"],
                    ts=row.get("ts", datetime.utcnow().isoformat()),
                    channel_values=json.loads(row.get("channel_values", "{}")),
                    channel_versions=json.loads(row.get("channel_versions", "{}")),
                    versions_seen=json.loads(row.get("versions_seen", "{}")),
                    pending_sends=json.loads(row.get("pending_sends", "[]")),
                )
                
                metadata = CheckpointMetadata(
                    source=row.get("source", "unknown"),
                    step=row.get("step", 0),
                    writes=json.loads(row.get("writes", "{}")),
                )
                
                checkpoints.append(CheckpointTuple(
                    config=config,
                    checkpoint=checkpoint,
                    metadata=metadata,
                    parent_config=None
                ))
            
            return checkpoints
            
        except Exception as e:
            logger.error("Failed to list checkpoints", thread_id=thread_id, error=str(e))
            return []
    
    def put(
        self,
        config: dict[str, Any],
        checkpoint: Checkpoint,
        metadata: CheckpointMetadata,
        new_versions: dict[str, Any],
    ) -> dict[str, Any]:
        """Save a checkpoint."""
        thread_id = config.get("configurable", {}).get("thread_id")
        if not thread_id:
            raise ValueError("thread_id required in config")
        
        try:
            row = {
                "thread_id": str(thread_id),
                "checkpoint_id": checkpoint["id"],
                "v": checkpoint.get("v", 1),
                "ts": checkpoint.get("ts", datetime.utcnow().isoformat()),
                "channel_values": json.dumps(checkpoint.get("channel_values", {})),
                "channel_versions": json.dumps(checkpoint.get("channel_versions", {})),
                "versions_seen": json.dumps(checkpoint.get("versions_seen", {})),
                "pending_sends": json.dumps(checkpoint.get("pending_sends", [])),
                "source": metadata.get("source", "unknown"),
                "step": metadata.get("step", 0),
                "writes": json.dumps(metadata.get("writes", {})),
            }
            
            self._client.table("graph_checkpoints").upsert(row).execute()
            
            logger.debug(
                "Checkpoint saved",
                thread_id=thread_id,
                checkpoint_id=checkpoint["id"]
            )
            
            return config
            
        except Exception as e:
            logger.error("Failed to save checkpoint", thread_id=thread_id, error=str(e))
            raise
    
    def put_writes(
        self,
        config: dict[str, Any],
        writes: Sequence[tuple[str, Any]],
        task_id: str,
    ) -> None:
        """Save intermediate writes (for streaming)."""
        # For now, we don't persist intermediate writes
        # This could be extended to support resumable streams
        pass


# ─────────────────────────────────────────────────────────────────────────────
# Brain Log Persistence
# ─────────────────────────────────────────────────────────────────────────────

async def persist_brain_log(run_id: UUID, entries: list[BrainLogEntry]) -> None:
    """
    Persist brain log entries to Supabase.
    Called after each agent step completes.
    """
    if not entries:
        return
    
    client = get_supabase_admin_client()
    
    rows = []
    for entry in entries:
        rows.append({
            "run_id": str(run_id),
            "step_type": entry.step_type.value if hasattr(entry.step_type, 'value') else entry.step_type,
            "content": entry.content,
            "tool_name": entry.tool_name,
            "tool_input": entry.tool_input,
            "tool_output": entry.tool_output if not callable(entry.tool_output) else str(entry.tool_output),
            "tokens_used": entry.tokens_used,
            "duration_ms": entry.duration_ms,
            "created_at": entry.timestamp.isoformat()
        })
    
    try:
        client.table("brain_log").insert(rows).execute()
        logger.debug(
            "Brain log persisted",
            run_id=str(run_id),
            entries=len(rows)
        )
    except Exception as e:
        logger.error(
            "Failed to persist brain log",
            run_id=str(run_id),
            error=str(e)
        )


async def update_run_status(
    run_id: UUID,
    status: str,
    result: Optional[dict[str, Any]] = None,
    error_message: Optional[str] = None
) -> None:
    """Update an agent run's status in the database."""
    client = get_supabase_admin_client()
    
    update_data = {
        "status": status,
        "completed_at": datetime.utcnow().isoformat() if status in ("completed", "failed") else None
    }
    
    if result:
        update_data["result"] = result
    if error_message:
        update_data["error_message"] = error_message
    
    try:
        client.table("agent_runs").update(update_data).eq("id", str(run_id)).execute()
        logger.info("Run status updated", run_id=str(run_id), status=status)
    except Exception as e:
        logger.error("Failed to update run status", run_id=str(run_id), error=str(e))
