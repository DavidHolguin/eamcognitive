"""
SNIES Tools - Mock implementations for Ministry of Education reporting
Sistema Nacional de Información de Educación Superior
"""

from typing import Any, Optional
from datetime import datetime
import random

from langchain_core.tools import BaseTool
from pydantic import BaseModel, Field


class ReporteSNIESInput(BaseModel):
    """Input for SNIES report generation."""
    tipo_reporte: str = Field(description="Tipo de reporte SNIES (matricula, graduados, docentes, infraestructura)")
    periodo: str = Field(description="Periodo del reporte")


class GenerarReporteSNIESTool(BaseTool):
    """Genera reportes para SNIES."""
    
    name: str = "generar_reporte_snies"
    description: str = "Genera reportes requeridos por el Sistema Nacional de Información de Educación Superior (SNIES)."
    args_schema: type[BaseModel] = ReporteSNIESInput
    
    def _run(self, tipo_reporte: str, periodo: str) -> dict[str, Any]:
        """Simulated SNIES report generation."""
        base_report = {
            "tipo": tipo_reporte,
            "periodo": periodo,
            "institucion": {
                "codigo_ies": "2815",
                "nombre": "Institución Universitaria EAM",
                "nit": "890001040",
                "municipio": "Armenia",
                "departamento": "Quindío"
            },
            "fecha_generacion": datetime.now().isoformat(),
            "estado": "generado"
        }
        
        if tipo_reporte.lower() == "matricula":
            base_report["datos"] = {
                "total_matriculados": random.randint(2800, 3500),
                "por_nivel": {
                    "pregrado": random.randint(2500, 3000),
                    "especializacion": random.randint(150, 250),
                    "maestria": random.randint(50, 100)
                },
                "por_sexo": {
                    "masculino": random.randint(1400, 1800),
                    "femenino": random.randint(1400, 1700)
                },
                "por_estrato": {
                    "1": random.randint(300, 500),
                    "2": random.randint(800, 1200),
                    "3": random.randint(700, 1000),
                    "4": random.randint(200, 400),
                    "5": random.randint(50, 100),
                    "6": random.randint(10, 30)
                },
                "nuevos_primer_semestre": random.randint(400, 600)
            }
        elif tipo_reporte.lower() == "graduados":
            base_report["datos"] = {
                "total_graduados": random.randint(350, 500),
                "por_programa": [
                    {"programa": "Ingeniería de Sistemas", "graduados": random.randint(40, 60)},
                    {"programa": "Administración de Empresas", "graduados": random.randint(50, 80)},
                    {"programa": "Contaduría Pública", "graduados": random.randint(40, 70)},
                    {"programa": "Ingeniería Industrial", "graduados": random.randint(35, 55)},
                    {"programa": "Trabajo Social", "graduados": random.randint(30, 50)}
                ],
                "tiempo_promedio_graduacion": "5.2 años",
                "tasa_empleabilidad": f"{random.randint(75, 90)}%"
            }
        elif tipo_reporte.lower() == "docentes":
            base_report["datos"] = {
                "total_docentes": random.randint(180, 250),
                "por_dedicacion": {
                    "tiempo_completo": random.randint(60, 90),
                    "medio_tiempo": random.randint(30, 50),
                    "catedra": random.randint(80, 120)
                },
                "por_formacion": {
                    "doctorado": random.randint(15, 30),
                    "maestria": random.randint(80, 120),
                    "especializacion": random.randint(40, 60),
                    "pregrado": random.randint(20, 40)
                },
                "relacion_estudiante_docente": f"{random.randint(15, 25)}:1"
            }
        else:
            base_report["datos"] = {
                "mensaje": "Tipo de reporte no especificado, datos genéricos generados",
                "registros_procesados": random.randint(1000, 5000)
            }
        
        return base_report
    
    async def _arun(self, tipo_reporte: str, periodo: str) -> dict[str, Any]:
        return self._run(tipo_reporte, periodo)
