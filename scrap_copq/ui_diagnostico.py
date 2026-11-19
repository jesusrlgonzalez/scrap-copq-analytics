"""Pestaña «Tus datos»: el diagnóstico sobre el Excel de una planta real, procesado en el navegador."""
import plotly.graph_objects as go
import streamlit as st

from . import diagnose as dg, intake, report as rp
from .supuestos import REFERENCIA, Supuestos

BLUE, GREY, INK = "#0E0F11", "#C9CDD1", "#0E0F11"  # negro señal resalta el 80 %, línea el resto


def _md(text: str) -> str:
    """Streamlit lee «$…$» como fórmula; se escapa el signo de pesos."""
    return text.replace("$", "\\$")


@st.cache_data(show_spinner=False)
def _template():
    return intake.template_bytes()


@st.cache_data(show_spinner=False)
def _dirty_example():
    return intake.example_with_errors()


@st.cache_data(show_spinner="Validando y analizando…")
def _run(content: bytes, settings: dg.Settings):
    data, issues = intake.validate(intake.read_workbook(content))
    return data, issues, dg.diagnose(data, settings)


def _pareto_fig(pc, pp):
    rank = {d: i + 1 for i, d in enumerate(pp["defecto"])}
    fig = go.Figure()
    fig.add_bar(x=pc["defecto"], y=pc["pct"], marker_color=[BLUE if v else GREY for v in pc["pocos_vitales"]],
                customdata=[rank.get(d) for d in pc["defecto"]],
                hovertemplate="%{x}: %{y:.1f} % del costo · lugar %{customdata} por piezas<extra></extra>")
    fig.update_layout(title="Pareto por costo (en negro, el 80 %)", height=340, margin=dict(l=10, r=10, t=50, b=10),
                      yaxis=dict(ticksuffix=" %"), plot_bgcolor="#FFFFFF", paper_bgcolor="#FFFFFF", font_color=INK, font_family="Barlow, system-ui, sans-serif")
    return fig


