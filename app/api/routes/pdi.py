"""
PDI (Plan de Desarrollo Institucional) API Routes
GraphRAG-based strategic alignment system
"""

from datetime import datetime
from typing import Any, Optional
from uuid import UUID
from enum import Enum

import structlog
from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks
from pydantic import BaseModel, Field

from app.db.supabase import get_supabase_admin_client
from app.security.zero_trust import require_auth
from app.core.llm import get_llm_client, generate_embedding

logger = structlog.get_logger(__name__)

router = APIRouter(prefix="/pdi", tags=["PDI - GraphRAG"])


# ─────────────────────────────────────────────────────────────────────────────
# Enums and Models
# ─────────────────────────────────────────────────────────────────────────────

class PDIEntityType(str, Enum):
    MACRO_OBJECTIVE = "macro_objective"
    STRATEGIC_AXIS = "strategic_axis"
    PROGRAM = "program"
    PROJECT = "project"
    INDICATOR = "indicator"
    RESPONSIBLE = "responsible"
    DEPENDENCY = "dependency"
    MISSION = "mission"
    VISION = "vision"


class PDIRelationType(str, Enum):
    CONTRIBUTES_TO = "contributes_to"
    DEPENDS_ON = "depends_on"
    MEASURED_BY = "measured_by"
    ASSIGNED_TO = "assigned_to"
    PART_OF = "part_of"
    ALIGNED_WITH = "aligned_with"
    DERIVES_FROM = "derives_from"


class AlignmentStatus(str, Enum):
    PENDING = "pending"
    ALIGNED = "aligned"
    ORPHAN = "orphan"
    MISALIGNED = "misaligned"
    NEEDS_REVIEW = "needs_review"


class PDIDocumentCreate(BaseModel):
    """Create a new PDI document for processing."""
    title: str
    content: str
    version: str = "1.0"


class PDIDocumentResponse(BaseModel):
    """PDI document response."""
    id: UUID
    title: str
    version: str
    status: str
    entity_count: int
    relation_count: int
    created_at: datetime


class TaskAlignmentRequest(BaseModel):
    """Request to align a task with PDI entities."""
    task_id: UUID
    task_title: str
    task_description: Optional[str] = None


class TaskAlignmentResponse(BaseModel):
    """Task alignment result."""
    task_id: UUID
    alignment_status: str
    alignment_score: float
    key_result_id: Optional[UUID] = None
    pdi_entity_id: Optional[UUID] = None
    ai_justification: str


class SemanticSearchRequest(BaseModel):
    """Semantic search in PDI entities."""
    query: str
    limit: int = Field(default=10, le=50)
    entity_types: Optional[list[PDIEntityType]] = None
    include_relations: bool = False


# ─────────────────────────────────────────────────────────────────────────────
# LLM Extraction Functions
# ─────────────────────────────────────────────────────────────────────────────

EXTRACTION_PROMPT = """Eres un experto en análisis de Planes de Desarrollo Institucional (PDI) universitarios.
Extrae entidades y relaciones del siguiente texto.

Tipos de entidades válidos:
- macro_objective: Objetivo macro o misión institucional
- strategic_axis: Eje estratégico o línea de acción
- program: Programa académico o administrativo
- project: Proyecto específico
- indicator: Indicador de gestión o KPI
- responsible: Persona o dependencia responsable
- dependency: Dependencia o unidad organizacional
- mission: Misión institucional
- vision: Visión institucional

Tipos de relaciones válidos:
- contributes_to: La entidad fuente contribuye al logro de la entidad destino
- depends_on: La entidad fuente depende de la entidad destino
- measured_by: La entidad fuente es medida por el indicador destino
- assigned_to: La entidad fuente está asignada a la entidad destino
- part_of: La entidad fuente es parte de la entidad destino
- aligned_with: Las entidades están alineadas estratégicamente
- derives_from: La entidad fuente se deriva de la entidad destino

Responde SOLO con JSON válido en este formato:
{
  "entities": [
    {"name": "...", "entity_type": "...", "description": "...", "source_text": "..."}
  ],
  "relations": [
    {"source": "nombre_entidad_1", "target": "nombre_entidad_2", "relation_type": "...", "description": "..."}
  ]
}"""


