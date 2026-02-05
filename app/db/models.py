"""
Database Models - Pydantic schemas for Supabase tables
Aligned with existing schema discovered in EAM COGNITIVE TEAM project
"""

from datetime import datetime
from enum import Enum
from typing import Any, Optional
from uuid import UUID

from pydantic import BaseModel, Field, ConfigDict


# ─────────────────────────────────────────────────────────────────────────────
# Enums (matching database types)
# ─────────────────────────────────────────────────────────────────────────────

class AgentStatus(str, Enum):
    ACTIVE = "active"
    IDLE = "idle"
    BUSY = "busy"
    ERROR = "error"


class RunStatus(str, Enum):
    QUEUED = "queued"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class AccessLevel(str, Enum):
    SEDE_PRINCIPAL = "sede_principal"
    VPN_INSTITUCIONAL = "vpn_institucional"
    EXTERNO = "externo"


class AppRole(str, Enum):
    ADMIN = "admin"
    DIRECTOR = "director"
    COORDINADOR = "coordinador"
    DOCENTE = "docente"
    ADMINISTRATIVO = "administrativo"
    INVITADO = "invitado"


class TaskStatus(str, Enum):
    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    CANCELLED = "cancelled"


class TaskPriority(str, Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    URGENT = "urgent"


class StepType(str, Enum):
    THINKING = "thinking"
    ACTION = "action"
    OBSERVATION = "observation"
    DECISION = "decision"
    ERROR = "error"


class MemoryType(str, Enum):
    EPISODIC = "episodic"
    SEMANTIC = "semantic"
    PROCEDURAL = "procedural"


class HITLStatus(str, Enum):
    PENDING = "pending"
    APPROVED = "approved"
    REJECTED = "rejected"
    EXPIRED = "expired"


class SenderType(str, Enum):
    USER = "user"
    AGENT = "agent"
    SYSTEM = "system"


# ─────────────────────────────────────────────────────────────────────────────
# Base Model
# ─────────────────────────────────────────────────────────────────────────────

class DBBaseModel(BaseModel):
    """Base for all database models with common config."""
    model_config = ConfigDict(
        from_attributes=True,
        populate_by_name=True,
        use_enum_values=True
    )


# ─────────────────────────────────────────────────────────────────────────────
# Agent Models
# ─────────────────────────────────────────────────────────────────────────────

class AgentModelConfig(BaseModel):
    """LLM configuration stored in agent.model_config JSONB."""
    model: str = "openai/gpt-4o-mini"
    temperature: float = 0.7
    max_tokens: Optional[int] = None


class Agent(DBBaseModel):
    """Represents an agent from the 'agents' table."""
    id: UUID
    name: str
    role: str
    avatar: str
    status: AgentStatus = AgentStatus.IDLE
    department: str
    specialization: str
    goal: str
    tools: list[str] = Field(default_factory=list)
    system_prompt: Optional[str] = None
    model_config_data: Optional[AgentModelConfig] = Field(
        default=None, 
        alias="model_config"
    )
    is_active: bool = True
    created_at: datetime
    updated_at: datetime


class AgentCreate(BaseModel):
    """Schema for creating a new agent."""
    name: str
    role: str
    avatar: str
    department: str
    specialization: str
    goal: str
    tools: list[str] = Field(default_factory=list)
    system_prompt: Optional[str] = None
    llm_config: Optional[AgentModelConfig] = None


# ─────────────────────────────────────────────────────────────────────────────
# Agent Run Models
# ─────────────────────────────────────────────────────────────────────────────

class AgentRun(DBBaseModel):
    """Represents an agent execution run from 'agent_runs' table."""
    id: UUID
    agent_id: UUID
    triggered_by: UUID
    conversation_id: Optional[UUID] = None
    status: RunStatus = RunStatus.QUEUED
    input_params: Optional[dict[str, Any]] = None
    result: Optional[dict[str, Any]] = None
    error_message: Optional[str] = None
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    created_at: datetime


class AgentRunCreate(BaseModel):
    """Schema for creating a new agent run."""
    agent_id: UUID
    triggered_by: UUID
    conversation_id: Optional[UUID] = None
    input_params: Optional[dict[str, Any]] = None


# ─────────────────────────────────────────────────────────────────────────────
# Conversation & Message Models
# ─────────────────────────────────────────────────────────────────────────────

class Conversation(DBBaseModel):
    """Represents a conversation from 'conversations' table."""
    id: UUID
    channel_id: Optional[UUID] = None
    user_id: Optional[UUID] = None
    title: Optional[str] = None
    metadata: Optional[dict[str, Any]] = None
    created_at: datetime
    updated_at: datetime


class Message(DBBaseModel):
    """Represents a message from 'messages' table."""
    id: UUID
    conversation_id: UUID
    sender_type: SenderType
    sender_id: Optional[UUID] = None
    agent_id: Optional[UUID] = None
    content: str
    metadata: Optional[dict[str, Any]] = None
    created_at: datetime


class MessageCreate(BaseModel):
    """Schema for creating a new message."""
    conversation_id: UUID
    sender_type: SenderType
    sender_id: Optional[UUID] = None
    agent_id: Optional[UUID] = None
    content: str
    metadata: Optional[dict[str, Any]] = None


# ─────────────────────────────────────────────────────────────────────────────
# OKR Models (Objectives & Key Results)
# ─────────────────────────────────────────────────────────────────────────────

class Objective(DBBaseModel):
    """Institutional objective from 'objectives' table."""
    id: UUID
    title: str
    description: Optional[str] = None
    period: str
    progress: int = Field(default=0, ge=0, le=100)
    embedding: Optional[list[float]] = None
    is_active: bool = True
    created_at: datetime
    updated_at: datetime


class KeyResult(DBBaseModel):
    """Key result linked to an objective from 'key_results' table."""
    id: UUID
    objective_id: UUID
    description: str
    current_value: float = 0
    target_value: float
    unit: Optional[str] = None
    created_at: datetime
    updated_at: datetime


# ─────────────────────────────────────────────────────────────────────────────
# Task Models
# ─────────────────────────────────────────────────────────────────────────────

class Task(DBBaseModel):
    """Task from 'tasks' table."""
    id: UUID
    title: str
    description: Optional[str] = None
    status: TaskStatus = TaskStatus.PENDING
    priority: TaskPriority = TaskPriority.MEDIUM
    assigned_agent_id: Optional[UUID] = None
    assigned_user_id: Optional[UUID] = None
    objective_id: Optional[UUID] = None
    due_date: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    created_at: datetime
    updated_at: datetime


# ─────────────────────────────────────────────────────────────────────────────
# Brain Log Models (To be created via migration)
# ─────────────────────────────────────────────────────────────────────────────

class BrainLogEntry(DBBaseModel):
    """Entry in brain_log table - agent thinking persistence."""
    id: UUID
    run_id: UUID
    step_type: StepType
    content: str
    tool_name: Optional[str] = None
    tool_input: Optional[dict[str, Any]] = None
    tool_output: Optional[Any] = None
    tokens_used: Optional[int] = None
    duration_ms: Optional[int] = None
    created_at: datetime


class BrainLogCreate(BaseModel):
    """Schema for creating a brain log entry."""
    run_id: UUID
    step_type: StepType
    content: str
    tool_name: Optional[str] = None
    tool_input: Optional[dict[str, Any]] = None
    tool_output: Optional[Any] = None
    tokens_used: Optional[int] = None
    duration_ms: Optional[int] = None


# ─────────────────────────────────────────────────────────────────────────────
# Memory Models (To be created via migration)
# ─────────────────────────────────────────────────────────────────────────────

class Memory(DBBaseModel):
    """Long-term memory with vector embedding."""
    id: UUID
    agent_id: Optional[UUID] = None
    content: str
    embedding: Optional[list[float]] = None
    memory_type: MemoryType
    importance: float = 0.5
    last_accessed: datetime
    access_count: int = 0
    metadata: Optional[dict[str, Any]] = None
    created_at: datetime


class MemoryCreate(BaseModel):
    """Schema for creating a memory."""
    agent_id: Optional[UUID] = None
    content: str
    embedding: Optional[list[float]] = None
    memory_type: MemoryType
    importance: float = 0.5
    metadata: Optional[dict[str, Any]] = None


# ─────────────────────────────────────────────────────────────────────────────
# HITL Models (To be created via migration)
# ─────────────────────────────────────────────────────────────────────────────

class HITLRequest(DBBaseModel):
    """Human-in-the-Loop approval request."""
    id: UUID
    run_id: UUID
    requested_by: UUID
    reason: str
    context: dict[str, Any]
    proposed_action: dict[str, Any]
    status: HITLStatus = HITLStatus.PENDING
    reviewed_by: Optional[UUID] = None
    review_notes: Optional[str] = None
    created_at: datetime
    reviewed_at: Optional[datetime] = None
    expires_at: datetime


class HITLRequestCreate(BaseModel):
    """Schema for creating a HITL request."""
    run_id: UUID
    requested_by: UUID
    reason: str
    context: dict[str, Any]
    proposed_action: dict[str, Any]


class HITLReview(BaseModel):
    """Schema for reviewing a HITL request."""
    status: HITLStatus
    review_notes: Optional[str] = None


# ─────────────────────────────────────────────────────────────────────────────
# User & Security Models
# ─────────────────────────────────────────────────────────────────────────────

class Profile(DBBaseModel):
    """User profile from 'profiles' table."""
    id: UUID
    email: str
    full_name: Optional[str] = None
    avatar_url: Optional[str] = None
    department: Optional[str] = None
    position: Optional[str] = None
    created_at: datetime
    updated_at: datetime


class UserRole(DBBaseModel):
    """User role assignment from 'user_roles' table."""
    id: UUID
    user_id: UUID
    role: AppRole
    granted_by: Optional[UUID] = None
    granted_at: datetime


class AccessLog(DBBaseModel):
    """Access log entry from 'access_logs' table."""
    id: UUID
    user_id: Optional[UUID] = None
    action: str
    resource_type: Optional[str] = None
    resource_id: Optional[UUID] = None
    ip_address: Optional[str] = None
    user_agent: Optional[str] = None
    access_level: Optional[AccessLevel] = None
    device_verified: bool = False
    metadata: Optional[dict[str, Any]] = None
    created_at: datetime
