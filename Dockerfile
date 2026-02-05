# ============================================================================
# EAM Cognitive OS - Production Dockerfile
# Multi-Agent System for Institución Universitaria EAM
# ============================================================================
# Imagen base: Python 3.11 (versión estable para CrewAI)
# NO usar 3.12+ debido a incompatibilidades con dependencias de CrewAI
# ============================================================================

FROM python:3.11-slim AS base

# Metadata
LABEL maintainer="EAM Cognitive Team"
LABEL version="2.0.1"
LABEL description="Backend cognitivo multi-agente para la IU EAM"

# Prevenir buffering de Python para logs en tiempo real
ENV PYTHONUNBUFFERED=1
ENV PYTHONDONTWRITEBYTECODE=1

# Directorio de trabajo
WORKDIR /app

# ============================================================================
# Builder Stage - Instalar dependencias con caching optimizado
# ============================================================================
FROM base AS builder

# Dependencias del sistema para compilación
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Instalar uv para gestión de dependencias ultrarrápida
RUN pip install uv

# Copiar solo archivos de dependencias primero (cache layer)
COPY requirements.txt pyproject.toml ./

# Crear virtualenv e instalar dependencias con uv
RUN uv venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"
RUN uv pip install -r requirements.txt

# ============================================================================
# Development Stage - Para iteración rápida local
# ============================================================================
FROM base AS development

# Instalar uv globalmente
RUN pip install uv

# Dependencias de desarrollo adicionales
RUN apt-get update && apt-get install -y --no-install-recommends \
    git \
    vim \
    && rm -rf /var/lib/apt/lists/*

# Copiar todo el proyecto
COPY . .

# Instalar dependencias incluyendo dev
RUN uv venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"
RUN uv pip install -r requirements.txt
RUN uv pip install pytest pytest-asyncio httpx

# Usuario no-root
RUN useradd --create-home --shell /bin/bash devuser
RUN chown -R devuser:devuser /app
USER devuser

EXPOSE 8000

# Hot-reload para desarrollo
CMD uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8000} --reload


# ============================================================================
# Production Stage - Imagen final mínima (Last stage = Default)
# ============================================================================
FROM base AS production

# Dependencias de runtime mínimas
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    && rm -rf /var/lib/apt/lists/* \
    && apt-get clean

# Copiar virtualenv del builder
COPY --from=builder /opt/venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"

# Copiar código de la aplicación
COPY app/ ./app/

# Usuario no-root por seguridad
RUN useradd --create-home --shell /bin/bash cognitiveuser
RUN chown -R cognitiveuser:cognitiveuser /app
USER cognitiveuser

# Puerto por defecto para FastAPI
EXPOSE 8000

# Health check dinámico
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD curl -f http://localhost:${PORT:-8000}/health || exit 1

# Comando de inicio - Shell form para expandir $PORT
CMD uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8000} --workers 2