def render():
    st.subheader("Diagnóstico de scrap con tus datos")
    st.markdown("Sube el Excel de tu planta y obtén el costo de no calidad, las cartas p′ y las palancas de ahorro con su "
                "intervalo, más un reporte de una página en formato 8D. **El archivo se procesa en tu navegador: "
                "no se envía a ningún servidor.**")
    st.caption("Aviso de uso de datos: para funcionar, la página descarga bibliotecas y tipografías de servicios públicos "
               "(jsDelivr, PyPI, Google Fonts), que reciben tu dirección IP y datos técnicos de tu navegador, pero no tu "
               "archivo. No subas datos personales ni confidenciales sin autorización de tu empresa.")
    st.download_button("Descargar plantilla de Excel (con datos de ejemplo)", _template(), "plantilla_scrap.xlsx",
                       "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
    st.caption("Hojas: *produccion* (una fila por corrida), *costos* (por producto) y *reclamos* (opcional). "
               "La hoja *instrucciones* explica cada columna. Mínimo 3 meses; ideal 12.")

    up = st.file_uploader("Tu archivo .xlsx", type=["xlsx"])
    if st.button("O prueba con un archivo de ejemplo que trae errores de captura"):
        st.session_state["ejemplo"] = True
    plant = st.text_input("Nombre de la planta o línea (aparece en el reporte)", "Mi planta")
    with st.expander("Supuestos de costo de cada palanca", expanded=True):
        ref = REFERENCIA
        a, b, c = st.columns(3)
        pm = a.number_input("Un preventivo adicional (MXN)", 0, 1_000_000, int(ref.costo_preventivo_mxn), 500)
        por_op = b.number_input("Inducción por operador nuevo (MXN)", 0, 1_000_000,
                                int(ref.costo_induccion_por_operador_mxn), 1_000)
        altas = c.number_input("Operadores nuevos que ingresan al año", 0, 10_000, None, 1, placeholder="sin capturar",
                               help="Sin este dato, el costo de la inducción no se captura y su ahorro se reporta bruto.")
        d, e, f = st.columns(3)
        desc = d.number_input("Descuento que se pierde al cambiar de proveedor (%)", 0.0, 50.0,
                              100 * ref.descuento_proveedor, 0.5)
        extra = e.number_input("Otros costos anuales del cambio de proveedor (MXN)", 0, 10_000_000, 0, 5_000)
        recl = f.number_input("Reclamos atribuibles al proveedor que se mueve (MXN/año)", 0, 100_000_000, 0, 10_000,
                              help="Atribuirlos es un supuesto del analista: súmalos solo si trazaste los reclamos a sus lotes.")
        gap = st.slider("Parte del efecto de operadores nuevos que cierra la inducción", 0, 100,
                        int(100 * ref.brecha_induccion), 10, format="%d %%")
        st.caption("Valores iniciales: los mismos supuestos del análisis guiado de la planta de ejemplo "
                   "(`scrap_copq/supuestos.py`). Con la planta de ejemplo, 10 altas y 201,520 MXN de reclamos por grieta "
                   "atribuidos al proveedor C, este diagnóstico da ≈ 1.34 M MXN/año frente a 1.23 M del análisis guiado: la "
                   "diferencia se debe a la especificación automática del modelo y está desglosada en "
                   "`docs/conciliacion_palancas.md`.")
    if up is not None:
        content = up.getvalue()
    elif st.session_state.get("ejemplo"):
        content = _dirty_example()
        st.caption("Analizando el archivo de ejemplo: la planta sintética con encabezados en otro formato, 4 filas con error, turnos mal escritos y 2 filas duplicadas.")
    else:
        st.info("Para probar, descarga la plantilla y súbela tal cual, o usa el archivo de ejemplo con errores.")
        return

    settings = dg.Settings(supuestos=Supuestos(costo_preventivo_mxn=pm, costo_induccion_por_operador_mxn=por_op,
                                               descuento_proveedor=desc / 100, brecha_induccion=gap / 100),
                           altas_operadores_anio=altas, reclamos_atribuidos_proveedor_mxn=recl,
                           costo_extra_proveedor_mxn=extra)
    try:
        data, issues, r = _run(content, settings)
    except intake.DataError as exc:
        st.error(str(exc))
        return

    errors = [i for i in issues if i.nivel == "error"]
    st.markdown(f"**{data['filas_validas']:,} de {data['filas_leidas']:,} filas válidas** · {len(errors)} filas excluidas · "
                f"{len(issues) - len(errors)} avisos")
    if issues:
        with st.expander("Ver errores y avisos de los datos", expanded=bool(errors)):
            st.dataframe(intake.issues_frame(issues), hide_index=True)

    k = r["kpis"]
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Costo de no calidad", rp.mxn(k["copq_mxn"]), border=True)
    c2.metric("Anualizado", rp.mxn(k["copq_anual_mxn"]), border=True)
    c3.metric("Tasa de scrap", f"{k['tasa_scrap']:.2%}", border=True)
    c4.metric("COPQ / ventas", "—" if k["copq_pct_ventas"] != k["copq_pct_ventas"] else f"{k['copq_pct_ventas']:.2%}", border=True)
    st.success(_md(rp.headline(r)))

    lev = r["palancas"]
    if not lev.empty:
        st.markdown("**Palancas con efecto demostrado (ahorro anual)**")
        st.dataframe(lev[["palanca", "piezas_evitadas_anio", "costo_anual", "ahorro_neto_p10", "ahorro_neto_p50", "ahorro_neto_p90"]]
                     .rename(columns={"palanca": "Palanca", "piezas_evitadas_anio": "Piezas evitadas", "costo_anual": "Costo",
                                      "ahorro_neto_p10": "Neto P10", "ahorro_neto_p50": "Neto P50", "ahorro_neto_p90": "Neto P90"})
                     .style.format({"Piezas evitadas": "{:,.0f}", "Costo": "${:,.0f}", "Neto P10": "${:,.0f}",
                                    "Neto P50": "${:,.0f}", "Neto P90": "${:,.0f}"}), hide_index=True)
        if not lev["costo_capturado"].all():
            st.warning("Hay palancas sin costo capturado: su ahorro neto es una cota superior, no una estimación neta.")
        st.caption(r["alcance_incertidumbre"] + " " + r["especificacion"] +
                   " Es una estimación de modelo: no es un ahorro observado ni prueba causalidad.")
    left, right = st.columns(2)
    if "costo" in r["pareto"]:
        left.plotly_chart(_pareto_fig(r["pareto"]["costo"], r["pareto"]["piezas"]), theme=None)
    if not r["control"].empty:
        right.markdown("**Carta p′ de Laney por línea**")
        right.dataframe(r["control"].rename(columns={"linea": "Línea", "dias": "Días", "dias_fuera_limites": "Fuera de límites",
                                                     "dias_con_senal": "Con señal", "sigma_z": "σ_z", "tasa_media": "Tasa media",
                                                     "fuera_sobre_umbral": "Fuera y sobre umbral de horas"}),
                        hide_index=True)
    val = r["validacion"]
    if val:
        (st.caption if val["supera_base"] else st.warning)(
            f"Prueba fuera de muestra: error medio {val['mae_modelo_pp']:.2f} pp contra {val['mae_base_pp']:.2f} pp del promedio "
            f"por línea ({val['mejora_pct']:+.0f} %)." + ("" if val["supera_base"] else " No pasar a piloto con estas palancas."))

    for a, b in rp.eight_d(r):
        st.markdown(f"**{a}.** {_md(b)}")
    html_report = rp.report_html(r, issues, plant, (data["filas_leidas"], data["filas_validas"]))
    st.download_button("Descargar reporte de una página (HTML, imprimible a PDF)", html_report.encode("utf-8"),
                       "diagnostico_scrap.html", "text/html", type="primary")
