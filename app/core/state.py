"""
Cognitive State - Canonical State Object
This is the SINGLE state object that flows through the entire LangGraph.
Implements the DSEE (Deterministic State Evolution Engine) pattern.
"""

from datetime import datetime
from enum import Enum
from typing import Annotated, Any, Optional
from uuid import UUID, uuid4

from pydantic import BaseModel, Field
from langgraph.graph.message import add_messages


# ─────────────────────────────────────────────────────────────────────────────
# Enums
# ─────────────────────────────────────────────────────────────────────────────

class AgentSlot(str, Enum):
    """Available agent slots (departments)."""
    ADMISIONES = "admisiones"
    FINANZAS = "finanzas"
    RETENCION = "retencion"
    COMUNICACIONES = "comunicaciones"
    TIC = "tic"


class StepType(str, Enum):
    """Types of brain log entries."""
    THINKING = "thinking"
    ACTION = "action"
    OBSERVATION = "observation"
    DECISION = "decision"
    ERROR = "error"


# ─────────────────────────────────────────────────────────────────────────────
# Nested State Components
# ─────────────────────────────────────────────────────────────────────────────

class BrainLogEntry(BaseModel):
    """
    Single entry in the agent's brain log.
    This is the "black box" recording of agent thinking.
    """
    step_type: StepType
    content: str
    agent_slot: Optional[AgentSlot] = None
    tool_name: Optional[str] = None
    tool_input: Optional[dict[str, Any]] = None
    tool_output: Optional[Any] = None
    tokens_used: Optional[int] = None
    duration_ms: Optional[int] = None
    timestamp: datetime = Field(default_factory=datetime.utcnow)
    
    class Config:
        use_enum_values = True


class GenUIPayload(BaseModel):
    """
    Payload for generating UI components on frontend.
    Streamed via WebSocket to React frontend.
    """
    component: str  # 'kanban', 'chart', 'hitl', 'card', 'table', 'form'
    data: dict[str, Any]
    metadata: Optional[dict[str, Any]] = None


class SecurityContext(BaseModel):
    """
    Security context for the current request.
    Used for Zero Trust validation and audit logging.
    """
    user_id: UUID
    access_level: str = "externo"  # 'sede_principal', 'vpn_institucional', 'externo'
    device_verified: bool = False
    session_id: str
    ip_address: Optional[str] = None
    user_agent: Optional[str] = None


class OKRContext(BaseModel):
    """
    OKR alignment context for the current task.
    Links actions to institutional objectives.
    """
    aligned_okr_ids: list[UUID] = Field(default_factory=list)
    primary_objective: Optional[str] = None
    relevance_scores: dict[str, float] = Field(default_factory=dict)
    context_summary: Optional[str] = None


# ─────────────────────────────────────────────────────────────────────────────
# Main Cognitive State
# ─────────────────────────────────────────────────────────────────────────────