async def extract_entities_and_relations(content: str) -> dict[str, Any]:
    """Extract entities and relations from PDI content using LLM."""
    llm = get_llm_client()
    
    kwargs = {
        "model": "gpt-4o",
        "messages": [
            {"role": "system", "content": EXTRACTION_PROMPT},
            {"role": "user", "content": content[:12000]}  # Limit content size
        ],
        "temperature": 0.2,
        "response_format": {"type": "json_object"}
    }
    
    try:
        response = await llm.chat.completions.create(**kwargs)
        content = response.choices[0].message.content
    except Exception as e:
        logger.warning("PDI extraction failed with response_format, trying without it", error=str(e))
        # Fallback: remove response_format and ensure JSON request in prompt
        del kwargs["response_format"]
        kwargs["messages"][-1]["content"] += "\n\nResponde únicamente en formato JSON válido."
        
        response = await llm.chat.completions.create(**kwargs)
        content = response.choices[0].message.content
    
    import json
    return json.loads(content)


ALIGNMENT_PROMPT = """Eres "El Estratega", un agente experto en alineación estratégica institucional.

Tu tarea es evaluar si una tarea contribuye causalmente a un Resultado Clave (KR) y a los objetivos del PDI.

Evalúa la alineación considerando:
1. Contribución directa: ¿La tarea ayuda directamente a lograr el KR?
2. Contribución indirecta: ¿La tarea habilita o prepara condiciones para el KR?
3. Relevancia temática: ¿El tema de la tarea está relacionado con el objetivo?

Responde SOLO con JSON válido:
{
  "alignment_score": 0.0-1.0,
  "status": "aligned|misaligned|orphan|needs_review",
  "justification": "Explicación de la evaluación",
  "suggested_kr_id": "UUID del KR más relevante o null",
  "suggested_pdi_entity_id": "UUID de la entidad PDI más relevante o null"
}"""


async def evaluate_task_alignment(
    task_title: str, 
    task_description: str,
    okrs: list[dict],
    pdi_entities: list[dict]
) -> dict[str, Any]:
    """Evaluate task alignment with OKRs and PDI using LLM."""
    llm = get_llm_client()
    
    context = f"""
TAREA:
Título: {task_title}
Descripción: {task_description or 'Sin descripción'}

OKRs DISPONIBLES:
{[f"- {okr['title']} (KRs: {okr.get('key_results', [])})" for okr in okrs]}

ENTIDADES PDI DISPONIBLES:
{[f"- {e['name']} ({e['entity_type']}): {e['description']}" for e in pdi_entities[:20]]}
"""
    
    kwargs = {
        "model": "gpt-4o",
        "messages": [
            {"role": "system", "content": ALIGNMENT_PROMPT},
            {"role": "user", "content": context}
        ],
        "temperature": 0.3,
        "response_format": {"type": "json_object"}
    }
    
    try:
        response = await llm.chat.completions.create(**kwargs)
        content = response.choices[0].message.content
    except Exception as e:
        logger.warning("Task alignment failed with response_format, trying without it", error=str(e))
        del kwargs["response_format"]
        kwargs["messages"][-1]["content"] += "\n\nResponde únicamente en formato JSON válido."
        
        response = await llm.chat.completions.create(**kwargs)
        content = response.choices[0].message.content
    
    import json
    return json.loads(content)


# ─────────────────────────────────────────────────────────────────────────────
# Background Processing
# ─────────────────────────────────────────────────────────────────────────────

