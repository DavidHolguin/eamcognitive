"""
Base Agent Node - Abstract base class for all departmental agents.
"""

from abc import ABC, abstractmethod
from datetime import datetime
from typing import Any, Optional
from uuid import UUID

import structlog
from langchain_openai import ChatOpenAI
from langchain_core.messages import HumanMessage, SystemMessage, AIMessage
from langchain_core.tools import BaseTool
from pydantic import BaseModel

from app.config import get_settings
from app.core.state import CognitiveState, AgentSlot, BrainLogEntry, StepType
from app.db.models import Agent, AgentModelConfig

logger = structlog.get_logger(__name__)


class AgentResponse(BaseModel):
    """Structured response from an agent."""
    response: str
    needs_delegation: bool = False
    delegate_to: Optional[str] = None
    requires_hitl: bool = False
    hitl_reason: Optional[str] = None
    genui_components: list[dict[str, Any]] = []


class BaseAgentNode(ABC):
    """
    Abstract base class for departmental agents.
    
    Each agent:
    1. Loads its configuration from the database
    2. Initializes an LLM via Vercel AI Gateway
    3. Binds its available tools
    4. Processes requests using ReAct pattern
    5. Logs all thinking to brain_log
    """
    
    def __init__(self, agent_slot: AgentSlot, agent_config: Agent):
        """
        Initialize the agent.
        
        Args:
            agent_slot: The slot this agent occupies
            agent_config: Agent configuration from database
        """
        self.slot = agent_slot
        self.config = agent_config
        self.settings = get_settings()
        self._llm: Optional[ChatOpenAI] = None
        self._tools: list[BaseTool] = []
    
    @property
    def llm(self) -> ChatOpenAI:
        """Get or create the LLM instance."""
        if self._llm is None:
            model_config = self.config.model_config_data or AgentModelConfig()
            self._llm = ChatOpenAI(
                base_url=self.settings.vercel_ai_gateway_url,
                api_key=self.settings.vercel_ai_gateway_token.get_secret_value(),
                model=model_config.model,
                temperature=model_config.temperature,
                max_tokens=model_config.max_tokens,
            )
        return self._llm
    
    @abstractmethod
    def get_tools(self) -> list[BaseTool]:
        """Return the tools available to this agent."""
        pass
    
    @property
    def tools(self) -> list[BaseTool]:
        """Get or create tools list."""
        if not self._tools:
            self._tools = self.get_tools()
        return self._tools
    
    def get_system_prompt(self) -> str:
        """
        Build the system prompt for this agent.
        Uses custom prompt from DB if available, otherwise uses template.
        """
        if self.config.system_prompt:
            return self.config.system_prompt
        
        return f"""Eres {self.config.name}, {self.config.role} del departamento de {self.config.department} en la Institución Universitaria EAM.

## Tu Especialización:
{self.config.specialization}

## Tu Objetivo Principal:
{self.config.goal}

## Herramientas Disponibles:
{', '.join(self.config.tools)}

## Instrucciones:
1. Analiza cuidadosamente la solicitud del usuario
2. Usa las herramientas disponibles cuando sea necesario
3. Proporciona respuestas claras y profesionales
4. Si necesitas información de otro departamento, indica que se requiere delegación
5. Para decisiones críticas (cambios financieros, eliminación de datos, etc.), solicita aprobación humana

## Contexto Institucional:
- Institución: Institución Universitaria EAM
- Ubicación: Armenia, Quindío, Colombia
- Sistema: EAM Cognitive OS v2.0.1
"""
    
    async def process(self, state: CognitiveState) -> dict[str, Any]:
        """
        Process a request through this agent.
        
        Args:
            state: Current cognitive state
            
        Returns:
            Updated state dictionary
        """
        start_time = datetime.utcnow()
        
        logger.info(
            f"{self.slot.value} agent processing",
            run_id=str(state.run_id),
            agent=self.slot.value
        )
        
        # Log initial thinking
        state.log_thinking(
            f"Iniciando procesamiento en {self.config.name}...",
            self.slot
        )
        
        try:
            # Build context message
            context = self._build_context_message(state)
            
            # Get LLM with tools bound
            if self.tools:
                llm_with_tools = self.llm.bind_tools(self.tools)
            else:
                llm_with_tools = self.llm
            
            # Build messages
            messages = [
                SystemMessage(content=self.get_system_prompt()),
                HumanMessage(content=context)
            ]
            
            # Add conversation history if available
            for msg in state.messages[-10:]:  # Last 10 messages
                if hasattr(msg, 'content'):
                    messages.append(msg)
            
            # Invoke LLM
            response = await llm_with_tools.ainvoke(messages)
            
            # Process tool calls if any
            if hasattr(response, 'tool_calls') and response.tool_calls:
                response = await self._process_tool_calls(state, response)
            
            # Extract response content
            response_content = response.content if hasattr(response, 'content') else str(response)
            
            # Calculate duration
            duration_ms = int((datetime.utcnow() - start_time).total_seconds() * 1000)
            
            # Log completion
            state.log_decision(
                f"Respuesta generada en {duration_ms}ms",
                self.slot
            )
            
            logger.info(
                f"{self.slot.value} agent completed",
                run_id=str(state.run_id),
                duration_ms=duration_ms
            )
            
            return {
                "current_response": response_content,
                "next_agent": None,  # Can be overridden for delegation
                "is_complete": True,
                "brain_log": state.brain_log,
                "messages": state.messages + [AIMessage(content=response_content)]
            }
            
        except Exception as e:
            logger.error(
                f"{self.slot.value} agent error",
                run_id=str(state.run_id),
                error=str(e)
            )
            state.log_error(f"Error en {self.config.name}: {str(e)}", self.slot)
            
            return {
                "error": str(e),
                "is_complete": True,
                "brain_log": state.brain_log
            }
    
    def _build_context_message(self, state: CognitiveState) -> str:
        """Build the context message for the LLM."""
        parts = [f"Solicitud del usuario: {state.user_message}"]
        
        # Add OKR context if available
        if state.okr_context and state.okr_context.context_summary:
            parts.append(f"\nContexto OKR: {state.okr_context.context_summary}")
        
        # Add retrieved memories if available
        if state.retrieved_memories:
            memory_text = "\n".join([
                f"- {m.get('content', '')[:200]}" 
                for m in state.retrieved_memories[:3]
            ])
            parts.append(f"\nMemoria relevante:\n{memory_text}")
        
        # Add delegation chain context
        if len(state.visited_agents) > 1:
            parts.append(f"\nAgentes previos consultados: {', '.join([a.value if hasattr(a, 'value') else a for a in state.visited_agents[:-1]])}")
        
        return "\n".join(parts)
    
    async def _process_tool_calls(
        self, 
        state: CognitiveState, 
        response: Any
    ) -> Any:
        """
        Process tool calls from the LLM response.
        Implements ReAct pattern with observation logging.
        """
        for tool_call in response.tool_calls:
            tool_name = tool_call.get("name", "unknown")
            tool_args = tool_call.get("args", {})
            
            # Log action
            state.log_action(tool_name, tool_args, self.slot)
            
            # Find and execute tool
            tool = next((t for t in self.tools if t.name == tool_name), None)
            if tool:
                try:
                    result = await tool.ainvoke(tool_args)
                    state.log_observation(
                        f"Resultado de {tool_name}",
                        tool_name=tool_name,
                        tool_output=result,
                        agent=self.slot
                    )
                except Exception as e:
                    state.log_error(f"Error en {tool_name}: {str(e)}", self.slot)
            else:
                state.log_error(f"Herramienta no encontrada: {tool_name}", self.slot)
        
        # Continue conversation with tool results
        # (In a full implementation, this would loop until no more tool calls)
        return response
