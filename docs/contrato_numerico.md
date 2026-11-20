# Contrato numérico

Qué cifras de este repositorio deben reproducirse, con qué tolerancia y qué cambio cuenta como falla.
`tests/test_contrato.py` lee las tablas de este documento: si el documento, los datos o el código
divergen, la prueba falla.

Planta sintética (semilla 42). Ninguna cifra es un ahorro observado ni un efecto causal validado.

## Alcance

El contrato protege **solo el escenario de referencia**: los datos de la planta sintética, los supuestos de costo
`REFERENCIA` (`scrap_copq/supuestos.py`), la especificación de referencia del modelo y las cifras que de ellos publica
el README. No restringe otros escenarios económicos: los supuestos que el usuario cambia en el tablero, los datos que
sube en «Tus datos» o un escenario nuevo pueden dar otras cifras, otro umbral u otro orden de palancas sin violar el
contrato. Cambiar el escenario de referencia es legítimo si se documenta en el CHANGELOG y se regeneran juntos la
referencia, este documento y el README.

## Reglas

| Regla | Qué cubre | Criterio |
|---|---|---|
| R1 | Datos de entrada, conteos, umbral, supuestos de costo | Igualdad exacta (SHA-256 y enteros) |
| R2 | Mismo entorno y misma semilla | Dos corridas dan exactamente el mismo escenario de referencia |
| R3 | Otro entorno (otras versiones de numpy, pandas o statsmodels) | Cada cifra publicada queda a ±½ unidad de su último dígito publicado |
| R4 | Decisiones | Falla si cambia el umbral, el orden de las palancas, el signo del P10 o la palanca principal |
| R5 | Las pruebas mismas | No se relajan tolerancias ni aserciones para que una corrida pase |

## Tolerancias fijadas antes de comparar

| Constante | Valor |
|---|---|
| Tolerancia relativa con el JSON de referencia (mismo entorno) | 1e-6 |
| Tolerancia de una cifra publicada en millones con 2 decimales | 0.005 |
| Tolerancia de un porcentaje publicado con 1 decimal | 0.05 |

## Datos de entrada (R1)

Huella SHA-256 con fin de línea `\n` y filas sin el encabezado.

| Archivo | Filas | SHA-256 |
|---|---|---|
| data/raw/altas_operadores.csv | 10 | 6f846ed82f53ad85f1071fc18d541c5435c7a5caeec43cfb345b40583c6f7ac9 |
| data/raw/catalogo_productos.csv | 6 | 9a3807b58f7d2c4507300da46b575e2eebca086d2b467b4bf5437d0310c91d38 |
| data/raw/mantenimientos.csv | 60 | f00462ca0f319e0bfbfca8f5bea0424cf2befbc206c8ce4adaffce2809534b88 |
| data/raw/produccion_turnos.csv | 2760 | 8711fb6e21d9d5dd3a7fccdfc25552f30db668e8dc456dc571797f704341419c |
| data/raw/reclamos_cliente.csv | 8 | 731bf4f6344944330c3e642b152b9699ad7a328d63869b07394516e6fc493f09 |
| data/raw/scrap_por_defecto.csv | 10302 | 78f650b7747faaa436074913278ca1e9ec72e4afee1f7342dd9eb2ffe37c3bc7 |
| data/processed/altas_operadores.csv | 10 | 6f846ed82f53ad85f1071fc18d541c5435c7a5caeec43cfb345b40583c6f7ac9 |
| data/processed/catalogo_productos.csv | 6 | 9a3807b58f7d2c4507300da46b575e2eebca086d2b467b4bf5437d0310c91d38 |
| data/processed/mantenimientos.csv | 60 | f00462ca0f319e0bfbfca8f5bea0424cf2befbc206c8ce4adaffce2809534b88 |
| data/processed/produccion_turnos.csv | 2751 | e79d87644d1f0c45b3dea84aaae358f8bbd6af7992a60b08d14eefa38cf108c3 |
| data/processed/reclamos_cliente.csv | 8 | 731bf4f6344944330c3e642b152b9699ad7a328d63869b07394516e6fc493f09 |
| data/processed/scrap_por_defecto.csv | 10292 | 07e5d5ab3f379f0754294c3153cb2e27534f172414cf72d829a40d084993c6ec |

## Decisiones (R4)

| Decisión | Valor |
|---|---|
| Umbral de horas desde el preventivo | 170 |
| Orden de las palancas por ahorro neto P50 | mantenimiento > proveedor > induccion |
| Palanca principal | mantenimiento |
| P10 del ahorro neto de cada palanca | positivo |
| Participación de la palanca principal en el total | más de 80 % |

## Equivalencia de entornos

El JSON de referencia y las cifras del README se generaron y verificaron con:

| Entorno | Python | numpy | pandas | statsmodels | scipy |
|---|---|---|---|---|---|
| Verificación local (20 nov 2026) | 3.13.18 | 2.5.5 | 3.1.1 | 0.15.0 | 1.18.1 |
| CI (`.github/workflows/pruebas.yml`) | 3.12 | según `requirements.txt` (mínimos) | | | |

Entre entornos se exige R3 y R4, no igualdad de bits. Si una versión nueva mueve una cifra publicada más
allá de su tolerancia o cambia una decisión, la corrida falla y el cambio se documenta en el CHANGELOG
antes de regenerar la referencia con `python -m scrap_copq.conciliacion --escribir`.

## Qué detecta (demostración con infracciones controladas)

Cada infracción se aplicó en una copia desechable del repositorio y `tests/test_contrato.py` falló:

| Infracción | Regla que la detecta |
|---|---|
| Cambiar una fila de `data/raw/produccion_turnos.csv` | R1 |
| Publicar 1.04 M en lugar de 1.03 M en la tabla del README | R3 |
| Fijar el umbral de referencia en 160 h en `conciliacion.py` | R3, R4 |
| Relajar la tolerancia de `tests/test_conciliacion.py` a 1e-2 | R5 |