async def process_pdi_document(document_id: str):
    """Background task to process PDI document."""
    client = get_supabase_admin_client()
    
    try:
        # Get document
        doc = client.table("pdi_documents").select("*").eq("id", document_id).single().execute()
        if not doc.data:
            logger.error("Document not found for processing", document_id=document_id)
            return
        
        # Update status: processing
        client.table("pdi_documents").update({
            "status": "processing",
            "processing_log": (doc.data.get("processing_log") or []) + [
                {"timestamp": datetime.utcnow().isoformat(), "message": "Iniciando procesamiento"}
            ]
        }).eq("id", document_id).execute()
        
        # Extract entities and relations
        client.table("pdi_documents").update({"status": "extracting"}).eq("id", document_id).execute()
        
        extraction = await extract_entities_and_relations(doc.data.get("content", ""))
        entities = extraction.get("entities", [])
        relations = extraction.get("relations", [])
        
        logger.info(
            "Extraction complete",
            document_id=document_id,
            entities=len(entities),
            relations=len(relations)
        )
        
        # Build graph
        client.table("pdi_documents").update({"status": "building_graph"}).eq("id", document_id).execute()
        
        # Create root community
        community = client.table("pdi_communities").insert({
            "document_id": document_id,
            "name": doc.data.get("title", "PDI"),
            "level": 1,
            "metadata": {"entity_count": len(entities)}
        }).execute()
        
        community_id = community.data[0]["id"] if community.data else None
        
        # Insert entities with embeddings
        entity_map = {}  # name -> id
        for entity in entities:
            embedding_text = f"{entity['name']}: {entity.get('description', '')}"
            embedding = await generate_embedding(embedding_text)
            
            result = client.table("pdi_entities").insert({
                "document_id": document_id,
                "community_id": community_id,
                "name": entity["name"],
                "entity_type": entity["entity_type"],
                "description": entity.get("description", ""),
                "source_text": entity.get("source_text", ""),
                "embedding": embedding,
                "metadata": {}
            }).execute()
            
            if result.data:
                entity_map[entity["name"]] = result.data[0]["id"]
        
        # Insert relations
        relation_count = 0
        for rel in relations:
            source_id = entity_map.get(rel["source"])
            target_id = entity_map.get(rel["target"])
            
            if source_id and target_id:
                client.table("pdi_entity_relations").insert({
                    "source_entity_id": source_id,
                    "target_entity_id": target_id,
                    "relation_type": rel["relation_type"],
                    "description": rel.get("description", ""),
                    "weight": 1.0
                }).execute()
                relation_count += 1
        
        # Generate community summary
        entity_names = [e["name"] for e in entities]
        summary_text = f"Este documento PDI contiene {len(entities)} entidades estratégicas relacionadas con: {', '.join(entity_names[:10])}"
        summary_embedding = await generate_embedding(summary_text)
        
        client.table("pdi_community_summaries").insert({
            "community_id": community_id,
            "summary_text": summary_text,
            "key_themes": entity_names[:5],
            "embedding": summary_embedding
        }).execute()
        
        # Mark as ready
        client.table("pdi_documents").update({
            "status": "ready",
            "entity_count": len(entities),
            "relation_count": relation_count,
            "processing_log": (doc.data.get("processing_log") or []) + [
                {"timestamp": datetime.utcnow().isoformat(), "message": f"Completado: {len(entities)} entidades, {relation_count} relaciones"}
            ]
        }).eq("id", document_id).execute()
        
        logger.info(
            "PDI document processing complete",
            document_id=document_id,
            entities=len(entities),
            relations=relation_count
        )
        
    except Exception as e:
        logger.error("PDI processing failed", document_id=document_id, error=str(e))
        client.table("pdi_documents").update({
            "status": "error",
            "processing_log": [{"timestamp": datetime.utcnow().isoformat(), "message": f"Error: {str(e)}"}]
        }).eq("id", document_id).execute()


# ─────────────────────────────────────────────────────────────────────────────
# API Endpoints
# ─────────────────────────────────────────────────────────────────────────────

@router.get("/documents")
async def list_documents(
    user=Depends(require_auth())
) -> dict[str, Any]:
    """List all PDI documents."""
    client = get_supabase_admin_client()
    
    result = client.table("pdi_documents").select(
        "id, title, version, status, entity_count, relation_count, created_at, updated_at"
    ).order("created_at", desc=True).execute()
    
    return {
        "documents": result.data or [],
        "total": len(result.data) if result.data else 0
    }


@router.post("/documents")
async def create_document(
    document: PDIDocumentCreate,
    background_tasks: BackgroundTasks,
    user=Depends(require_auth())
) -> dict[str, Any]:
    """Create and process a new PDI document."""
    client = get_supabase_admin_client()
    
    # Create document record
    result = client.table("pdi_documents").insert({
        "title": document.title,
        "content": document.content,
        "version": document.version,
        "status": "uploading",
        "uploaded_by": str(user.id),
        "processing_log": [{"timestamp": datetime.utcnow().isoformat(), "message": "Documento creado"}]
    }).execute()
    
    if not result.data:
        raise HTTPException(status_code=500, detail="Error creando documento")
    
    document_id = result.data[0]["id"]
    
    # Start background processing
    background_tasks.add_task(process_pdi_document, document_id)
    
    logger.info("PDI document created", document_id=document_id, title=document.title)
    
    return {
        "id": document_id,
        "title": document.title,
        "status": "uploading",
        "message": "Documento creado. El procesamiento iniciará en segundo plano.",
        "entities": [],
        "relations": []
    }


