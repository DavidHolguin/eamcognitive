"""
TIC Agent - Infraestructura y Sistemas
⚙️ Arquitecto de Sistemas
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
TIC_AGENT_ID = "09037548-2f4f-4c06-b762-ec5582045508"


class TICAgent(BaseAgentNode):
    """
    Agente TIC - Infraestructura y soporte tecnológico.
    
    Responsabilidades:
    - Monitoreo de sistemas
    - Diagnóstico de errores
    - Integraciones de sistemas
    - Mantenimiento de SIGEAM
    - Soporte técnico
    """
    
    def __init__(self, agent_config: Agent):
        super().__init__(AgentSlot.TIC, agent_config)
    
    def get_tools(self) -> list[BaseTool]:
        """Get tools for TIC agent."""
        # Placeholder tools
        return []


async def get_tic_agent() -> TICAgent:
    """Load TIC agent from database."""
    client = get_supabase_admin_client()
    result = client.table("agents").select("*").eq("id", TIC_AGENT_ID).single().execute()
    
    if not result.data:
        raise ValueError(f"TIC agent not found: {TIC_AGENT_ID}")
    
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
    
    return TICAgent(config)


async def process_tic(state: CognitiveState) -> dict[str, Any]:
    """Process function for LangGraph node."""
    try:
        agent = await get_tic_agent()
        return await agent.process(state)
    except Exception as e:
        logger.error("Failed to process tic", error=str(e))
        state.log_error(f"Error en TIC: {str(e)}", AgentSlot.TIC)
        return {
            "error": str(e),
            "is_complete": True,
            "brain_log": state.brain_log
        }
