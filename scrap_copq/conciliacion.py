"""Escenario de referencia y conciliación entre los dos recorridos de cálculo de las palancas.

* **Análisis guiado** (`model.py`): notebook, README y tablero «Planta de ejemplo».
* **Diagnóstico genérico** (`diagnose.py`): modo «Tus datos», con especificación automática.

Con los mismos datos y los mismos supuestos (`supuestos.py`), los costos de las palancas salen de
las mismas funciones. Las cifras restantes difieren solo por la especificación del modelo; el
puente las descompone paso a paso y cada paso se recalcula, no se escribe a mano.

    python -m scrap_copq.conciliacion            # imprime referencia y puente
    python -m scrap_copq.conciliacion --escribir # actualiza reports/referencia_palancas.json

Planta sintética: ningún valor es un ahorro observado ni una relación causal validada.
"""
from __future__ import annotations

import json
import sys

import pandas as pd

from . import diagnose as dg, intake, metrics as m, model as md
from .clean import load
from .config import PROCESSED, ROOT
from .supuestos import ALCANCE_INCERTIDUMBRE, REFERENCIA, Supuestos

JSON_REFERENCIA = ROOT / "reports" / "referencia_palancas.json"
PALANCAS = ("mantenimiento", "induccion", "proveedor")


def tablas_planta():
    t = load(PROCESSED)
    t["prod"] = m.with_costs(t["produccion_turnos"], t["catalogo_productos"])
    return t


def analisis_guiado(t, esp: md.Especificacion = md.REF_ESP, threshold=None, interval=None,
                    supuestos: Supuestos = REFERENCIA):
    """Palancas del análisis guiado. Con los valores por omisión, es el escenario de referencia."""
    if threshold is None:
        threshold, _ = md.find_threshold(t["prod"], esp=esp)
    res = md.fit(t["prod"], threshold, esp)
    sav = md.simulate_savings(res, t["prod"], t["catalogo_productos"], t["altas_operadores"], t["mantenimientos"],
                              t["reclamos_cliente"], threshold, interval=interval, supuestos=supuestos)
    return threshold, sav


def escenario_referencia(t=None) -> dict:
    """Escenario documentado en el README: especificación y supuestos de referencia, año completo."""
    t = t if t is not None else tablas_planta()
    threshold, sav = analisis_guiado(t)
    k = m.kpis(t["prod"], t["reclamos_cliente"])
    total = float(sav["ahorro_neto_p50"].sum())
    return {
        "naturaleza": "Planta sintética (semilla 42). Estimación de modelo, no ahorro observado ni efecto causal validado.",
        "supuestos": {k_: v for k_, v in REFERENCIA.__dict__.items()},
        "alcance_incertidumbre": ALCANCE_INCERTIDUMBRE,
        "copq_mxn": float(k["copq_mxn"]), "copq_pct_ventas": float(k["copq_pct_ventas"]),
        "umbral_h": int(threshold),
        "palancas": {p: {c: float(sav.loc[p, c]) for c in ("ahorro_bruto_p50", "reclamos_atribuidos_mxn", "costo_anual",
                                                          "ahorro_neto_p10", "ahorro_neto_p50", "ahorro_neto_p90")}
                     for p in PALANCAS},
        "total_neto_p50": total, "total_pct_copq": total / float(k["copq_mxn"]),
    }


def datos_plantilla():
    """La planta sintética tal como la ve el modo «Tus datos» (plantilla de ejemplo)."""
    data, _ = intake.validate(intake.read_workbook(intake.template_bytes()))
    return data


def ajustes_equivalentes(t) -> dg.Settings:
    """Ajustes del diagnóstico genérico con los mismos supuestos que la referencia: mismas altas
    de operadores y los mismos reclamos atribuidos al proveedor que se mueve."""
    return dg.Settings(supuestos=REFERENCIA, altas_operadores_anio=len(t["altas_operadores"]),
                       reclamos_atribuidos_proveedor_mxn=md.reclamos_atribuidos_proveedor(t["reclamos_cliente"]))


def diagnostico_generico(data=None, settings: dg.Settings | None = None) -> pd.DataFrame:
    data = data if data is not None else datos_plantilla()
    lev = dg.diagnose(data, settings or dg.Settings())["palancas"]
    return lev.set_index("tipo")


