"""
SIGEAM Tools - Mock implementations for Sistema de Gestión Académica
These are placeholder tools that simulate SIGEAM API responses.
"""

from typing import Any, Optional
from datetime import datetime
import random

from langchain_core.tools import BaseTool
from pydantic import BaseModel, Field


class ConsultarEstudianteInput(BaseModel):
    """Input for student lookup."""
    documento: str = Field(description="Número de documento del estudiante")


class ConsultarEstudianteTool(BaseTool):
    """Consulta información de un estudiante en SIGEAM."""
    
    name: str = "consultar_estudiante"
    description: str = "Busca información de un estudiante por número de documento en el sistema SIGEAM."
    args_schema: type[BaseModel] = ConsultarEstudianteInput
    
    def _run(self, documento: str) -> dict[str, Any]:
        """Simulated student lookup."""
        # Mock response
        return {
            "encontrado": True,
            "estudiante": {
                "documento": documento,
                "nombre": "Juan Carlos Pérez López",
                "programa": "Ingeniería de Sistemas",
                "semestre": 6,
                "promedio": 4.2,
                "estado": "Activo",
                "fecha_ingreso": "2022-01-15",
                "correo": f"juan.perez@eam.edu.co"
            }
        }
    
    async def _arun(self, documento: str) -> dict[str, Any]:
        return self._run(documento)


class EstadisticasMatriculaInput(BaseModel):
    """Input for enrollment statistics."""
    periodo: str = Field(description="Periodo académico (ej: 2025-1)")
    programa: Optional[str] = Field(default=None, description="Programa académico (opcional)")


class ObtenerEstadisticasMatriculaTool(BaseTool):
    """Obtiene estadísticas de matrícula."""
    
    name: str = "obtener_estadisticas_matricula"
    description: str = "Obtiene estadísticas de matrícula para un periodo académico."
    args_schema: type[BaseModel] = EstadisticasMatriculaInput
    
    def _run(self, periodo: str, programa: Optional[str] = None) -> dict[str, Any]:
        """Simulated enrollment statistics."""
        return {
            "periodo": periodo,
            "programa": programa or "Todos",
            "estadisticas": {
                "total_matriculados": random.randint(2500, 3500),
                "nuevos": random.randint(400, 600),
                "reintegros": random.randint(50, 100),
                "transferencias": random.randint(10, 30),
                "crecimiento_vs_anterior": f"+{random.randint(3, 8)}%"
            },
            "por_jornada": {
                "diurna": random.randint(1500, 2000),
                "nocturna": random.randint(800, 1200),
                "virtual": random.randint(200, 400)
            }
        }
    
    async def _arun(self, periodo: str, programa: Optional[str] = None) -> dict[str, Any]:
        return self._run(periodo, programa)


class ReporteCohorteInput(BaseModel):
    """Input for cohort report."""
    cohorte: str = Field(description="Año de cohorte (ej: 2022)")
    programa: Optional[str] = Field(default=None, description="Programa académico (opcional)")


class GenerarReporteCohorteToolmocktool(BaseTool):
    """Genera reporte de cohorte estudiantil."""
    
    name: str = "generar_reporte_cohorte"
    description: str = "Genera un reporte de seguimiento de cohorte estudiantil."
    args_schema: type[BaseModel] = ReporteCohorteInput
    
    def _run(self, cohorte: str, programa: Optional[str] = None) -> dict[str, Any]:
        """Simulated cohort report."""
        total = random.randint(300, 500)
        return {
            "cohorte": cohorte,
            "programa": programa or "Todos los programas",
            "fecha_generacion": datetime.now().isoformat(),
            "resumen": {
                "ingresaron": total,
                "activos": int(total * 0.65),
                "graduados": int(total * 0.15),
                "desertores": int(total * 0.20),
                "tasa_retencion": f"{random.randint(75, 85)}%",
                "promedio_semestres_graduacion": 10.5
            },
            "distribucion_por_estado": {
                "matriculados": int(total * 0.55),
                "en_practica": int(total * 0.08),
                "egresados_sin_titulo": int(total * 0.02),
                "graduados": int(total * 0.15),
                "retiros_voluntarios": int(total * 0.12),
                "desertores": int(total * 0.08)
            }
        }
    
    async def _arun(self, cohorte: str, programa: Optional[str] = None) -> dict[str, Any]:
        return self._run(cohorte, programa)
