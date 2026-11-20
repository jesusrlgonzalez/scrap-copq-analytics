"""INC-V03: el modo «Tus datos» debe recalcular sin caché serializada y con resultados idénticos."""
from pathlib import Path

from streamlit.testing.v1 import AppTest

from scrap_copq import diagnose as dg
from scrap_copq import intake
from scrap_copq import ui_diagnostico as ui

ROOT = Path(__file__).resolve().parents[1]


def test_run_no_usa_cache_serializada():
    """st.cache_data serializa el resultado; en Stlite/Pyodide no se puede reconstruir (INC-V03)."""
    assert not hasattr(ui._run, "clear"), "_run no debe llevar @st.cache_data"


def test_run_es_determinista():
    content = intake.example_with_errors()
    a = ui._run(content, dg.Settings())
    b = ui._run(content, dg.Settings())
    assert a[0]["filas_validas"] == b[0]["filas_validas"]
    assert a[2]["kpis"] == b[2]["kpis"]
    assert a[2]["palancas"].equals(b[2]["palancas"])


def _app():
    at = AppTest.from_file(str(ROOT / "streamlit_app.py"), default_timeout=300)
    at.run()
    at.segmented_control[0].set_value("Tus datos").run()
    at.button[0].click().run()
    return at


def _kpis(at):
    return [(m.label, m.value) for m in at.metric]


def test_tres_recalculos_y_cambio_de_nombre_sin_error():
    at = _app()
    assert not at.exception
    primero = _kpis(at)
    assert ("Costo de no calidad", "$8.45 M") in primero
    for _ in range(2):  # 2.º y 3.er recálculo con el mismo archivo y los mismos supuestos
        at.run()
        assert not at.exception and _kpis(at) == primero
    at.text_input[0].set_value("Planta prueba").run()  # solo cambia el nombre del reporte
    assert not at.exception and _kpis(at) == primero
    assert any("Hipótesis de causa raíz por validar" in m.value for m in at.markdown)


def test_cambiar_un_supuesto_recalcula():
    at = _app()
    antes = [m.value for m in at.success]
    at.number_input[0].set_value(400_000).run()  # preventivo mucho más caro
    assert not at.exception
    assert [m.value for m in at.success] != antes
