"""Especificación compartida de los supuestos económicos de las palancas.

Es la única fuente de los costos que usan el análisis guiado (`model.py`, notebook y tablero
«Planta de ejemplo») y el diagnóstico genérico (`diagnose.py`, modo «Tus datos»). Con los mismos
supuestos, el costo de cada palanca se calcula con las mismas funciones en los dos recorridos.

Todos los valores son supuestos de una planta sintética, no datos de una empresa.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass

import pandas as pd

from .config import PM_COST_MXN, SUPPLIER_C_DISCOUNT, TRAINING_COST_MXN

ALCANCE_INCERTIDUMBRE = (
    "P10–P90 por simulación de los coeficientes del GLM (β ~ Normal(β̂, Σ̂)): solo incertidumbre de "
    "parámetros. No incluye la incertidumbre de la especificación del modelo, de los supuestos de costo "
    "ni de la causalidad. En la planta sintética, los efectos fueron sembrados por el generador.")


@dataclass(frozen=True)
class Supuestos:
    """Supuestos económicos de las palancas (MXN). Ninguno es un costo observado en una empresa."""
    costo_preventivo_mxn: float = PM_COST_MXN                  # un preventivo adicional
    costo_induccion_por_operador_mxn: float = TRAINING_COST_MXN  # inducción por competencias, por alta
    descuento_proveedor: float = SUPPLIER_C_DISCOUNT           # fracción del material que se deja de ahorrar al cambiar
    brecha_induccion: float = 0.5                              # fracción del efecto de operadores nuevos que cierra la inducción
    n_sims: int = 2000
    seed: int = 7

    def como_tabla(self) -> pd.DataFrame:
        etiquetas = {
            "costo_preventivo_mxn": "Un preventivo adicional (MXN)",
            "costo_induccion_por_operador_mxn": "Inducción por operador nuevo (MXN)",
            "descuento_proveedor": "Descuento de material que se pierde al cambiar de proveedor",
            "brecha_induccion": "Parte del efecto de operadores nuevos que cierra la inducción",
            "n_sims": "Simulaciones de coeficientes",
            "seed": "Semilla de la simulación",
        }
        return pd.DataFrame({"supuesto": [etiquetas[k] for k in asdict(self)], "valor": list(asdict(self).values())})


REFERENCIA = Supuestos()


def costo_preventivos(preventivos_adicionales: float, s: Supuestos) -> float:
    """Costo anual de los preventivos adicionales (puede ser negativo si se hacen menos)."""
    return float(preventivos_adicionales) * s.costo_preventivo_mxn


def costo_induccion(altas_anio: float | None, s: Supuestos) -> float | None:
    """Costo anual del programa de inducción. None si no se conoce el número de altas."""
    return None if altas_anio is None else float(altas_anio) * s.costo_induccion_por_operador_mxn


def costo_cambio_proveedor(compras_material_mxn: float, s: Supuestos) -> float:
    """Descuento que se deja de recibir al mover las compras de un proveedor más barato."""
    return float(compras_material_mxn) * s.descuento_proveedor


def compras_material(prod: pd.DataFrame, catalog: pd.DataFrame, mask) -> float:
    """Material comprado (MXN) en las corridas seleccionadas: piezas producidas × costo de material."""
    material = prod["producto"].map(catalog.set_index("producto")["costo_material_mxn"])
    return float((prod.loc[mask, "piezas_producidas"] * material[mask]).sum())
