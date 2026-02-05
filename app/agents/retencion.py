"""
Retención Agent - Alertas de Deserción y BI
📊 Científico de Datos
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
RETENCION_AGENT_ID = "4eede45a-d0e3-4e51-9219-46b1a1f1688b"


class RetencionAgent(BaseAgentNode):
    """
    Agente de Retención - Alertas tempranas y análisis de permanencia.
    
    Responsabilidades:
    - Predicción de riesgo de deserción
    - Análisis de cohortes
    - Generación de alertas tempranas
    - Business Intelligence estudiantil
    - Estrategias de retención
    """
    
    def __init__(self, agent_config: Agent):
        super().__init__(AgentSlot.RETENCION, agent_config)
    
    def get_tools(self) -> list[BaseTool]:
        """Get tools for Retención agent."""
        # Placeholder tools - will be implemented in tools/retencion.py
        return []


async def get_retencion_agent() -> RetencionAgent:
    """Load Retención agent from database."""
    client = get_supabase_admin_client()
    result = client.table("agents").select("*").eq("id", RETENCION_AGENT_ID).single().execute()
    
    if not result.data:
        raise ValueError(f"Retención agent not found: {RETENCION_AGENT_ID}")
    
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
    
    return RetencionAgent(config)


async def process_retencion(state: CognitiveState) -> dict[str, Any]:
    """Process function for LangGraph node."""
    try:
        agent = await get_retencion_agent()
        return await agent.process(state)
    except Exception as e:
        logger.error("Failed to process retencion", error=str(e))
        state.log_error(f"Error en Retención: {str(e)}", AgentSlot.RETENCION)
        return {
            "error": str(e),
            "is_complete": True,
            "brain_log": state.brain_log
        }
