"""Modelo explicativo del scrap (GLM binomial) y simulación de ahorro por palanca."""
from dataclasses import dataclass

import numpy as np
import pandas as pd
import statsmodels.api as sm

from .config import SHIFT_HOURS
from .supuestos import (ALCANCE_INCERTIDUMBRE, REFERENCIA, Supuestos, compras_material, costo_cambio_proveedor,
                        costo_induccion, costo_preventivos)

LABELS = {
    "const": "Intercepto (L1)", "L2": "Línea L2", "L3": "Línea L3",
    "nocturno": "Turno nocturno", "cambio_modelo": "Cambio de modelo",
    "nuevos_L1": "Operador nuevo · L1", "nuevos_L2": "Operador nuevo · L2",
    "nuevos_L3": "Operador nuevo · L3", "nuevos_todas": "Operador nuevo · todas las líneas", "exceso_mantto_L2": "+10 h sobre umbral de mantto · L2",
    "proveedor_C": "Lote del proveedor C · L1", "humedad_soldadura": "+10 pts de humedad · soldadura",
}
LEVERS = {
    "mantenimiento": "Mantenimiento preventivo de L2 en el umbral",
    "induccion": "Inducción por competencias a operadores nuevos",
    "proveedor": "Reasignar los lotes del proveedor C al A",
}


@dataclass(frozen=True)
class Especificacion:
    """Especificación del GLM. La de referencia es la del análisis guiado (README y notebook).
    Las variantes sirven para explicar diferencias con el diagnóstico genérico (`conciliacion.py`)."""
    operadores: str = "por_linea"     # "por_linea" o "comun" (un solo efecto para todas las líneas)
    humedad: bool = True
    cambio_modelo: bool = True


REF_ESP = Especificacion()


def design(prod, threshold=160, esp: Especificacion = REF_ESP):
    """Matriz de diseño; cada variable responde a una hipótesis del análisis exploratorio."""
    line = prod["linea"]
    X = pd.DataFrame({
        "const": 1.0,
        "L2": (line == "L2").astype(float),
        "L3": (line == "L3").astype(float),
        "nocturno": (prod["turno"] == "Nocturno").astype(float),
        "cambio_modelo": prod["cambio_modelo"].astype(float),
        **{f"nuevos_{ln}": prod["operadores_nuevos"] * (line == ln) for ln in ("L1", "L2", "L3")},
        "exceso_mantto_L2": (prod["horas_desde_mantto"] - threshold).clip(lower=0) / 10 * (line == "L2"),
        "proveedor_C": ((prod["proveedor_material"] == "C") & (line == "L1")).astype(float),
        "humedad_soldadura": (prod["humedad_rel_pct"] - 55) / 10 * (line != "L1"),
    }, index=prod.index)
    if esp.operadores == "comun":
        cols = ["nuevos_L1", "nuevos_L2", "nuevos_L3"]
        X = X.drop(columns=cols).assign(nuevos_todas=X[cols].sum(axis=1))
    elif esp.operadores != "por_linea":
        raise ValueError(esp.operadores)
    if not esp.humedad:
        X = X.drop(columns="humedad_soldadura")
    if not esp.cambio_modelo:
        X = X.drop(columns="cambio_modelo")
    return X.astype(float)


def fit(prod, threshold=160, esp: Especificacion = REF_ESP):
    """Cuasi-binomial (escala = chi² de Pearson / gl) para no subestimar los errores estándar
    con sobredispersión. Se omiten variables sin variación en la muestra de entrenamiento."""
    X = design(prod, threshold, esp)
    X = X.loc[:, X.ne(0).any()]
    n = prod["piezas_producidas"]
    res = sm.GLM(prod["piezas_scrap"] / n, X, family=sm.families.Binomial(),
                 var_weights=n).fit(scale="X2")
    res.especificacion = esp
    return res


def _exog(res, prod, threshold):
    return design(prod, threshold, getattr(res, "especificacion", REF_ESP))[res.model.exog_names]


