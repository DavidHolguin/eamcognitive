"""
Admisiones Agent - Gestión de Matrículas y SIGEAM
🎓 Analista de Inscripciones
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
ADMISIONES_AGENT_ID = "858a631f-4ea3-4189-9474-8c8974494f65"


class AdmisionesAgent(BaseAgentNode):
    """
    Agente de Admisiones - Gestión de matrículas, cohortes y SIGEAM.
    
    Responsabilidades:
    - Consultas al sistema SIGEAM
    - Proyecciones de cohortes estudiantiles
    - Procesos de inscripción
    - Reportes de matrícula
    """
    
    def __init__(self, agent_config: Agent):
        super().__init__(AgentSlot.ADMISIONES, agent_config)
    
    def get_tools(self) -> list[BaseTool]:
        """Get tools for Admisiones agent."""
        from app.tools.sigeam import (
            ConsultarEstudianteTool,
            ObtenerEstadisticasMatriculaTool,
            GenerarReporteCohorteToolmocktool
        )
        return [
            ConsultarEstudianteTool(),
            ObtenerEstadisticasMatriculaTool(),
            GenerarReporteCohorteToolmocktool(),
        ]


async def get_admisiones_agent() -> AdmisionesAgent:
    """Load Admisiones agent from database."""
    client = get_supabase_admin_client()
    result = client.table("agents").select("*").eq("id", ADMISIONES_AGENT_ID).single().execute()
    
    if not result.data:
        raise ValueError(f"Admisiones agent not found: {ADMISIONES_AGENT_ID}")
    
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
    
    return AdmisionesAgent(config)


async def process_admisiones(state: CognitiveState) -> dict[str, Any]:
    """Process function for LangGraph node."""
    try:
        agent = await get_admisiones_agent()
        return await agent.process(state)
    except Exception as e:
        logger.error("Failed to process admisiones", error=str(e))
        state.log_error(f"Error en Admisiones: {str(e)}", AgentSlot.ADMISIONES)
        return {
            "error": str(e),
            "is_complete": True,
            "brain_log": state.brain_log
        }