@router.get("/documents/{document_id}")
async def get_document(
    document_id: UUID,
    user=Depends(require_auth())
) -> dict[str, Any]:
    """Get a PDI document with its entities and relations."""
    client = get_supabase_admin_client()
    
    doc = client.table("pdi_documents").select("*").eq("id", str(document_id)).single().execute()
    
    if not doc.data:
        raise HTTPException(status_code=404, detail="Documento no encontrado")
    
    # Get entities
    entities = client.table("pdi_entities").select(
        "id, name, entity_type, description, metadata"
    ).eq("document_id", str(document_id)).execute()
    
    # Get relations
    entity_ids = [e["id"] for e in (entities.data or [])]
    relations = []
    if entity_ids:
        relations_result = client.table("pdi_entity_relations").select(
            "id, source_entity_id, target_entity_id, relation_type, description"
        ).in_("source_entity_id", entity_ids).execute()
        relations = relations_result.data or []
    
    return {
        "document": doc.data,
        "entities": entities.data or [],
        "relations": relations
    }


@router.get("/entities")
async def list_entities(
    document_id: Optional[UUID] = None,
    entity_type: Optional[PDIEntityType] = None,
    limit: int = 50,
    user=Depends(require_auth())
) -> dict[str, Any]:
    """List PDI entities with optional filters."""
    client = get_supabase_admin_client()
    
    query = client.table("pdi_entities").select(
        "id, name, entity_type, description, document_id, community_id, metadata, created_at"
    )
    
    if document_id:
        query = query.eq("document_id", str(document_id))
    
    if entity_type:
        query = query.eq("entity_type", entity_type.value)
    
    result = query.limit(limit).execute()
    
    return {
        "entities": result.data or [],
        "total": len(result.data) if result.data else 0
    }


@router.get("/graph")
async def get_graph(
    document_id: Optional[UUID] = None,
    user=Depends(require_auth())
) -> dict[str, Any]:
    """Get PDI graph data for visualization (nodes and edges)."""
    client = get_supabase_admin_client()
    
    # Get entities as nodes
    entities_query = client.table("pdi_entities").select(
        "id, name, entity_type, description"
    )
    if document_id:
        entities_query = entities_query.eq("document_id", str(document_id))
    
    entities = entities_query.execute()
    
    nodes = [
        {
            "id": e["id"],
            "label": e["name"],
            "type": e["entity_type"],
            "data": {"description": e["description"]}
        }
        for e in (entities.data or [])
    ]
    
    # Get relations as edges
    entity_ids = [n["id"] for n in nodes]
    edges = []
    
    if entity_ids:
        relations = client.table("pdi_entity_relations").select(
            "id, source_entity_id, target_entity_id, relation_type, weight"
        ).in_("source_entity_id", entity_ids).execute()
        
        edges = [
            {
                "id": r["id"],
                "source": r["source_entity_id"],
                "target": r["target_entity_id"],
                "type": r["relation_type"],
                "weight": r["weight"]
            }
            for r in (relations.data or [])
        ]
    
    return {
        "nodes": nodes,
        "edges": edges
    }


@router.post("/search")
async def semantic_search(
    request: SemanticSearchRequest,
    user=Depends(require_auth())
) -> dict[str, Any]:
    """Semantic search across PDI entities using vector similarity."""
    client = get_supabase_admin_client()
    
    # Generate query embedding
    query_embedding = await generate_embedding(request.query)
    
    # Vector similarity search using pgvector
    # Note: This requires a database function for vector similarity
    result = client.rpc("match_pdi_entities", {
        "query_embedding": query_embedding,
        "match_threshold": 0.5,
        "match_count": request.limit
    }).execute()
    
    entities = result.data or []
    
    # Filter by entity types if specified
    if request.entity_types:
        type_values = [t.value for t in request.entity_types]
        entities = [e for e in entities if e.get("entity_type") in type_values]
    
    # Include relations if requested
    if request.include_relations and entities:
        entity_ids = [e["id"] for e in entities]
        relations = client.table("pdi_entity_relations").select(
            "*, source:pdi_entities!source_entity_id(name), target:pdi_entities!target_entity_id(name)"
        ).in_("source_entity_id", entity_ids).execute()
        
        return {
            "query": request.query,
            "entities": entities,
            "relations": relations.data or []
        }
    
    return {
        "query": request.query,
        "entities": entities,
        "total": len(entities)
    }


