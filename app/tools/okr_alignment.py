"""
OKR Alignment Tool - Links actions to institutional objectives
"""

from typing import Any, Optional
from uuid import UUID

import structlog
from langchain_core.tools import BaseTool
from pydantic import BaseModel, Field

from app.db.supabase import get_supabase_admin_client

logger = structlog.get_logger(__name__)


class OKRAlignmentInput(BaseModel):
    """Input for OKR alignment check."""
    accion: str = Field(description="Descripción de la acción a vincular")


class OKRAlignmentTool(BaseTool):
    """Alinea acciones con OKRs institucionales."""
    
    name: str = "alinear_okr"
    description: str = "Encuentra los Objetivos y Resultados Clave (OKRs) institucionales más relevantes para una acción."
    args_schema: type[BaseModel] = OKRAlignmentInput
    
    def _run(self, accion: str) -> dict[str, Any]:
        """Find relevant OKRs for an action."""
        try:
            client = get_supabase_admin_client()
            
            # Get active objectives
            result = client.table("objectives").select(
                "id, title, description, period, progress"
            ).eq("is_active", True).execute()
            
            objectives = result.data if result.data else []
            
            # Simple keyword matching (in production, use embeddings)
            keywords = accion.lower().split()
            scored_objectives = []
            
            for obj in objectives:
                score = 0
                text = f"{obj['title']} {obj.get('description', '')}".lower()
                for keyword in keywords:
                    if keyword in text:
                        score += 1
                if score > 0:
                    scored_objectives.append({
                        "id": obj["id"],
                        "title": obj["title"],
                        "relevance_score": score / len(keywords),
                        "progress": obj["progress"]
                    })
            
            # Sort by relevance
            scored_objectives.sort(key=lambda x: x["relevance_score"], reverse=True)
            
            return {
                "accion": accion,
                "okrs_relevantes": scored_objectives[:3],
                "total_encontrados": len(scored_objectives),
                "recomendacion": scored_objectives[0]["title"] if scored_objectives else None
            }
            
        except Exception as e:
            logger.error("OKR alignment failed", error=str(e))
            return {
                "error": str(e),
                "accion": accion,
                "okrs_relevantes": []
            }
    
    async def _arun(self, accion: str) -> dict[str, Any]:
        return self._run(accion)
