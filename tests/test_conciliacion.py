"""Conciliación HC-1/HC-2: el código, el escenario de referencia, la documentación y la demo no deben divergir."""
import json
import re
from pathlib import Path

import pytest

from scrap_copq import conciliacion as cc, diagnose as dg, model as md, report as rp
from scrap_copq.supuestos import ALCANCE_INCERTIDUMBRE, REFERENCIA

ROOT = Path(__file__).resolve().parents[1]
RTOL = 1e-6   # tolerancia frente a diferencias numéricas entre versiones de numpy/statsmodels


@pytest.fixture(scope="module")
def planta():
    return cc.tablas_planta()


@pytest.fixture(scope="module")
def referencia(planta):
    return cc.escenario_referencia(planta)


@pytest.fixture(scope="module")
def guardada():
    return json.loads(cc.JSON_REFERENCIA.read_text(encoding="utf-8"))


@pytest.fixture(scope="module")
def puente(planta):
    return cc.puente(planta)


def millones(x):
    return f"{x / 1e6:.2f}"


def test_referencia_reproduce_el_json(referencia, guardada):
    assert referencia["umbral_h"] == guardada["umbral_h"]
    assert referencia["supuestos"] == guardada["supuestos"]
    assert referencia["copq_mxn"] == pytest.approx(guardada["copq_mxn"], rel=RTOL)
    assert referencia["total_neto_p50"] == pytest.approx(guardada["total_neto_p50"], rel=RTOL)
    for p in cc.PALANCAS:
        for c, v in guardada["palancas"][p].items():
            assert referencia["palancas"][p][c] == pytest.approx(v, rel=RTOL, abs=1e-6), (p, c)


@pytest.mark.parametrize("archivo", ["README.md", "README.es.md"])
def test_readme_coincide_con_la_referencia(archivo, guardada):
    texto = (ROOT / archivo).read_text(encoding="utf-8")
    pal = guardada["palancas"]
    for p in cc.PALANCAS:
        intervalo = f"{millones(pal[p]['ahorro_neto_p10'])} – {millones(pal[p]['ahorro_neto_p90'])} M"
        filas = [ln for ln in texto.splitlines() if ln.startswith("|") and intervalo in ln]
        assert len(filas) == 1, (archivo, p, intervalo)
        assert f"{millones(pal[p]['ahorro_neto_p50'])} M" in filas[0], (archivo, p, filas[0])
    assert f"{guardada['total_neto_p50'] / 1e6:.2f} m" in texto.lower()
    assert f"{100 * guardada['total_pct_copq']:.1f} %" in texto
    assert f"{guardada['copq_mxn'] / 1e6:.2f} m" in texto.lower()
    assert f"{100 * guardada['copq_pct_ventas']:.2f} %" in texto
    generico = guardada["total_generico_equivalente"]
    afirmado = re.findall(r"(?:genérico da|generic diagnosis gives) (?:MXN )?(\d\.\d\d) M", texto)
    assert afirmado == [millones(generico)], afirmado
    afirmado = re.findall(r"(?:Dos especificaciones razonables dan|Two reasonable specifications give) (\d\.\d\d) M y? ?(?:and )?(\d\.\d\d) M",
                          texto)
    assert afirmado == [(millones(guardada["total_neto_p50"]), millones(generico))], afirmado
    assert f"+{100 * (generico / guardada['total_neto_p50'] - 1):.1f} %" in texto
    assert f"{pal['proveedor']['reclamos_atribuidos_mxn']:,.0f}" in texto


def test_notebook_coincide_con_la_referencia(guardada):
    nb = json.loads((ROOT / "notebooks" / "analisis_scrap_copq.ipynb").read_text(encoding="utf-8"))
    salida = "".join("".join(o.get("text", "")) for c in nb["cells"] if c["cell_type"] == "code" for o in c.get("outputs", []))
    total = re.search(r"Ahorro neto total \(mediana\): ([\d,]+) MXN", salida).group(1)
    assert int(total.replace(",", "")) == round(guardada["total_neto_p50"])


def test_tablero_con_valores_iniciales_reproduce_la_referencia(planta, guardada):
    fuente = (ROOT / "streamlit_app.py").read_text(encoding="utf-8")
    assert "supuestos=REFERENCIA" in fuente and "n_sims=" not in fuente
    threshold, res = guardada["umbral_h"], md.fit(planta["prod"], guardada["umbral_h"])
    sav = md.simulate_savings(res, planta["prod"], planta["catalogo_productos"], planta["altas_operadores"],
                              planta["mantenimientos"], planta["reclamos_cliente"], threshold,
                              interval=threshold, gap_closed=REFERENCIA.brecha_induccion, supuestos=REFERENCIA)
    assert sav["ahorro_neto_p50"].sum() == pytest.approx(guardada["total_neto_p50"], rel=RTOL)