def puente(t=None, data=None) -> pd.DataFrame:
    """Del total de referencia al del diagnóstico genérico con supuestos equivalentes, un cambio a la vez."""
    t = t if t is not None else tablas_planta()
    ref_thr, ref = analisis_guiado(t)
    gen = diagnostico_generico(data, ajustes_equivalentes(t))
    gen_thr = float(gen.loc["mantenimiento", "umbral_h"])

    _, m_thr = analisis_guiado(t, threshold=int(gen_thr))
    ind = {}
    for nombre, esp in (("comun", md.Especificacion(operadores="comun")),
                        ("sin_humedad", md.Especificacion(operadores="comun", humedad=False)),
                        ("sin_cambio", md.Especificacion(operadores="comun", humedad=False, cambio_modelo=False))):
        _, sav = analisis_guiado(t, esp=esp, threshold=ref_thr)
        ind[nombre] = float(sav.loc["induccion", "ahorro_neto_p50"])

    r = lambda p: float(ref.loc[p, "ahorro_neto_p50"])  # noqa: E731
    g = lambda p: float(gen.loc[p, "ahorro_neto_p50"])  # noqa: E731
    pasos = [
        ("Referencia (análisis guiado, README)", "—", float(ref["ahorro_neto_p50"].sum())),
        (f"Mantenimiento: umbral {ref_thr} h → {gen_thr:.0f} h (devianzas casi empatadas)", "mantenimiento",
         float(m_thr.loc["mantenimiento", "ahorro_neto_p50"]) - r("mantenimiento")),
        ("Mantenimiento: fórmula de preventivos adicionales y anualización 365/días", "mantenimiento",
         g("mantenimiento") - float(m_thr.loc["mantenimiento", "ahorro_neto_p50"])),
        ("Inducción: un efecto común en vez de uno por línea", "induccion", ind["comun"] - r("induccion")),
        ("Inducción: sin humedad en el modelo (variable omitida)", "induccion", ind["sin_humedad"] - ind["comun"]),
        ("Inducción: sin cambio de modelo en el modelo (variable omitida)", "induccion", ind["sin_cambio"] - ind["sin_humedad"]),
        ("Inducción: residuo (turnos y anualización)", "induccion", g("induccion") - ind["sin_cambio"]),
        ("Proveedor: referencia B en vez de A (efectos iguales, OR ≈ 1) y anualización", "proveedor",
         g("proveedor") - r("proveedor")),
    ]
    out = pd.DataFrame(pasos, columns=["paso", "palanca", "mxn"])
    out.attrs.update(referencia=float(ref["ahorro_neto_p50"].sum()),
                     generico=float(gen.loc[list(PALANCAS), "ahorro_neto_p50"].sum()))
    return out


def efecto_de_supuestos_por_omision(t=None, data=None) -> dict:
    """Cuánto cambia el diagnóstico genérico si no se capturan las altas ni se atribuyen reclamos."""
    t = t if t is not None else tablas_planta()
    eq = diagnostico_generico(data, ajustes_equivalentes(t))
    om = diagnostico_generico(data, dg.Settings())
    return {"equivalente": float(eq["ahorro_neto_p50"].sum()), "por_omision": float(om["ahorro_neto_p50"].sum()),
            "induccion_costo_capturado_por_omision": bool(om.loc["induccion", "costo_capturado"]),
            "proveedor_neto_sin_reclamos": float(om.loc["proveedor", "ahorro_neto_p50"])}


def main(argv=None):
    argv = argv if argv is not None else sys.argv[1:]
    t = tablas_planta()
    ref = escenario_referencia(t)
    pb = puente(t)
    if "--escribir" in argv:
        ref["puente"] = [{"paso": p, "palanca": pal, "mxn": round(v, 2)} for p, pal, v in pb.itertuples(index=False)]
        ref["total_generico_equivalente"] = pb.attrs["generico"]
        JSON_REFERENCIA.write_text(json.dumps(ref, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        print(f"Escrito {JSON_REFERENCIA.relative_to(ROOT)}")
    print(f"Referencia: {ref['total_neto_p50']:,.0f} MXN/año ({ref['total_pct_copq']:.1%} del COPQ)")
    print(pb.to_string(index=False, formatters={"mxn": "{:,.0f}".format}))
    print(f"Diagnóstico genérico con supuestos equivalentes: {pb.attrs['generico']:,.0f} MXN/año")


if __name__ == "__main__":
    main()