def find_threshold(prod, grid=range(80, 241, 10), esp: Especificacion = REF_ESP):
    """Umbral de horas desde mantenimiento que minimiza la devianza."""
    dev = pd.Series({t: fit(prod, t, esp).deviance for t in grid}, name="devianza")
    return int(dev.idxmin()), dev


def odds_ratios(res):
    ci = res.conf_int()
    out = pd.DataFrame({"odds_ratio": np.exp(res.params), "ic95_inf": np.exp(ci[0]),
                        "ic95_sup": np.exp(ci[1]), "p_valor": res.pvalues})
    out.index = [LABELS.get(i, i) for i in out.index]
    return out.drop(index=LABELS["const"])


def predict_rate(res, prod, threshold=160):
    return pd.Series(res.predict(_exog(res, prod, threshold)), index=prod.index)


def holdout(prod, cutoff="2025-10-01", threshold=160):
    """Entrena con ene–sep y evalúa oct–dic contra dos modelos base: promedio por línea y por línea × banda de 50 h desde el mantenimiento."""
    train, test = prod[prod["fecha"] < cutoff], prod[prod["fecha"] >= cutoff]
    res = fit(train, threshold)
    real = test["piezas_scrap"] / test["piezas_producidas"]
    base_rate = train.groupby("linea")["piezas_scrap"].sum() / train.groupby("linea")["piezas_producidas"].sum()
    band = lambda d: (d["horas_desde_mantto"] // 50).clip(upper=6)  # noqa: E731
    key_train = list(zip(train["linea"], band(train)))
    grouped = train.assign(k=key_train).groupby("k")
    band_rate = grouped["piezas_scrap"].sum() / grouped["piezas_producidas"].sum()
    band_pred = pd.Series([band_rate.get(k, np.nan) for k in zip(test["linea"], band(test))], index=test.index)
    band_pred = band_pred.fillna(test["linea"].map(base_rate))
    mae = {"Modelo base (promedio por línea)": (test["linea"].map(base_rate) - real).abs().mean(),
           "Modelo base (línea × banda de horas)": (band_pred - real).abs().mean(),
           "GLM binomial": (predict_rate(res, test, threshold) - real).abs().mean()}
    return pd.Series(mae, name="error_absoluto_medio_pp") * 100


def l2_hours(prod, interval):
    """Horas desde el mantenimiento si el preventivo de L2 se hiciera cada `interval` horas de operación."""
    order = prod.loc[prod["linea"] == "L2", "run_id"].sort_values().index
    op = SHIFT_HOURS - prod.loc[order, "paro_min"] / 60
    hours = prod["horas_desde_mantto"].copy()
    hours.loc[order] = (op.cumsum() - op) % interval
    return hours


def _scenario(res, prod, lever, threshold, interval, gap_closed):
    if lever == "mantenimiento":
        return _exog(res, prod.assign(horas_desde_mantto=l2_hours(prod, interval)), threshold)
    X = _exog(res, prod, threshold)
    if lever == "induccion":
        cols = X.columns.intersection(["nuevos_L1", "nuevos_L2", "nuevos_L3", "nuevos_todas"])
        X[cols] *= 1 - gap_closed
    elif lever == "proveedor":
        X["proveedor_C"] = 0.0
    else:
        raise ValueError(lever)
    return X


def lever_cost(lever, prod, catalog, hires, maint, interval, supuestos: Supuestos = REFERENCIA):
    """Costo anual de implementar cada palanca, con las funciones compartidas de `supuestos.py`."""
    if lever == "mantenimiento":
        hours = (SHIFT_HOURS - prod.loc[prod["linea"] == "L2", "paro_min"] / 60).sum()
        return costo_preventivos(hours / interval - (maint["linea"] == "L2").sum(), supuestos)
    if lever == "induccion":
        return costo_induccion(len(hires), supuestos)
    if lever == "proveedor":
        return costo_cambio_proveedor(compras_material(prod, catalog, c_lots_l1(prod)), supuestos)
    raise ValueError(lever)


def c_lots_l1(prod):
    """Corridas de L1 con material del proveedor C (las únicas donde el modelo estima su efecto)."""
    return (prod["proveedor_material"] == "C") & (prod["linea"] == "L1")


def reclamos_atribuidos_proveedor(claims):
    """Supuesto del análisis guiado: todos los reclamos por grieta se atribuyen a lotes del proveedor C.
    Sin este supuesto, la palanca de proveedor no paga su costo (ver docs/conciliacion_palancas.md)."""
    return float(claims.loc[claims["defecto"] == "Grieta", "costo_total_mxn"].sum())


def _expected_scrap(X, betas, n):
    return n * (1 / (1 + np.exp(-(X.to_numpy() @ np.atleast_2d(betas).T)))).T


def simulate_savings(res, prod, catalog, hires, maint, claims, threshold, interval=None, gap_closed=None,
                     levers=("mantenimiento", "induccion", "proveedor"), n_sims=None, seed=None,
                     supuestos: Supuestos = REFERENCIA, atribuir_reclamos=True):
    """Ahorro anual por palanca con incertidumbre paramétrica (β ~ Normal(β̂, Σ̂)).
    El mantenimiento se simula recalculando el ciclo de horas de L2 con el nuevo intervalo
    (por omisión, el umbral). Si `atribuir_reclamos`, a la palanca de proveedor se suman los
    reclamos por grieta, trazados a lotes del proveedor C (supuesto declarado).
    `gap_closed`, `n_sims` y `seed` sustituyen, si se dan, a los de `supuestos`."""
    interval = interval or threshold
    gap_closed = supuestos.brecha_induccion if gap_closed is None else gap_closed
    n_sims = supuestos.n_sims if n_sims is None else n_sims
    seed = supuestos.seed if seed is None else seed
    betas = np.random.default_rng(seed).multivariate_normal(res.params, res.cov_params(), n_sims)
    n = prod["piezas_producidas"].to_numpy()
    unit_cost = prod["costo_unitario_scrap_mxn"].to_numpy()
    base = _expected_scrap(_exog(res, prod, threshold), betas, n)
    traced = {"proveedor": reclamos_atribuidos_proveedor(claims) if atribuir_reclamos else 0.0}
    rows = []
    for lever in levers:
        alt = _expected_scrap(_scenario(res, prod, lever, threshold, interval, gap_closed), betas, n)
        gross = ((base - alt) * unit_cost).sum(axis=1) + traced.get(lever, 0)
        cost = lever_cost(lever, prod, catalog, hires, maint, interval, supuestos)
        p10, p50, p90 = np.percentile(gross, [10, 50, 90])
        rows.append({"palanca": lever, "piezas_evitadas": float(np.median((base - alt).sum(axis=1))),
                     "ahorro_bruto_p50": p50, "ahorro_bruto_p10": p10, "ahorro_bruto_p90": p90,
                     "reclamos_atribuidos_mxn": traced.get(lever, 0.0),
                     "costo_anual": cost, "ahorro_neto_p50": p50 - cost,
                     "ahorro_neto_p10": p10 - cost, "ahorro_neto_p90": p90 - cost})
    out = pd.DataFrame(rows).set_index("palanca")
    out.attrs["alcance_incertidumbre"] = ALCANCE_INCERTIDUMBRE
    return out


def maintenance_curve(res, prod, catalog, maint, threshold, intervals=range(100, 341, 10),
                      supuestos: Supuestos = REFERENCIA):
    """Ahorro neto (estimación puntual) según el intervalo de mantenimiento preventivo de L2."""
    n = prod["piezas_producidas"].to_numpy()
    unit_cost = prod["costo_unitario_scrap_mxn"].to_numpy()
    base = _expected_scrap(_exog(res, prod, threshold), res.params, n)
    rows = []
    for interval in intervals:
        alt = _expected_scrap(_scenario(res, prod, "mantenimiento", threshold, interval, 0), res.params, n)
        gross = float(((base - alt) * unit_cost).sum())
        cost = lever_cost("mantenimiento", prod, catalog, None, maint, interval, supuestos)
        rows.append({"intervalo_h": interval, "ahorro_bruto": gross, "costo_anual": cost,
                     "ahorro_neto": gross - cost})
    return pd.DataFrame(rows).set_index("intervalo_h")