@router.post("/align-task")
async def align_task(
    request: TaskAlignmentRequest,
    user=Depends(require_auth())
) -> TaskAlignmentResponse:
    """
    Evaluate and create alignment between a task and PDI/OKRs.
    This is the "El Estratega" agent endpoint.
    """
    client = get_supabase_admin_client()
    
    # Get available OKRs
    okrs = client.table("objectives").select(
        "id, title, description, key_results(id, description)"
    ).eq("is_active", True).execute()
    
    # Get PDI entities for context
    entities = client.table("pdi_entities").select(
        "id, name, entity_type, description"
    ).limit(30).execute()
    
    # Evaluate alignment with LLM
    alignment = await evaluate_task_alignment(
        task_title=request.task_title,
        task_description=request.task_description or "",
        okrs=okrs.data or [],
        pdi_entities=entities.data or []
    )
    
    # Create alignment record
    alignment_status = alignment.get("status", "needs_review")
    alignment_score = alignment.get("alignment_score", 0.0)
    
    # Find best matching KR if aligned
    # Helper to sanitize UUIDs
    def sanitize_uuid(value: Any) -> Optional[str]:
        if not value:
            return None
        if isinstance(value, str) and value.lower() in ["null", "none", ""]:
            return None
        try:
            # Validate if it's a real UUID
            UUID(str(value))
            return str(value)
        except ValueError:
            return None

    # Find best matching KR if aligned
    key_result_id = sanitize_uuid(alignment.get("suggested_kr_id"))
    pdi_entity_id = sanitize_uuid(alignment.get("suggested_pdi_entity_id"))
    
    # Create task_kr_alignment record
    if alignment_status in ["aligned", "needs_review"]:
        # Get first KR from first objective if no suggestion
        if not key_result_id and okrs.data:
            first_okr = okrs.data[0]
            krs = first_okr.get("key_results", [])
            if krs:
                key_result_id = krs[0]["id"]
        
        if key_result_id:
            client.table("task_kr_alignments").insert({
                "task_id": str(request.task_id),
                "key_result_id": key_result_id,
                "alignment_score": alignment_score,
                "ai_justification": alignment.get("justification", ""),
                "status": alignment_status,
                "pdi_entity_id": pdi_entity_id
            }).execute()
    
    # Update task alignment status
    client.table("tasks").update({
        "alignment_status": alignment_status,
        "alignment_confidence": alignment_score,
        "last_alignment_check": datetime.utcnow().isoformat()
    }).eq("id", str(request.task_id)).execute()
    
    logger.info(
        "Task alignment evaluated",
        task_id=str(request.task_id),
        status=alignment_status,
        score=alignment_score
    )
    
    return TaskAlignmentResponse(
        task_id=request.task_id,
        alignment_status=alignment_status,
        alignment_score=alignment_score,
        key_result_id=key_result_id,
        pdi_entity_id=pdi_entity_id,
        ai_justification=alignment.get("justification", "")
    )


@router.get("/alignment-report")
async def get_alignment_report(
    user=Depends(require_auth())
) -> dict[str, Any]:
    """
    Generate strategic alignment report.
    Shows coverage of PDI by current tasks and identifies gaps.
    """
    client = get_supabase_admin_client()
    
    # Get all PDI entities
    entities = client.table("pdi_entities").select("id, name, entity_type").execute()
    total_entities = len(entities.data) if entities.data else 0
    
    # Get aligned tasks
    alignments = client.table("task_kr_alignments").select(
        "*, tasks(id, title, status), key_results(id, description, objective_id)"
    ).execute()
    
    # Get orphan tasks
    orphan_tasks = client.table("tasks").select(
        "id, title, status, alignment_status"
    ).eq("alignment_status", "orphan").execute()
    
    # Calculate coverage by entity type
    entity_coverage = {}
    if entities.data:
        for e in entities.data:
            etype = e["entity_type"]
            if etype not in entity_coverage:
                entity_coverage[etype] = {"total": 0, "covered": 0}
            entity_coverage[etype]["total"] += 1
    
    aligned_entity_ids = set()
    for a in (alignments.data or []):
        if a.get("pdi_entity_id"):
            aligned_entity_ids.add(a["pdi_entity_id"])
    
    if entities.data:
        for e in entities.data:
            if e["id"] in aligned_entity_ids:
                entity_coverage[e["entity_type"]]["covered"] += 1
    
    # Calculate overall metrics
    covered_entities = len(aligned_entity_ids)
    coverage_percentage = (covered_entities / total_entities * 100) if total_entities > 0 else 0
    
    return {
        "summary": {
            "total_entities": total_entities,
            "covered_entities": covered_entities,
            "coverage_percentage": round(coverage_percentage, 1),
            "total_alignments": len(alignments.data) if alignments.data else 0,
            "orphan_tasks": len(orphan_tasks.data) if orphan_tasks.data else 0
        },
        "coverage_by_type": entity_coverage,
        "orphan_tasks": orphan_tasks.data or [],
        "recent_alignments": (alignments.data or [])[:10]
    }
