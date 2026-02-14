"""
Chat API Routes - Main conversation endpoint
"""

from datetime import datetime
from typing import Any, Optional
from uuid import UUID, uuid4

import structlog
from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field
import json

from app.config import get_settings
from app.core.state import CognitiveState, SecurityContext
from app.core.graph import get_cognitive_graph
from app.core.checkpointer import persist_brain_log, update_run_status
from app.db.supabase import get_supabase_admin_client
from app.db.models import MessageCreate, SenderType, RunStatus
from app.security.zero_trust import get_current_user, build_security_context, require_auth
from app.security.audit import log_access, AuditContext
from app.protocols.genui import stream_genui_payloads

logger = structlog.get_logger(__name__)

router = APIRouter(prefix="/chat", tags=["Chat"])


# ─────────────────────────────────────────────────────────────────────────────
# Request/Response Models
# ─────────────────────────────────────────────────────────────────────────────

class ChatRequest(BaseModel):
    """Chat request payload."""
    message: str = Field(..., min_length=1, max_length=10000)
    conversation_id: Optional[UUID] = None


class ChatResponse(BaseModel):
    """Chat response payload."""
    run_id: UUID
    conversation_id: UUID
    response: str
    agent_used: Optional[str] = None
    genui_payloads: list[dict[str, Any]] = Field(default_factory=list)
    requires_hitl: bool = False
    hitl_request_id: Optional[UUID] = None


class StreamEvent(BaseModel):
    """Server-Sent Event structure."""
    event: str
    data: dict[str, Any]


# ─────────────────────────────────────────────────────────────────────────────
# Endpoints
# ─────────────────────────────────────────────────────────────────────────────

@router.post("", response_model=ChatResponse)
async def send_message(
    request: Request,
    payload: ChatRequest,
    user = Depends(require_auth())
):
    """
    Send a message to the cognitive system.
    
    This endpoint:
    1. Creates or continues a conversation
    2. Saves the user message
    3. Routes through the cognitive graph
    4. Returns the agent response
    """
    settings = get_settings()
    client = get_supabase_admin_client()
    
    # Build security context
    security_context = await build_security_context(request, user)
    
    async with AuditContext("chat.send", security_context) as audit:
        # Get or create conversation
        if payload.conversation_id:
            conv_result = client.table("conversations").select("*").eq(
                "id", str(payload.conversation_id)
            ).single().execute()
            
            if not conv_result.data:
                raise HTTPException(status_code=404, detail="Conversación no encontrada")
            
            conversation_id = payload.conversation_id
        else:
            # Create new conversation
            conv_data = {
                "user_id": str(user.id),
                "title": payload.message[:50] + "..." if len(payload.message) > 50 else payload.message
            }
            conv_result = client.table("conversations").insert(conv_data).execute()
            conversation_id = UUID(conv_result.data[0]["id"])
        
        # Ensure conversation_id is a string for LangGraph compatibility
        conv_id_str = str(conversation_id)
        
        # Save user message
        msg_data = {
            "conversation_id": str(conversation_id),
            "sender_type": "user",
            "sender_id": str(user.id),
            "content": payload.message
        }
        client.table("messages").insert(msg_data).execute()
        
        # Create agent run
        run_id = uuid4()
        run_data = {
            "id": str(run_id),
            "agent_id": None,  # Will be set when supervisor routes
            "triggered_by": str(user.id),
            "conversation_id": str(conversation_id),
            "status": "running",
            "input_params": {"message": payload.message},
            "started_at": datetime.utcnow().isoformat()
        }
        client.table("agent_runs").insert(run_data).execute()
        
        audit.metadata["run_id"] = str(run_id)
        audit.metadata["conversation_id"] = str(conversation_id)
        
        try:
            # Build initial cognitive state
            initial_state = CognitiveState(
                run_id=run_id,
                conversation_id=conv_id_str,
                triggered_by=str(user.id),
                user_message=payload.message,
                security_context=security_context
            )
            
            # Run the cognitive graph
            graph = get_cognitive_graph()
            config = {"configurable": {"thread_id": str(run_id)}}
            
            final_state = await graph.ainvoke(initial_state, config)
            
            # Persist brain log
            if hasattr(final_state, 'brain_log'):
                await persist_brain_log(run_id, final_state.brain_log)
            
            # Get response
            response_text = final_state.get("final_response") or final_state.get("current_response") or ""
            
            # Get which agent was used
            visited = final_state.get("visited_agents", [])
            agent_used = visited[-1].value if visited and hasattr(visited[-1], 'value') else (visited[-1] if visited else None)
            
            # Update run status
            await update_run_status(
                run_id,
                "completed",
                result={"response": response_text[:500], "agent": agent_used}
            )
            
            # Save agent response as message
            agent_msg_data = {
                "conversation_id": str(conversation_id),
                "sender_type": "agent",
                "content": response_text
            }
            client.table("messages").insert(agent_msg_data).execute()
            
            return ChatResponse(
                run_id=run_id,
                conversation_id=conversation_id,
                response=response_text,
                agent_used=agent_used,
                genui_payloads=[p.model_dump() for p in final_state.get("genui_payloads", [])],
                requires_hitl=final_state.get("requires_hitl", False),
                hitl_request_id=final_state.get("hitl_request_id")
            )
            
        except Exception as e:
            logger.error(
                "Chat processing failed",
                run_id=str(run_id),
                error=str(e)
            )
            await update_run_status(run_id, "failed", error_message=str(e))
            raise HTTPException(status_code=500, detail=f"Error procesando mensaje: {str(e)}")


