"""
EAM Cognitive OS - FastAPI Main Entrypoint
Sistema Operativo Cognitivo para la Institución Universitaria EAM
Armenia, Quindío, Colombia
"""

from contextlib import asynccontextmanager
from datetime import datetime
from typing import Any

import structlog
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app import __version__
from app.config import get_settings
from app.api.routes import chat, agents, runs, hitl, memory, pdi
from app.api.websocket import router as websocket_router

# Configure structured logging
structlog.configure(
    processors=[
        structlog.stdlib.filter_by_level,
        structlog.stdlib.add_logger_name,
        structlog.stdlib.add_log_level,
        structlog.stdlib.PositionalArgumentsFormatter(),
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.processors.StackInfoRenderer(),
        structlog.processors.format_exc_info,
        structlog.processors.UnicodeDecoder(),
        structlog.processors.JSONRenderer()
    ],
    wrapper_class=structlog.stdlib.BoundLogger,
    context_class=dict,
    logger_factory=structlog.stdlib.LoggerFactory(),
    cache_logger_on_first_use=True,
)

logger = structlog.get_logger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan handler."""
    settings = get_settings()
    
    logger.info(
        "EAM Cognitive OS starting",
        version=__version__,
        app_name=settings.app_name,
        debug=settings.debug
    )
    
    # Pre-compile the cognitive graph
    from app.core.graph import get_cognitive_graph
    get_cognitive_graph()
    logger.info("Cognitive graph compiled")
    
    yield
    
    logger.info("EAM Cognitive OS shutting down")


# Create FastAPI app
settings = get_settings()

app = FastAPI(
    title=settings.app_name,
    description="""
Sistema Operativo Cognitivo para la Institución Universitaria EAM.

## Características

- 🤖 **Multi-Agent System**: 5 agentes departamentales especializados
- 🧠 **LangGraph**: Control de flujo determinista
- 💾 **Brain Log**: Persistencia del "pensamiento" de agentes
- 🎨 **GenUI**: Componentes de UI generativos
- ✅ **HITL**: Human-in-the-Loop para decisiones críticas

## Agentes Disponibles

- 🎓 **Admisiones**: Matrículas y SIGEAM
- 💰 **Finanzas**: Cartera y SNIES
- 📊 **Retención**: Alertas de deserción
- ✍️ **Comunicaciones**: Contenido institucional
- ⚙️ **TIC**: Infraestructura tecnológica
    """,
    version=__version__,
    lifespan=lifespan,
    docs_url="/docs",
    redoc_url="/redoc"
)

# Configure CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ─────────────────────────────────────────────────────────────────────────────
# Request Logging Middleware
# ─────────────────────────────────────────────────────────────────────────────

@app.middleware("http")
async def log_requests(request: Request, call_next):
    """Log all HTTP requests."""
    start_time = datetime.utcnow()
    
    response = await call_next(request)
    
    duration_ms = int((datetime.utcnow() - start_time).total_seconds() * 1000)
    
    logger.info(
        "HTTP request",
        method=request.method,
        path=request.url.path,
        status_code=response.status_code,
        duration_ms=duration_ms,
        client=request.client.host if request.client else "unknown"
    )
    
    return response


# ─────────────────────────────────────────────────────────────────────────────
# Exception Handlers
# ─────────────────────────────────────────────────────────────────────────────

@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    """Handle all unhandled exceptions."""
    logger.error(
        "Unhandled exception",
        path=request.url.path,
        method=request.method,
        error=str(exc),
        exc_info=True
    )
    
    return JSONResponse(
        status_code=500,
        content={
            "error": "Error interno del servidor",
            "detail": str(exc) if settings.debug else "Contacte al administrador"
        }
    )


# ─────────────────────────────────────────────────────────────────────────────
# Include Routers
# ─────────────────────────────────────────────────────────────────────────────

app.include_router(chat.router, prefix="/api")
app.include_router(agents.router, prefix="/api")
app.include_router(runs.router, prefix="/api")
app.include_router(hitl.router, prefix="/api")
app.include_router(memory.router, prefix="/api")
app.include_router(pdi.router, prefix="/api")
app.include_router(websocket_router)


# ─────────────────────────────────────────────────────────────────────────────
# Health Check Endpoints
# ─────────────────────────────────────────────────────────────────────────────

@app.get("/health", tags=["Health"])
async def health_check() -> dict[str, Any]:
    """Basic health check."""
    return {
        "status": "healthy",
        "version": __version__,
        "timestamp": datetime.utcnow().isoformat()
    }


@app.get("/health/ready", tags=["Health"])
async def readiness_check() -> dict[str, Any]:
    """
    Readiness check - verifies all dependencies.
    Returns 200 if ready to accept traffic.
    """
    from app.db.supabase import get_supabase_client
    
    checks = {
        "database": False,
        "cognitive_graph": False
    }
    
    # Check Supabase connection
    try:
        client = get_supabase_client()
        client.table("agents").select("id").limit(1).execute()
        checks["database"] = True
    except Exception as e:
        logger.warning("Database health check failed", error=str(e))
    
    # Check cognitive graph
    try:
        from app.core.graph import get_cognitive_graph
        graph = get_cognitive_graph()
        checks["cognitive_graph"] = graph is not None
    except Exception as e:
        logger.warning("Cognitive graph health check failed", error=str(e))
    
    all_healthy = all(checks.values())
    
    return JSONResponse(
        status_code=200 if all_healthy else 503,
        content={
            "status": "ready" if all_healthy else "not_ready",
            "checks": checks,
            "version": __version__,
            "timestamp": datetime.utcnow().isoformat()
        }
    )


@app.get("/", tags=["Root"])
async def root() -> dict[str, Any]:
    """Root endpoint with API info."""
    return {
        "name": settings.app_name,
        "version": __version__,
        "institution": settings.institution_name,
        "location": settings.institution_location,
        "docs": "/docs",
        "health": "/health"
    }


# ─────────────────────────────────────────────────────────────────────────────
# Run with Uvicorn (development)
# ─────────────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "app.main:app",
        host="0.0.0.0",
        port=8000,
        reload=settings.debug
    )
