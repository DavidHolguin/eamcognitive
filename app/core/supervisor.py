"""
Supervisor Node - Agent Router
Routes user messages to the appropriate departmental agent(s).
"""

from typing import Any, Literal
from uuid import UUID

import structlog
from langchain_openai import ChatOpenAI
from langchain_core.messages import HumanMessage, SystemMessage
from pydantic import BaseModel, Field

from app.config import get_settings
from app.core.state import CognitiveState, AgentSlot

logger = structlog.get_logger(__name__)


# ─────────────────────────────────────────────────────────────────────────────
# Routing Schema
# ─────────────────────────────────────────────────────────────────────────────

class RouterDecision(BaseModel):
    """Structured output for routing decisions."""
    selected_agent: Literal["admisiones", "finanzas", "retencion", "comunicaciones", "tic", "none"] = Field(
        description="The agent best suited to handle this request"
    )
    confidence: float = Field(
        ge=0.0, le=1.0,
        description="Confidence in the routing decision"
    )
    reasoning: str = Field(
        description="Brief explanation of why this agent was selected"
    )
    requires_collaboration: bool = Field(
        default=False,
        description="Whether multiple agents should collaborate"
    )
    secondary_agents: list[str] = Field(
        default_factory=list,
        description="Additional agents for collaboration if needed"
    )


# ─────────────────────────────────────────────────────────────────────────────
# Supervisor System Prompt
# ─────────────────────────────────────────────────────────────────────────────

SUPERVISOR_SYSTEM_PROMPT = """Eres el Supervisor del Sistema Operativo Cognitivo de la Institución Universitaria EAM (Armenia, Quindío, Colombia).

Tu rol es analizar las solicitudes de los usuarios y enrutarlas al agente departamental más apropiado.

## Agentes Disponibles:

1. **admisiones** (🎓 Analista de Inscripciones)
   - Gestión de matrículas y cohortes
   - Consultas SIGEAM
   - Procesos de inscripción
   - Proyecciones de estudiantes

2. **finanzas** (💰 Contador Cognitivo)
   - Cartera estudiantil
   - Facturación
   - Reportes SNIES
   - Análisis de morosidad
   - Presupuesto

3. **retencion** (📊 Científico de Datos)
   - Alertas de deserción
   - Análisis de permanencia
   - Business Intelligence
   - Predicciones de riesgo académico

4. **comunicaciones** (✍️ Estratega de Contenido)
   - Circulares institucionales
   - Comunicados oficiales
   - Redes sociales institucionales
   - Contenido para la comunidad

5. **tic** (⚙️ Arquitecto de Sistemas)
   - Infraestructura tecnológica
   - Integraciones de sistemas
   - Soporte técnico
   - Mantenimiento de SIGEAM

## Instrucciones:
- Analiza cuidadosamente la solicitud del usuario
- Selecciona el agente MÁS apropiado
- Si la solicitud requiere múltiples expertos, indica colaboración
- Explica brevemente tu razonamiento
- Si no está claro qué agente usar, selecciona "none" para solicitar clarificación

## Contexto Institucional:
- Sistema single-tenant para la EAM
- Prioriza la eficiencia operativa
- Considera los OKRs institucionales en tus decisiones
"""


def get_supervisor_llm() -> ChatOpenAI:
    """Get ChatOpenAI configured for Vercel AI Gateway."""
    settings = get_settings()
    return ChatOpenAI(
        base_url=settings.vercel_ai_gateway_url,
        api_key=settings.vercel_ai_gateway_token.get_secret_value(),
        model=settings.default_model,
        temperature=0.3,  # Lower temperature for consistent routing
    )


async def supervisor_node(state: CognitiveState) -> dict[str, Any]:
    """
    Supervisor node that routes messages to appropriate agents.
    
    Args:
        state: Current cognitive state
        
    Returns:
        Updated state dictionary with routing decision
    """
    logger.info(
        "Supervisor analyzing request",
        run_id=str(state.run_id),
        message_preview=state.user_message[:100]
    )
    
    # Log thinking
    state.log_thinking(
        f"Analyzing user request: {state.user_message[:100]}...",
        agent=None
    )
    
    # Get LLM with structured output
    llm = get_supervisor_llm()
    structured_llm = llm.with_structured_output(RouterDecision)
    
    # Build messages
    messages = [
        SystemMessage(content=SUPERVISOR_SYSTEM_PROMPT),
        HumanMessage(content=f"""Analiza esta solicitud y decide el enrutamiento:

{state.user_message}

Considera:
- OKRs alineados: {[str(okr) for okr in (state.okr_context.aligned_okr_ids if state.okr_context else [])]}
- Agentes ya visitados en esta sesión: {[a.value if hasattr(a, 'value') else a for a in state.visited_agents]}
""")
    ]
    
    try:
        # Get routing decision
        decision: RouterDecision = await structured_llm.ainvoke(messages)
        
        # Log decision
        state.log_decision(
            f"Routing to: {decision.selected_agent} (confidence: {decision.confidence:.2f}) - {decision.reasoning}"
        )
        
        logger.info(
            "Supervisor decision made",
            run_id=str(state.run_id),
            selected_agent=decision.selected_agent,
            confidence=decision.confidence,
            requires_collaboration=decision.requires_collaboration
        )
        
        # Determine next agent
        if decision.selected_agent == "none":
            # Need clarification - return to user
            return {
                "next_agent": None,
                "current_response": "No estoy seguro de cómo ayudarte con esa solicitud. ¿Podrías proporcionar más detalles sobre qué departamento necesitas?",
                "brain_log": state.brain_log
            }
        
        next_agent = AgentSlot(decision.selected_agent)
        
        # Build delegation chain if collaboration needed
        delegation_chain = [next_agent]
        if decision.requires_collaboration:
            for agent_name in decision.secondary_agents:
                try:
                    delegation_chain.append(AgentSlot(agent_name))
                except ValueError:
                    pass  # Skip invalid agent names
        
        return {
            "next_agent": next_agent,
            "delegation_chain": delegation_chain,
            "brain_log": state.brain_log
        }
        
    except Exception as e:
        logger.error(
            "Supervisor routing failed",
            run_id=str(state.run_id),
            error=str(e)
        )
        state.log_error(f"Routing error: {str(e)}")
        return {
            "next_agent": None,
            "error": str(e),
            "brain_log": state.brain_log
        }


def route_to_agent(state: CognitiveState) -> str:
    """
    Conditional edge function for LangGraph routing.
    Determines which node to visit next based on state.
    """
    # Check for errors
    if state.error:
        return "end"
    
    # Check for HITL
    if state.requires_hitl:
        return "hitl_checkpoint"
    
    # Check if complete
    if state.is_complete:
        return "end"
    
    # Check for max iterations
    settings = get_settings()
    if state.iteration_count >= settings.max_agent_iterations:
        return "end"
    
    # Route to next agent
    if state.next_agent:
        return state.next_agent.value if hasattr(state.next_agent, 'value') else state.next_agent
    
    # Default to end
    return "end"
