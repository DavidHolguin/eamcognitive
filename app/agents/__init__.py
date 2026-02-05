"""EAM Cognitive OS - Agents module."""

from app.agents.base import BaseAgentNode, AgentResponse
from app.agents.admisiones import AdmisionesAgent, process_admisiones
from app.agents.finanzas import FinanzasAgent, process_finanzas
from app.agents.retencion import RetencionAgent, process_retencion
from app.agents.comunicaciones import ComunicacionesAgent, process_comunicaciones
from app.agents.tic import TICAgent, process_tic

__all__ = [
    "BaseAgentNode",
    "AgentResponse",
    "AdmisionesAgent",
    "FinanzasAgent",
    "RetencionAgent",
    "ComunicacionesAgent",
    "TICAgent",
    "process_admisiones",
    "process_finanzas",
    "process_retencion",
    "process_comunicaciones",
    "process_tic",
]