class CognitiveState(BaseModel):
    """
    Cognitive State - The canonical state object for the entire system.
    
    This is the ONLY object that flows through the LangGraph StateGraph.
    All agent nodes read from and write to this state.
    
    Design Principles (DSEE Pattern):
    1. Deterministic: Same input → same output
    2. Immutable Updates: New state objects, not mutations
    3. Full Audit Trail: Every change recorded in brain_log
    4. Type Safety: Strict Pydantic validation
    """
    
    # ─────────────────────────────────────────────────────────────────────────
    # Execution Identifiers
    # ─────────────────────────────────────────────────────────────────────────
    run_id: UUID = Field(default_factory=uuid4)
    conversation_id: UUID
    triggered_by: UUID  # User ID who initiated this run
    
    # ─────────────────────────────────────────────────────────────────────────
    # Input/Output
    # ─────────────────────────────────────────────────────────────────────────
    user_message: str
    current_response: str = ""
    final_response: Optional[str] = None
    
    # LangGraph messages (for chat history within this run)
    messages: Annotated[list[Any], add_messages] = Field(default_factory=list)
    
    # ─────────────────────────────────────────────────────────────────────────
    # Agent Routing
    # ─────────────────────────────────────────────────────────────────────────
    next_agent: Optional[AgentSlot] = None
    visited_agents: list[AgentSlot] = Field(default_factory=list)
    delegation_chain: list[AgentSlot] = Field(default_factory=list)
    
    # ─────────────────────────────────────────────────────────────────────────
    # Brain Log (Black Box Recording)
    # ─────────────────────────────────────────────────────────────────────────
    brain_log: list[BrainLogEntry] = Field(default_factory=list)
    
    # ─────────────────────────────────────────────────────────────────────────
    # GenUI Components (for frontend streaming)
    # ─────────────────────────────────────────────────────────────────────────
    genui_payloads: list[GenUIPayload] = Field(default_factory=list)
    
    # ─────────────────────────────────────────────────────────────────────────
    # OKR Alignment (Strategic Context)
    # ─────────────────────────────────────────────────────────────────────────
    okr_context: Optional[OKRContext] = None
    
    # ─────────────────────────────────────────────────────────────────────────
    # Memory Context
    # ─────────────────────────────────────────────────────────────────────────
    retrieved_memories: list[dict[str, Any]] = Field(default_factory=list)
    memory_query: Optional[str] = None
    
    # ─────────────────────────────────────────────────────────────────────────
    # Flow Control
    # ─────────────────────────────────────────────────────────────────────────
    requires_hitl: bool = False
    hitl_reason: Optional[str] = None
    hitl_request_id: Optional[UUID] = None
    
    is_complete: bool = False
    error: Optional[str] = None
    iteration_count: int = 0
    
    # ─────────────────────────────────────────────────────────────────────────
    # Security Context
    # ─────────────────────────────────────────────────────────────────────────
    security_context: SecurityContext
    
    # ─────────────────────────────────────────────────────────────────────────
    # Metadata
    # ─────────────────────────────────────────────────────────────────────────
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)
    
    class Config:
        use_enum_values = True
    
    # ─────────────────────────────────────────────────────────────────────────
    # Helper Methods
    # ─────────────────────────────────────────────────────────────────────────
    
    def log_thinking(self, content: str, agent: Optional[AgentSlot] = None) -> "CognitiveState":
        """Add a thinking entry to the brain log."""
        entry = BrainLogEntry(
            step_type=StepType.THINKING,
            content=content,
            agent_slot=agent
        )
        self.brain_log.append(entry)
        self.updated_at = datetime.utcnow()
        return self
    
    def log_action(
        self, 
        tool_name: str, 
        tool_input: dict[str, Any],
        agent: Optional[AgentSlot] = None
    ) -> "CognitiveState":
        """Add an action entry to the brain log."""
        entry = BrainLogEntry(
            step_type=StepType.ACTION,
            content=f"Executing tool: {tool_name}",
            agent_slot=agent,
            tool_name=tool_name,
            tool_input=tool_input
        )
        self.brain_log.append(entry)
        self.updated_at = datetime.utcnow()
        return self
    
    def log_observation(
        self, 
        content: str,
        tool_name: Optional[str] = None,
        tool_output: Optional[Any] = None,
        agent: Optional[AgentSlot] = None
    ) -> "CognitiveState":
        """Add an observation entry to the brain log."""
        entry = BrainLogEntry(
            step_type=StepType.OBSERVATION,
            content=content,
            agent_slot=agent,
            tool_name=tool_name,
            tool_output=tool_output
        )
        self.brain_log.append(entry)
        self.updated_at = datetime.utcnow()
        return self
    
    def log_decision(self, content: str, agent: Optional[AgentSlot] = None) -> "CognitiveState":
        """Add a decision entry to the brain log."""
        entry = BrainLogEntry(
            step_type=StepType.DECISION,
            content=content,
            agent_slot=agent
        )
        self.brain_log.append(entry)
        self.updated_at = datetime.utcnow()
        return self
    
    def log_error(self, content: str, agent: Optional[AgentSlot] = None) -> "CognitiveState":
        """Add an error entry to the brain log."""
        entry = BrainLogEntry(
            step_type=StepType.ERROR,
            content=content,
            agent_slot=agent
        )
        self.brain_log.append(entry)
        self.error = content
        self.updated_at = datetime.utcnow()
        return self
    
    def add_genui(self, component: str, data: dict[str, Any]) -> "CognitiveState":
        """Add a GenUI payload for frontend rendering."""
        payload = GenUIPayload(component=component, data=data)
        self.genui_payloads.append(payload)
        self.updated_at = datetime.utcnow()
        return self
    
    def mark_visited(self, agent: AgentSlot) -> "CognitiveState":
        """Mark an agent as visited in this run."""
        if agent not in self.visited_agents:
            self.visited_agents.append(agent)
        self.updated_at = datetime.utcnow()
        return self
    
    def request_hitl(self, reason: str) -> "CognitiveState":
        """Request human-in-the-loop approval."""
        self.requires_hitl = True
        self.hitl_reason = reason
        self.updated_at = datetime.utcnow()
        return self
    
    def complete(self, response: str) -> "CognitiveState":
        """Mark the run as complete with final response."""
        self.final_response = response
        self.current_response = response
        self.is_complete = True
        self.updated_at = datetime.utcnow()
        return self
