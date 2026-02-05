"""
Cartera Tools - Mock implementations for financial portfolio management
"""

from typing import Any, Optional
from datetime import datetime
import random

from langchain_core.tools import BaseTool
from pydantic import BaseModel, Field


class ConsultarCarteraInput(BaseModel):
    """Input for portfolio lookup."""
    documento: Optional[str] = Field(default=None, description="Documento del estudiante")
    programa: Optional[str] = Field(default=None, description="Programa académico")


class ConsultarCarteraTool(BaseTool):
    """Consulta estado de cartera estudiantil."""
    
    name: str = "consultar_cartera"
    description: str = "Consulta el estado de cartera de un estudiante o programa."
    args_schema: type[BaseModel] = ConsultarCarteraInput
    
    def _run(self, documento: Optional[str] = None, programa: Optional[str] = None) -> dict[str, Any]:
        """Simulated portfolio lookup."""
        if documento:
            # Individual student
            return {
                "tipo": "individual",
                "documento": documento,
                "nombre": "Juan Carlos Pérez López",
                "cartera": {
                    "total_deuda": random.randint(0, 5000000),
                    "vencida": random.randint(0, 2000000),
                    "al_dia": random.randint(0, 3000000),
                    "ultimo_pago": "2025-01-15",
                    "monto_ultimo_pago": 1500000,
                    "estado": random.choice(["Al día", "En mora", "Acuerdo de pago"])
                }
            }
        else:
            # Program or global
            return {
                "tipo": "consolidado",
                "programa": programa or "Todos",
                "cartera": {
                    "total": random.randint(800000000, 1200000000),
                    "corriente": random.randint(500000000, 700000000),
                    "vencida_30": random.randint(50000000, 100000000),
                    "vencida_60": random.randint(30000000, 80000000),
                    "vencida_90_mas": random.randint(100000000, 200000000),
                    "provision": random.randint(80000000, 120000000)
                },
                "indicadores": {
                    "tasa_morosidad": f"{random.randint(8, 15)}%",
                    "dias_promedio_mora": random.randint(25, 45),
                    "recuperacion_mes": random.randint(50000000, 150000000)
                }
            }
    
    async def _arun(self, documento: Optional[str] = None, programa: Optional[str] = None) -> dict[str, Any]:
        return self._run(documento, programa)


class AnalizarMorosidadInput(BaseModel):
    """Input for delinquency analysis."""
    periodo: str = Field(description="Periodo a analizar")
    segmento: Optional[str] = Field(default=None, description="Segmento específico")


class AnalizarMorosidadTool(BaseTool):
    """Analiza patrones de morosidad."""
    
    name: str = "analizar_morosidad"
    description: str = "Analiza patrones y tendencias de morosidad estudiantil."
    args_schema: type[BaseModel] = AnalizarMorosidadInput
    
    def _run(self, periodo: str, segmento: Optional[str] = None) -> dict[str, Any]:
        """Simulated delinquency analysis."""
        return {
            "periodo": periodo,
            "segmento": segmento or "General",
            "analisis": {
                "estudiantes_morosos": random.randint(200, 400),
                "porcentaje_poblacion": f"{random.randint(8, 15)}%",
                "monto_en_mora": random.randint(150000000, 300000000),
                "edad_promedio_deuda": f"{random.randint(60, 120)} días"
            },
            "segmentacion_mora": {
                "30_dias": {"cantidad": random.randint(100, 150), "monto": random.randint(30000000, 50000000)},
                "60_dias": {"cantidad": random.randint(50, 80), "monto": random.randint(40000000, 70000000)},
                "90_dias": {"cantidad": random.randint(30, 60), "monto": random.randint(50000000, 100000000)},
                "mas_90": {"cantidad": random.randint(20, 50), "monto": random.randint(80000000, 150000000)}
            },
            "tendencia": "Mejorando" if random.random() > 0.5 else "Deteriorando",
            "recomendaciones": [
                "Fortalecer cobranza preventiva",
                "Implementar alertas tempranas",
                "Revisar políticas de financiación"
            ]
        }
    
    async def _arun(self, periodo: str, segmento: Optional[str] = None) -> dict[str, Any]:
        return self._run(periodo, segmento)


class GenerarFacturaInput(BaseModel):
    """Input for invoice generation."""
    documento: str = Field(description="Documento del estudiante")
    concepto: str = Field(description="Concepto de facturación")
    valor: int = Field(description="Valor a facturar")


class GenerarFacturaTool(BaseTool):
    """Genera factura para un estudiante."""
    
    name: str = "generar_factura"
    description: str = "Genera una factura para un estudiante. REQUIERE APROBACIÓN HITL."
    args_schema: type[BaseModel] = GenerarFacturaInput
    
    def _run(self, documento: str, concepto: str, valor: int) -> dict[str, Any]:
        """Simulated invoice generation."""
        return {
            "status": "pendiente_aprobacion",
            "mensaje": "Esta operación requiere aprobación humana",
            "factura_borrador": {
                "numero": f"FAC-{datetime.now().strftime('%Y%m%d')}-{random.randint(1000, 9999)}",
                "fecha": datetime.now().isoformat(),
                "documento_estudiante": documento,
                "concepto": concepto,
                "valor": valor,
                "iva": int(valor * 0.19),
                "total": int(valor * 1.19)
            }
        }
    
    async def _arun(self, documento: str, concepto: str, valor: int) -> dict[str, Any]:
        return self._run(documento, concepto, valor)
