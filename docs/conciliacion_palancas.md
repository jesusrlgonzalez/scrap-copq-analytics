# Conciliación de las palancas de ahorro entre el análisis guiado y el diagnóstico genérico

**Planta sintética (semilla 42).** Ninguna cifra es un ahorro observado en una empresa ni un efecto causal validado.

## 1. Dos recorridos, una especificación de supuestos

| Recorrido | Dónde se usa | Modelo | Supuestos de costo |
|---|---|---|---|
| **Análisis guiado** | Notebook, README, tablero «Planta de ejemplo» | `model.py`: efectos de operadores nuevos por línea, humedad, cambio de modelo; umbral con rejilla 80–240 h | `supuestos.REFERENCIA` |
| **Diagnóstico genérico** | Modo «Tus datos», reporte 8D | `diagnose.py`: especificación automática, sin humedad ni cambio de modelo; umbral con rejilla por cuantiles | Los mismos (`supuestos.Supuestos`), editables en la interfaz |

Los costos de las palancas se calculan con las mismas funciones de [`scrap_copq/supuestos.py`](../scrap_copq/supuestos.py) en los dos recorridos:
- `costo_preventivos`;
- `costo_induccion` (número de altas × costo por operador);
- `costo_cambio_proveedor` (descuento perdido × material comprado).

Si falta el número de altas, el costo de la inducción queda marcado como **no capturado**; antes se tomaba como cero sin aviso.

## 2. Escenario de referencia

[`reports/referencia_palancas.json`](../reports/referencia_palancas.json) se regenera con `python -m scrap_copq.conciliacion --escribir`. Fija estos valores:
- Umbral de 170 h.
- Ahorro neto P50 de 1,228,540 MXN al año, el 14.5 % del COPQ de 8,459,560 MXN.
- Detalle por palanca: mantenimiento 1,026,870, inducción 77,786 y proveedor 123,884.

Las pruebas exigen que el notebook, el tablero (con sus valores iniciales), el README y el JSON coincidan.

## 3. Puente: de 1,228,540 a 1,344,244 MXN

Diagnóstico genérico sobre la plantilla de ejemplo, con los mismos supuestos que la referencia: 10 altas y 201,520 MXN de reclamos por grieta atribuidos al proveedor que se mueve. Cada paso se recalcula con `conciliacion.puente()`.

| Paso | Palanca | MXN | Cómo se verifica |
|---|---|---:|---|
| Referencia | — | 1,228,540 | JSON |
| Umbral de 170 h → 160 h | Mantenimiento | +37,113 | Análisis guiado con umbral de 160 h. Las devianzas de 160 y 170 h difieren en ≈ 2 unidades en ambos modelos, así que cada especificación inclina el empate a un lado |
| Fórmula de preventivos adicionales y anualización (365/364) | Mantenimiento | +3,559 | Residuo frente al paso anterior. El ahorro bruto coincide al 0.1 % (1,159,353 frente a 1,158,258); la diferencia está en cómo se cuentan los preventivos actuales |
| Efecto común de operadores nuevos (OR 1.19) en vez de efectos por línea (1.10 / 1.12 / 1.34) | Inducción | +8,637 | Análisis guiado con `Especificacion(operadores="comun")` |
| Sin humedad en el modelo | Inducción | +60,813 | Además, `humedad=False`. Es sesgo por variable omitida: OR 1.19 → 1.25 |
| Sin cambio de modelo | Inducción | +5,220 | Además, `cambio_modelo=False`: OR 1.258, el mismo que el diagnóstico genérico |
| Residuo (turnos y anualización) | Inducción | +557 | Lo que queda sin explicar: el 0.05 % de la referencia |
| Referencia B en vez de A y anualización | Proveedor | −196 | A y B tienen el mismo efecto (OR 1.001, p = 0.95); C solo surte a L1 |
| **Diagnóstico genérico** | — | **1,344,244** | +9.4 % sobre la referencia |

## 4. Qué cambia con los supuestos por omisión del modo «Tus datos»

| Supuesto | Valor por omisión | Efecto en la planta de ejemplo |
|---|---|---|
| Altas de operadores al año | Sin capturar | La inducción se reporta bruta (≈ 303 mil MXN) con aviso de costo no capturado: es una cota superior |
| Reclamos atribuidos al proveedor | 0 | La palanca de proveedor da ≈ −78 mil MXN. Solo paga su costo si se atribuyen a C los reclamos por grieta, cosa que el análisis guiado hace como supuesto declarado |

## 5. Límites

- **Intervalo P10–P90:** solo cubre la incertidumbre de los parámetros. No incluye la de la especificación (la diferencia de este puente es un ejemplo), la de los costos ni la causal.
- **Efectos sembrados:** los efectos los sembró el generador. Que el modelo los recupere demuestra el método, no la eficacia en una planta real.
- **Validación:** para afirmar un ahorro en una planta real hacen falta datos autorizados y un piloto con medición antes y después (`docs/MVP_PILOTO.md`).
