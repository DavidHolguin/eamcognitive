#!/bin/bash
set -e

# Configurar puerto por defecto si no existe
PORT=${PORT:-8000}
HOST="0.0.0.0"

echo "🚀 Iniciando EAM Cognitive Backend en $HOST:$PORT"

# Verificar variables críticas (opcional, para debug rápido)
if [ -z "$SUPABASE_URL" ]; then
    echo "⚠️ ADVERTENCIA: SUPABASE_URL no está definida"
fi

# Iniciar Uvicorn con configuración de producción
exec uvicorn app.main:app \
    --host "$HOST" \
    --port "$PORT" \
    --workers 2 \
    --proxy-headers \
    --forwarded-allow-ips "*"
