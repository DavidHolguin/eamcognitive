"""
Comunicaciones Agent - Contenido Institucional
✍️ Estratega de Contenido
"""

from typing import Any
from uuid import UUID

import structlog
from langchain_core.tools import BaseTool

from app.core.state import CognitiveState, AgentSlot
from app.agents.base import BaseAgentNode
from app.db.models import Agent
from app.db.supabase import get_supabase_admin_client

logger = structlog.get_logger(__name__)

# Agent ID from database
COMUNICACIONES_AGENT_ID = "de679eac-d3ec-4889-b506-9c05c2ba5e4d"


class ComunicacionesAgent(BaseAgentNode):
    """
    Agente de Comunicaciones - Contenido y comunicados oficiales.
    
    Responsabilidades:
    - Redacción de circulares
    - Comunicados institucionales
    - Gestión de redes sociales
    - Análisis de engagement
    - Contenido para la comunidad
    """
    
    def __init__(self, agent_config: Agent):
        super().__init__(AgentSlot.COMUNICACIONES, agent_config)
    
    def get_tools(self) -> list[BaseTool]:
        """Get tools for Comunicaciones agent."""
        # Placeholder tools
        return []


async def get_comunicaciones_agent() -> ComunicacionesAgent:
    """Load Comunicaciones agent from database."""
    client = get_supabase_admin_client()
    result = client.table("agents").select("*").eq("id", COMUNICACIONES_AGENT_ID).single().execute()
    
    if not result.data:
        raise ValueError(f"Comunicaciones agent not found: {COMUNICACIONES_AGENT_ID}")
    
    agent_data = result.data
    config = Agent(
        id=agent_data["id"],
        name=agent_data["name"],
        role=agent_data["role"],
        avatar=agent_data["avatar"],
        status=agent_data["status"],
        department=agent_data["department"],
        specialization=agent_data["specialization"],
        goal=agent_data["goal"],
        tools=agent_data.get("tools", []),
        system_prompt=agent_data.get("system_prompt"),
        model_config_data=agent_data.get("model_config"),
        is_active=agent_data.get("is_active", True),
        created_at=agent_data["created_at"],
        updated_at=agent_data["updated_at"]
    )
    
    return ComunicacionesAgent(config)


async def process_comunicaciones(state: CognitiveState) -> dict[str, Any]:
    """Process function for LangGraph node."""
    try:
        agent = await get_comunicaciones_agent()
        return await agent.process(state)
    except Exception as e:
        logger.error("Failed to process comunicaciones", error=str(e))
        state.log_error(f"Error en Comunicaciones: {str(e)}", AgentSlot.COMUNICACIONES)
        return {
            "error": str(e),
            "is_complete": True,
            "brain_log": state.brain_log
        }
