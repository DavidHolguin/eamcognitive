"""
WebSocket Handler - Real-time streaming for GenUI and brain log
"""

from typing import Any, Optional
from uuid import UUID
import json

import structlog
from fastapi import APIRouter, WebSocket, WebSocketDisconnect, Depends, Query
from starlette.websockets import WebSocketState

from app.config import get_settings
from app.db.supabase import get_supabase_client
from app.core.state import CognitiveState, GenUIPayload

logger = structlog.get_logger(__name__)

router = APIRouter(tags=["WebSocket"])


class ConnectionManager:
    """Manages WebSocket connections."""
    
    def __init__(self):
        self.active_connections: dict[str, list[WebSocket]] = {}
    
    async def connect(self, websocket: WebSocket, conversation_id: str):
        """Accept and store a new connection."""
        await websocket.accept()
        if conversation_id not in self.active_connections:
            self.active_connections[conversation_id] = []
        self.active_connections[conversation_id].append(websocket)
        logger.info(
            "WebSocket connected",
            conversation_id=conversation_id,
            total_connections=len(self.active_connections[conversation_id])
        )
    
    def disconnect(self, websocket: WebSocket, conversation_id: str):
        """Remove a connection."""
        if conversation_id in self.active_connections:
            try:
                self.active_connections[conversation_id].remove(websocket)
                if not self.active_connections[conversation_id]:
                    del self.active_connections[conversation_id]
            except ValueError:
                pass
        logger.info("WebSocket disconnected", conversation_id=conversation_id)
    
    async def send_to_conversation(self, conversation_id: str, message: dict[str, Any]):
        """Send a message to all connections for a conversation."""
        if conversation_id not in self.active_connections:
            return
        
        disconnected = []
        for connection in self.active_connections[conversation_id]:
            try:
                if connection.client_state == WebSocketState.CONNECTED:
                    await connection.send_json(message)
            except Exception as e:
                logger.warning("Failed to send WebSocket message", error=str(e))
                disconnected.append(connection)
        
        # Clean up disconnected
        for conn in disconnected:
            self.disconnect(conn, conversation_id)
    
    async def broadcast_genui(self, conversation_id: str, payload: GenUIPayload):
        """Broadcast a GenUI payload to all listeners."""
        await self.send_to_conversation(conversation_id, {
            "type": "genui",
            "payload": payload.model_dump()
        })
    
    async def broadcast_thinking(self, conversation_id: str, content: str, agent: Optional[str] = None):
        """Broadcast a thinking step."""
        await self.send_to_conversation(conversation_id, {
            "type": "thinking",
            "content": content,
            "agent": agent
        })
    
    async def broadcast_response(self, conversation_id: str, response: str, is_final: bool = False):
        """Broadcast a response (partial or final)."""
        await self.send_to_conversation(conversation_id, {
            "type": "response" if is_final else "partial_response",
            "content": response
        })


# Global connection manager
manager = ConnectionManager()


@router.websocket("/ws/{conversation_id}")
async def websocket_endpoint(
    websocket: WebSocket,
    conversation_id: str,
    token: Optional[str] = Query(None)
):
    """
    WebSocket endpoint for real-time updates.
    
    Message types from server:
    - thinking: Agent thinking steps
    - genui: UI component payloads
    - partial_response: Streaming text
    - response: Final response
    - error: Error occurred
    
    Message types to server:
    - ping: Keep-alive
    - subscribe: Subscribe to additional events
    """
    # Validate token (simplified - in production, validate JWT)
    if not token:
        await websocket.close(code=4001, reason="Authentication required")
        return
    
    await manager.connect(websocket, conversation_id)
    
    try:
        while True:
            data = await websocket.receive_text()
            
            try:
                message = json.loads(data)
                msg_type = message.get("type", "")
                
                if msg_type == "ping":
                    await websocket.send_json({"type": "pong"})
                
                elif msg_type == "subscribe":
                    # Additional subscription handling
                    event_types = message.get("events", [])
                    logger.debug(
                        "Subscription updated",
                        conversation_id=conversation_id,
                        events=event_types
                    )
                
                else:
                    logger.warning(
                        "Unknown WebSocket message type",
                        msg_type=msg_type
                    )
                    
            except json.JSONDecodeError:
                await websocket.send_json({
                    "type": "error",
                    "message": "Invalid JSON"
                })
                
    except WebSocketDisconnect:
        manager.disconnect(websocket, conversation_id)
    except Exception as e:
        logger.error("WebSocket error", error=str(e))
        manager.disconnect(websocket, conversation_id)


def get_connection_manager() -> ConnectionManager:
    """Get the global connection manager."""
    return manager
