"""
Finanzas Agent - Cartera Estudiantil y SNIES
💰 Contador Cognitivo
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
FINANZAS_AGENT_ID = "2ee09831-3ca7-4c7b-b946-fcfec1135b38"


class FinanzasAgent(BaseAgentNode):
    """
    Agente de Finanzas - Cartera estudiantil, facturación y SNIES.
    
    Responsabilidades:
    - Gestión de cartera estudiantil
    - Análisis de morosidad
    - Generación de facturas
    - Reportes SNIES
    - Análisis presupuestal
    """
    
    def __init__(self, agent_config: Agent):
        super().__init__(AgentSlot.FINANZAS, agent_config)
    
    def get_tools(self) -> list[BaseTool]:
        """Get tools for Finanzas agent."""
        from app.tools.cartera import (
            ConsultarCarteraTool,
            AnalizarMorosidadTool,
            GenerarFacturaTool,
        )
        from app.tools.snies import GenerarReporteSNIESTool
        
        return [
            ConsultarCarteraTool(),
            AnalizarMorosidadTool(),
            GenerarFacturaTool(),
            GenerarReporteSNIESTool(),
        ]


async def get_finanzas_agent() -> FinanzasAgent:
    """Load Finanzas agent from database."""
    client = get_supabase_admin_client()
    result = client.table("agents").select("*").eq("id", FINANZAS_AGENT_ID).single().execute()
    
    if not result.data:
        raise ValueError(f"Finanzas agent not found: {FINANZAS_AGENT_ID}")
    
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
    
    return FinanzasAgent(config)


async def process_finanzas(state: CognitiveState) -> dict[str, Any]:
    """Process function for LangGraph node."""
    try:
        agent = await get_finanzas_agent()
        return await agent.process(state)
    except Exception as e:
        logger.error("Failed to process finanzas", error=str(e))
        state.log_error(f"Error en Finanzas: {str(e)}", AgentSlot.FINANZAS)
        return {
            "error": str(e),
            "is_complete": True,
            "brain_log": state.brain_log
        }