def test_mismos_supuestos_mismos_costos(planta, referencia):
    gen = cc.diagnostico_generico(settings=cc.ajustes_equivalentes(planta))
    assert gen["costo_capturado"].all()
    assert gen.loc["induccion", "costo_anual"] == referencia["palancas"]["induccion"]["costo_anual"]
    anual = 365 / ((planta["prod"]["fecha"].max() - planta["prod"]["fecha"].min()).days + 1)
    assert gen.loc["proveedor", "costo_anual"] == pytest.approx(referencia["palancas"]["proveedor"]["costo_anual"] * anual,
                                                                rel=1e-9)
    assert gen.loc["proveedor", "reclamos_atribuidos_mxn"] == referencia["palancas"]["proveedor"]["reclamos_atribuidos_mxn"]


def test_puente_cierra_y_solo_deja_residuos_pequenos(puente, referencia):
    assert puente["mxn"].iloc[0] == pytest.approx(referencia["total_neto_p50"], rel=RTOL)
    assert puente["mxn"].sum() == pytest.approx(puente.attrs["generico"], abs=1)
    residuos = puente[puente["paso"].str.contains("residuo|fórmula", case=False)]
    assert len(residuos) == 2
    assert (residuos["mxn"].abs() < 0.005 * referencia["total_neto_p50"]).all()
    # Los pasos explicados son los grandes: la diferencia no queda en los residuos.
    explicados = puente.iloc[1:].drop(residuos.index)["mxn"].sum()
    assert explicados > 0.95 * (puente.attrs["generico"] - referencia["total_neto_p50"])


def test_puente_documentado_coincide_con_el_calculado(puente, guardada):
    doc = (ROOT / "docs" / "conciliacion_palancas.md").read_text(encoding="utf-8").replace("−", "-")
    for paso, guardado in zip(puente.itertuples(index=False), guardada["puente"]):
        assert paso.mxn == pytest.approx(guardado["mxn"], rel=1e-4, abs=1)
        texto = f"{paso.mxn:,.0f}" if paso.palanca == "—" else f"{paso.mxn:+,.0f}"
        assert texto in doc, texto
    assert f"{guardada['total_generico_equivalente']:,.0f}" in doc


def test_umbrales_casi_empatados_explican_el_paso_de_mantenimiento(planta):
    _, dev = md.find_threshold(planta["prod"])
    assert abs(dev.loc[160] - dev.loc[170]) < 0.001 * dev.min()


def test_supuestos_por_omision_no_ocultan_costos(planta):
    gen = cc.diagnostico_generico(settings=dg.Settings())
    assert not gen.loc["induccion", "costo_capturado"]
    assert gen.loc["proveedor", "ahorro_neto_p50"] < 0          # sin atribuir reclamos, el cambio no paga
    r = dg.diagnose(cc.datos_plantilla(), dg.Settings(n_sims=200))
    html = rp.report_html(r, [], "Planta", (1, 1))
    assert "sin capturar" in html and "solo incertidumbre de parámetros" in html


def test_incertidumbre_y_naturaleza_declaradas(planta, guardada):
    threshold = guardada["umbral_h"]
    sav = md.simulate_savings(md.fit(planta["prod"], threshold), planta["prod"], planta["catalogo_productos"],
                              planta["altas_operadores"], planta["mantenimientos"], planta["reclamos_cliente"],
                              threshold, n_sims=100)
    assert sav.attrs["alcance_incertidumbre"] == ALCANCE_INCERTIDUMBRE == guardada["alcance_incertidumbre"]
    assert "sintética" in guardada["naturaleza"] and "no ahorro observado" in guardada["naturaleza"]


def test_otros_escenarios_siguen_disponibles(planta):
    caro = REFERENCIA.__class__(costo_induccion_por_operador_mxn=30_000)
    _, base = cc.analisis_guiado(planta, threshold=170)
    _, alt = cc.analisis_guiado(planta, threshold=170, supuestos=caro)
    assert alt.loc["induccion", "costo_anual"] == 2 * base.loc["induccion", "costo_anual"]
    assert alt.loc["induccion", "ahorro_bruto_p50"] == base.loc["induccion", "ahorro_bruto_p50"]
    comun = md.fit(planta["prod"], 170, md.Especificacion(operadores="comun"))
    assert "nuevos_todas" in comun.params and "nuevos_L1" not in comun.params
