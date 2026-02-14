"""
LangGraph StateGraph - Main Cognitive Graph
Orchestrates the flow between Supervisor and departmental agents.
"""

from typing import Any
from uuid import UUID

import structlog
from langgraph.graph import StateGraph, START, END
from langgraph.graph.state import CompiledStateGraph

from app.core.state import CognitiveState, AgentSlot
from app.core.supervisor import supervisor_node, route_to_agent
from app.core.checkpointer import SupabaseCheckpointer

logger = structlog.get_logger(__name__)


# ─────────────────────────────────────────────────────────────────────────────
# Placeholder Agent Nodes (will be replaced with actual implementations)
# ─────────────────────────────────────────────────────────────────────────────

async def admisiones_node(state: CognitiveState) -> dict[str, Any]:
    """Admisiones agent node - placeholder."""
    state.mark_visited(AgentSlot.ADMISIONES)
    state.log_thinking("Procesando solicitud de Admisiones...", AgentSlot.ADMISIONES)
    # Actual implementation will be in agents/admisiones.py
    from app.agents.admisiones import process_admisiones
    return await process_admisiones(state)


async def finanzas_node(state: CognitiveState) -> dict[str, Any]:
    """Finanzas agent node - placeholder."""
    state.mark_visited(AgentSlot.FINANZAS)
    state.log_thinking("Procesando solicitud de Finanzas...", AgentSlot.FINANZAS)
    from app.agents.finanzas import process_finanzas
    return await process_finanzas(state)


async def retencion_node(state: CognitiveState) -> dict[str, Any]:
    """Retención agent node - placeholder."""
    state.mark_visited(AgentSlot.RETENCION)
    state.log_thinking("Procesando solicitud de Retención...", AgentSlot.RETENCION)
    from app.agents.retencion import process_retencion
    return await process_retencion(state)


async def comunicaciones_node(state: CognitiveState) -> dict[str, Any]:
    """Comunicaciones agent node - placeholder."""
    state.mark_visited(AgentSlot.COMUNICACIONES)
    state.log_thinking("Procesando solicitud de Comunicaciones...", AgentSlot.COMUNICACIONES)
    from app.agents.comunicaciones import process_comunicaciones
    return await process_comunicaciones(state)


async def tic_node(state: CognitiveState) -> dict[str, Any]:
    """TIC agent node - placeholder."""
    state.mark_visited(AgentSlot.TIC)
    state.log_thinking("Procesando solicitud de TIC...", AgentSlot.TIC)
    from app.agents.tic import process_tic
    return await process_tic(state)


# ─────────────────────────────────────────────────────────────────────────────
# HITL Checkpoint Node
# ─────────────────────────────────────────────────────────────────────────────

async def hitl_checkpoint_node(state: CognitiveState) -> dict[str, Any]:
    """
    Human-in-the-Loop checkpoint node.
    Pauses execution and waits for human approval.
    """
    logger.info(
        "HITL checkpoint reached",
        run_id=str(state.run_id),
        reason=state.hitl_reason
    )
    
    state.log_decision(f"Esperando aprobación humana: {state.hitl_reason}")
    
    # Create HITL request in database
    from app.security.hitl import create_hitl_request
    hitl_request = await create_hitl_request(state)
    
    return {
        "hitl_request_id": hitl_request.id if hitl_request else None,
        "is_complete": True,  # Pause execution until approval
        "current_response": f"⏸️ Esta acción requiere aprobación humana: {state.hitl_reason}",
        "brain_log": state.brain_log
    }


# ─────────────────────────────────────────────────────────────────────────────
# End Node
# ─────────────────────────────────────────────────────────────────────────────

async def end_node(state: CognitiveState) -> dict[str, Any]:
    """
    Final node - marks execution as complete.
    """
    logger.info(
        "Execution complete",
        run_id=str(state.run_id),
        visited_agents=[a.value if hasattr(a, 'value') else a for a in state.visited_agents]
    )
    
    # Finalize response if not already set
    if not state.final_response:
        state.complete(state.current_response or "Procesamiento completado.")
    
    state.log_decision("Ejecución finalizada")
    
    return {
        "is_complete": True,
        "final_response": state.final_response or state.current_response,
        "brain_log": state.brain_log
    }


# ─────────────────────────────────────────────────────────────────────────────
# Graph Builder
# ─────────────────────────────────────────────────────────────────────────────

def build_cognitive_graph(use_checkpointer: bool = True) -> CompiledStateGraph:
    """
    Build and compile the main cognitive graph.
    
    Returns:
        Compiled LangGraph StateGraph
    """
    # Create graph with CognitiveState
    builder = StateGraph(CognitiveState)
    
    # Add nodes
    builder.add_node("supervisor", supervisor_node)
    builder.add_node("admisiones", admisiones_node)
    builder.add_node("finanzas", finanzas_node)
    builder.add_node("retencion", retencion_node)
    builder.add_node("comunicaciones", comunicaciones_node)
    builder.add_node("tic", tic_node)
    builder.add_node("hitl_checkpoint", hitl_checkpoint_node)
    builder.add_node("end", end_node)
    
    # Set entry point
    builder.add_edge(START, "supervisor")
    
    # Conditional routing from supervisor
    builder.add_conditional_edges(
        "supervisor",
        route_to_agent,
        {
            "admisiones": "admisiones",
            "finanzas": "finanzas",
            "retencion": "retencion",
            "comunicaciones": "comunicaciones",
            "tic": "tic",
            "hitl_checkpoint": "hitl_checkpoint",
            "end": "end"
        }
    )
    
    # Agent nodes can route back to supervisor or end
    for agent in ["admisiones", "finanzas", "retencion", "comunicaciones", "tic"]:
        builder.add_conditional_edges(
            agent,
            route_to_agent,
            {
                "admisiones": "admisiones",
                "finanzas": "finanzas",
                "retencion": "retencion",
                "comunicaciones": "comunicaciones",
                "tic": "tic",
                "hitl_checkpoint": "hitl_checkpoint",
                "end": "end"
            }
        )
    
    # HITL always goes to end (waits for external approval)
    builder.add_edge("hitl_checkpoint", "end")
    
    # End node terminates
    builder.add_edge("end", END)
    
    # Compile with or without checkpointer
    if use_checkpointer:
        checkpointer = SupabaseCheckpointer()
        graph = builder.compile(checkpointer=checkpointer)
    else:
        graph = builder.compile()
    
    logger.info("Cognitive graph compiled successfully", checkpointer=use_checkpointer)
    
    return graph


# ─────────────────────────────────────────────────────────────────────────────
# Global Graph Instances
# ─────────────────────────────────────────────────────────────────────────────

_cognitive_graph: CompiledStateGraph | None = None
_cognitive_graph_async: CompiledStateGraph | None = None


def get_cognitive_graph() -> CompiledStateGraph:
    """Get or create the global cognitive graph instance (with sync checkpointer)."""
    global _cognitive_graph
    if _cognitive_graph is None:
        _cognitive_graph = build_cognitive_graph(use_checkpointer=True)
    return _cognitive_graph


def get_cognitive_graph_async() -> CompiledStateGraph:
    """Get or create the global cognitive graph instance WITHOUT checkpointer.
    Use this for async operations (ainvoke, astream, astream_events)
    since the SupabaseCheckpointer only has sync methods."""
    global _cognitive_graph_async
    if _cognitive_graph_async is None:
        _cognitive_graph_async = build_cognitive_graph(use_checkpointer=False)
    return _cognitive_graph_async

