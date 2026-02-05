"""
Memory Search Tool - Vector similarity search for long-term memory
"""

from typing import Any, Optional
from uuid import UUID

import structlog
from langchain_core.tools import BaseTool
from pydantic import BaseModel, Field

from app.db.supabase import get_supabase_admin_client
from app.config import get_settings

logger = structlog.get_logger(__name__)


class MemorySearchInput(BaseModel):
    """Input for memory search."""
    query: str = Field(description="Texto de búsqueda")
    limit: int = Field(default=5, description="Número máximo de resultados")
    agent_id: Optional[str] = Field(default=None, description="Filtrar por agente específico")


class MemorySearchTool(BaseTool):
    """Busca en la memoria de largo plazo."""
    
    name: str = "buscar_memoria"
    description: str = "Busca información relevante en la memoria institucional de largo plazo."
    args_schema: type[BaseModel] = MemorySearchInput
    
    def _run(self, query: str, limit: int = 5, agent_id: Optional[str] = None) -> dict[str, Any]:
        """Search memories using similarity."""
        try:
            client = get_supabase_admin_client()
            
            # For now, do a simple text search until embeddings are implemented
            search_query = client.table("memories").select(
                "id, content, memory_type, importance, created_at"
            ).ilike("content", f"%{query}%").limit(limit)
            
            if agent_id:
                search_query = search_query.eq("agent_id", agent_id)
            
            result = search_query.execute()
            memories = result.data if result.data else []
            
            return {
                "query": query,
                "results": memories,
                "total_encontrados": len(memories),
                "metodo": "text_search"  # Will be "vector_similarity" after embedding implementation
            }
            
        except Exception as e:
            logger.error("Memory search failed", error=str(e))
            # Return empty results on error (table might not exist yet)
            return {
                "query": query,
                "results": [],
                "total_encontrados": 0,
                "error": str(e)
            }
    
    async def _arun(self, query: str, limit: int = 5, agent_id: Optional[str] = None) -> dict[str, Any]:
        return self._run(query, limit, agent_id)
