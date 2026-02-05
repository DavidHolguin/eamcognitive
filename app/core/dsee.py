"""
DSEE - Deterministic State Evolution Engine
Ensures deterministic state transitions with full audit trail.
"""

from datetime import datetime
from typing import Any, Callable, TypeVar
from uuid import UUID

import structlog

from app.core.state import CognitiveState, BrainLogEntry, StepType

logger = structlog.get_logger(__name__)

T = TypeVar("T")


class DSEEEngine:
    """
    Deterministic State Evolution Engine.
    
    Core principles:
    1. Pure Functions: State transitions are pure functions
    2. Immutability: States are never mutated, always replaced
    3. Audit Trail: Every transition is logged
    4. Reproducibility: Same input → same output
    """
    
    def __init__(self, persist_callback: Callable[[CognitiveState], None] | None = None):
        """
        Initialize DSEE Engine.
        
        Args:
            persist_callback: Optional callback to persist state changes
        """
        self.persist_callback = persist_callback
        self._transition_count = 0
    
    def evolve(
        self,
        state: CognitiveState,
        transition_fn: Callable[[CognitiveState], CognitiveState],
        transition_name: str = "anonymous"
    ) -> CognitiveState:
        """
        Apply a deterministic state transition.
        
        Args:
            state: Current state
            transition_fn: Pure function that returns new state
            transition_name: Name for logging/audit
            
        Returns:
            New evolved state
        """
        self._transition_count += 1
        start_time = datetime.utcnow()
        
        logger.info(
            "DSEE transition starting",
            transition=transition_name,
            run_id=str(state.run_id),
            iteration=state.iteration_count
        )
        
        try:
            # Apply transition
            new_state = transition_fn(state)
            
            # Update metadata
            new_state.updated_at = datetime.utcnow()
            new_state.iteration_count = state.iteration_count + 1
            
            # Calculate duration
            duration_ms = int((new_state.updated_at - start_time).total_seconds() * 1000)
            
            # Log successful transition
            logger.info(
                "DSEE transition complete",
                transition=transition_name,
                run_id=str(new_state.run_id),
                duration_ms=duration_ms,
                brain_log_entries=len(new_state.brain_log)
            )
            
            # Persist if callback provided
            if self.persist_callback:
                self.persist_callback(new_state)
            
            return new_state
            
        except Exception as e:
            logger.error(
                "DSEE transition failed",
                transition=transition_name,
                run_id=str(state.run_id),
                error=str(e)
            )
            # Log error in state
            error_state = state.log_error(f"Transition '{transition_name}' failed: {str(e)}")
            
            if self.persist_callback:
                self.persist_callback(error_state)
            
            raise
    
    def batch_evolve(
        self,
        state: CognitiveState,
        transitions: list[tuple[Callable[[CognitiveState], CognitiveState], str]]
    ) -> CognitiveState:
        """
        Apply multiple transitions in sequence.
        
        Args:
            state: Initial state
            transitions: List of (transition_fn, name) tuples
            
        Returns:
            Final evolved state
        """
        current_state = state
        for transition_fn, name in transitions:
            current_state = self.evolve(current_state, transition_fn, name)
        return current_state


# ─────────────────────────────────────────────────────────────────────────────
# Common State Transitions
# ─────────────────────────────────────────────────────────────────────────────

def transition_start_agent(agent_slot: str) -> Callable[[CognitiveState], CognitiveState]:
    """Create a transition that marks entering an agent."""
    def _transition(state: CognitiveState) -> CognitiveState:
        from app.core.state import AgentSlot
        slot = AgentSlot(agent_slot)
        state.mark_visited(slot)
        state.log_thinking(f"Entering agent: {slot.value}", slot)
        return state
    return _transition


def transition_complete_response(response: str) -> Callable[[CognitiveState], CognitiveState]:
    """Create a transition that completes the run with a response."""
    def _transition(state: CognitiveState) -> CognitiveState:
        state.complete(response)
        state.log_decision(f"Final response generated ({len(response)} chars)")
        return state
    return _transition


def transition_request_hitl(reason: str) -> Callable[[CognitiveState], CognitiveState]:
    """Create a transition that requests HITL approval."""
    def _transition(state: CognitiveState) -> CognitiveState:
        state.request_hitl(reason)
        state.log_decision(f"HITL requested: {reason}")
        return state
    return _transition


def transition_add_memory(
    content: str, 
    relevance: float = 0.5
) -> Callable[[CognitiveState], CognitiveState]:
    """Create a transition that adds a retrieved memory."""
    def _transition(state: CognitiveState) -> CognitiveState:
        state.retrieved_memories.append({
            "content": content,
            "relevance": relevance,
            "retrieved_at": datetime.utcnow().isoformat()
        })
        return state
    return _transition


# ─────────────────────────────────────────────────────────────────────────────
# Global Engine Instance
# ─────────────────────────────────────────────────────────────────────────────

_engine: DSEEEngine | None = None


def get_dsee_engine(persist_callback: Callable[[CognitiveState], None] | None = None) -> DSEEEngine:
    """Get or create the global DSEE engine instance."""
    global _engine
    if _engine is None:
        _engine = DSEEEngine(persist_callback)
    return _engine
