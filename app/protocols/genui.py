"""
GenUI Protocol - Generative UI component streaming
"""

from typing import Any, AsyncGenerator
from enum import Enum
import json

from pydantic import BaseModel, Field

from app.core.state import GenUIPayload


class GenUIComponent(str, Enum):
    """Available GenUI component types."""
    CARD = "card"
    TABLE = "table"
    CHART = "chart"
    KANBAN = "kanban"
    FORM = "form"
    HITL = "hitl"
    PROGRESS = "progress"
    ALERT = "alert"
    MARKDOWN = "markdown"


class CardPayload(BaseModel):
    """Payload for card component."""
    title: str
    content: str
    icon: str = "📋"
    variant: str = "default"  # default, success, warning, error
    actions: list[dict[str, str]] = Field(default_factory=list)


class TablePayload(BaseModel):
    """Payload for table component."""
    columns: list[dict[str, str]]
    rows: list[dict[str, Any]]
    title: str = ""
    sortable: bool = True


class ChartPayload(BaseModel):
    """Payload for chart component."""
    chart_type: str  # bar, line, pie, area
    data: list[dict[str, Any]]
    x_key: str
    y_keys: list[str]
    title: str = ""


class KanbanPayload(BaseModel):
    """Payload for kanban board component."""
    columns: list[dict[str, Any]]
    title: str = ""


class HITLPayload(BaseModel):
    """Payload for HITL approval component."""
    request_id: str
    reason: str
    context: dict[str, Any]
    proposed_action: str
    expires_at: str


class ProgressPayload(BaseModel):
    """Payload for progress indicator."""
    current: int
    total: int
    label: str = ""
    variant: str = "default"


def create_genui_payload(
    component: GenUIComponent,
    data: dict[str, Any],
    metadata: dict[str, Any] | None = None
) -> GenUIPayload:
    """
    Create a GenUI payload for streaming to frontend.
    
    Args:
        component: The component type
        data: Component-specific data
        metadata: Optional metadata
        
    Returns:
        GenUI payload ready for streaming
    """
    return GenUIPayload(
        component=component.value,
        data=data,
        metadata=metadata
    )


def genui_card(
    title: str,
    content: str,
    icon: str = "📋",
    variant: str = "default",
    actions: list[dict[str, str]] | None = None
) -> GenUIPayload:
    """Create a card component payload."""
    return create_genui_payload(
        GenUIComponent.CARD,
        CardPayload(
            title=title,
            content=content,
            icon=icon,
            variant=variant,
            actions=actions or []
        ).model_dump()
    )


def genui_table(
    columns: list[dict[str, str]],
    rows: list[dict[str, Any]],
    title: str = ""
) -> GenUIPayload:
    """Create a table component payload."""
    return create_genui_payload(
        GenUIComponent.TABLE,
        TablePayload(
            columns=columns,
            rows=rows,
            title=title
        ).model_dump()
    )


def genui_chart(
    chart_type: str,
    data: list[dict[str, Any]],
    x_key: str,
    y_keys: list[str],
    title: str = ""
) -> GenUIPayload:
    """Create a chart component payload."""
    return create_genui_payload(
        GenUIComponent.CHART,
        ChartPayload(
            chart_type=chart_type,
            data=data,
            x_key=x_key,
            y_keys=y_keys,
            title=title
        ).model_dump()
    )


def genui_hitl(
    request_id: str,
    reason: str,
    context: dict[str, Any],
    proposed_action: str,
    expires_at: str
) -> GenUIPayload:
    """Create a HITL approval component payload."""
    return create_genui_payload(
        GenUIComponent.HITL,
        HITLPayload(
            request_id=request_id,
            reason=reason,
            context=context,
            proposed_action=proposed_action,
            expires_at=expires_at
        ).model_dump()
    )


def genui_progress(
    current: int,
    total: int,
    label: str = ""
) -> GenUIPayload:
    """Create a progress indicator payload."""
    return create_genui_payload(
        GenUIComponent.PROGRESS,
        ProgressPayload(
            current=current,
            total=total,
            label=label
        ).model_dump()
    )


async def stream_genui_payloads(
    payloads: list[GenUIPayload]
) -> AsyncGenerator[str, None]:
    """
    Stream GenUI payloads as Server-Sent Events.
    
    Args:
        payloads: List of GenUI payloads to stream
        
    Yields:
        SSE-formatted event strings
    """
    for payload in payloads:
        event_data = json.dumps(payload.model_dump())
        yield f"event: genui\ndata: {event_data}\n\n"
