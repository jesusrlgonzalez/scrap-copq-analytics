"""Contrato numérico (docs/contrato_numerico.md): datos, reproducción, tolerancias y decisiones."""
import hashlib
import re
from pathlib import Path

import pytest

from scrap_copq import conciliacion as cc

ROOT = Path(__file__).resolve().parents[1]
DOC = (ROOT / "docs" / "contrato_numerico.md").read_text(encoding="utf-8")
TOL_RTOL, TOL_MILLONES, TOL_PCT = 1e-6, 0.005, 0.05


def _filas(seccion):
    bloque = DOC.split(f"## {seccion}")[1].split("\n## ")[0]
    return [[c.strip() for c in ln.strip("|").split("|")] for ln in bloque.splitlines()
            if ln.startswith("|") and not ln.startswith("|---")][1:]


@pytest.fixture(scope="module")
def referencia():
    return cc.escenario_referencia(cc.tablas_planta())


def test_r1_datos_de_entrada_identicos():
    filas = _filas("Datos de entrada (R1)")
    assert len(filas) == 12
    for archivo, n, huella in filas:
        datos = (ROOT / archivo).read_bytes().replace(b"\r\n", b"\n")
        assert hashlib.sha256(datos).hexdigest() == huella, archivo
        assert datos.rstrip(b"\n").count(b"\n") == int(n), archivo


def test_r2_mismo_entorno_misma_salida(referencia):
    assert cc.escenario_referencia(cc.tablas_planta()) == referencia


def test_r3_cifras_publicadas_dentro_de_tolerancia(referencia):
    pal = referencia["palancas"]
    for archivo in ("README.md", "README.es.md"):
        texto = (ROOT / archivo).read_text(encoding="utf-8")
        for p in cc.PALANCAS:
            fila = next(ln for ln in texto.splitlines() if ln.startswith("|") and re.search(r"\d\.\d\d – \d\.\d\d M", ln)
                        and abs(float(re.search(r"(\d\.\d\d) – ", ln).group(1)) - pal[p]["ahorro_neto_p10"] / 1e6) <= TOL_MILLONES
                        and abs(float(re.search(r"– (\d\.\d\d) M", ln).group(1)) - pal[p]["ahorro_neto_p90"] / 1e6) <= TOL_MILLONES)
            p50 = float(re.search(r"(\d\.\d\d) M", fila.split("|")[2]).group(1))
            assert abs(p50 - pal[p]["ahorro_neto_p50"] / 1e6) <= TOL_MILLONES, (archivo, p, fila)
        total = re.search(r"(\d\.\d\d) (?:millones|million)", texto)
        assert total and abs(float(total.group(1)) - referencia["copq_mxn"] / 1e6) <= TOL_MILLONES, archivo
        pct = re.search(r"\((\d+\.\d) % (?:del COPQ|of COPQ)", texto)
        assert pct and abs(float(pct.group(1)) - 100 * referencia["total_pct_copq"]) <= TOL_PCT, archivo


def test_r4_decisiones_estables(referencia):
    dec = {k: v for k, v in _filas("Decisiones (R4)")}
    pal = referencia["palancas"]
    assert referencia["umbral_h"] == int(dec["Umbral de horas desde el preventivo"])
    orden = sorted(cc.PALANCAS, key=lambda p: -pal[p]["ahorro_neto_p50"])
    assert " > ".join(orden) == dec["Orden de las palancas por ahorro neto P50"]
    assert orden[0] == dec["Palanca principal"]
    assert all(pal[p]["ahorro_neto_p10"] > 0 for p in cc.PALANCAS)
    assert pal[orden[0]]["ahorro_neto_p50"] / referencia["total_neto_p50"] > 0.80


def test_otro_escenario_economico_no_esta_restringido():
    """El contrato fija el escenario de referencia, no los demás: otros supuestos pueden cambiar cifras y orden."""
    from dataclasses import replace

    from scrap_copq.supuestos import REFERENCIA
    t = cc.tablas_planta()
    _, sav = cc.analisis_guiado(t, supuestos=replace(REFERENCIA, costo_preventivo_mxn=10 * REFERENCIA.costo_preventivo_mxn))
    ref = cc.escenario_referencia(t)
    assert sav.loc["mantenimiento", "ahorro_neto_p50"] < ref["palancas"]["mantenimiento"]["ahorro_neto_p50"]


def test_r5_tolerancias_no_se_relajan():
    tol = {k: float(v) for k, v in _filas("Tolerancias fijadas antes de comparar")}
    assert list(tol.values()) == [TOL_RTOL, TOL_MILLONES, TOL_PCT]
    conc = (ROOT / "tests" / "test_conciliacion.py").read_text(encoding="utf-8")
    rtol = float(re.search(r"^RTOL = ([\d.e-]+)", conc, re.MULTILINE).group(1))
    assert rtol <= TOL_RTOL
    for f in ("test_conciliacion.py", "test_contrato.py"):
        assert not re.search(r"pytest\.(skip|xfail)|@pytest\.mark\.(skip|xfail)", (ROOT / "tests" / f).read_text(encoding="utf-8")), f