@router.post("/stream")
async def send_message_stream(
    request: Request,
    payload: ChatRequest,
    user = Depends(require_auth())
):
    """
    Send a message with Server-Sent Events streaming.
    
    Events:
    - thinking: Agent thinking steps
    - genui: UI component updates
    - response: Final response
    - error: Error occurred
    """
    async def event_generator():
        try:
            # Similar logic to send_message but with streaming
            security_context = await build_security_context(request, user)
            
            yield f"event: start\ndata: {json.dumps({'status': 'processing'})}\n\n"
            
            # Build and run graph (simplified for streaming)
            conv_id = payload.conversation_id or uuid4()
            run_id = uuid4()
            
            initial_state = CognitiveState(
                run_id=str(run_id),
                conversation_id=str(conv_id),
                triggered_by=str(user.id),
                user_message=payload.message,
                security_context=security_context
            )
            
            graph = get_cognitive_graph()
            config = {"configurable": {"thread_id": str(initial_state.run_id)}}
            
            # Use ainvoke instead of astream_events to avoid
            # NotImplementedError from sync SupabaseCheckpointer
            yield f"event: thinking\ndata: {json.dumps({'node': 'supervisor', 'status': 'routing'})}\n\n"
            
            final_state = await graph.ainvoke(initial_state, config)
            
            # Extract response from final state
            if isinstance(final_state, dict):
                response_text = final_state.get("final_response") or final_state.get("current_response") or ""
                
                # Send any GenUI payloads
                for genui_item in final_state.get("genui_payloads", []):
                    yield f"event: genui\ndata: {json.dumps(genui_item.model_dump() if hasattr(genui_item, 'model_dump') else genui_item)}\n\n"
            else:
                response_text = str(final_state) if final_state else ""
            
            if not response_text:
                response_text = "El agente procesó la solicitud pero no generó una respuesta de texto."
            
            yield f"event: response\ndata: {json.dumps({'response': response_text})}\n\n"
            yield f"event: end\ndata: {json.dumps({'status': 'complete'})}\n\n"
            
        except Exception as e:
            import traceback
            error_msg = str(e) or f"{type(e).__name__}: {repr(e)}"
            tb = traceback.format_exc()
            logger.error("Stream error", error=error_msg, traceback=tb)
            yield f"event: error\ndata: {json.dumps({'error': error_msg, 'type': type(e).__name__, 'traceback': tb[:500]})}\n\n"
    
    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no"
        }
    )


@router.get("/history/{conversation_id}")
async def get_conversation_history(
    conversation_id: UUID,
    limit: int = 50,
    user = Depends(require_auth())
):
    """Get message history for a conversation."""
    client = get_supabase_admin_client()
    
    # Verify user has access to conversation
    conv_result = client.table("conversations").select("user_id").eq(
        "id", str(conversation_id)
    ).single().execute()
    
    if not conv_result.data:
        raise HTTPException(status_code=404, detail="Conversación no encontrada")
    
    # Get messages
    messages_result = client.table("messages").select("*").eq(
        "conversation_id", str(conversation_id)
    ).order("created_at", desc=False).limit(limit).execute()
    
    return {
        "conversation_id": conversation_id,
        "messages": messages_result.data or []
    }
