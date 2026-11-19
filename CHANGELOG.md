# Changelog

All notable changes follow [Keep a Changelog](https://keepachangelog.com/en/1.1.0/) and [Semantic Versioning](https://semver.org/).

## [Unreleased]

### Fixed
- The "Tus datos" diagnosis no longer sets the onboarding and supplier-change costs to zero by default. Both analyses now take their costs from one specification (`scrap_copq/supuestos.py`) and the same cost functions. A missing hire count is flagged as *not captured* (upper bound) instead of being silently zero. On the synthetic template, the default net total drops from MXN 1.52 M to 1.29 M.
- The dashboard savings simulator uses the reference number of simulations, so its initial values match the README (MXN 1,228,540).

### Added
- Reference scenario `reports/referencia_palancas.json` and `python -m scrap_copq.conciliacion`, with a step-by-step bridge between the guided analysis (1.23 M) and the generic diagnosis under the same assumptions (1.34 M). See `docs/conciliacion_palancas.md`.
- `model.Especificacion` to run documented variants of the GLM (pooled new-operator effect, without humidity or changeover).
- Twelve tests that fail if code, reference scenario, README, notebook, dashboard or the bridge document diverge, or if a cost is silently dropped.

### Documentation
- The scope of the P10–P90 interval (parameter uncertainty only), the synthetic nature of the data and the absence of any observed saving or validated causal effect are stated in the README, the demo and the 8D report. The supplier lever pays off only if crack claims are attributed to supplier C; without that assumption it is negative.

### Security
- Browser demo (Hugging Face Space): the Python requirements are pinned (`statsmodels==0.14.4`, `matplotlib==3.8.4`, `plotly==7.1.0`, `openpyxl==3.1.5`, `et-xmlfile==2.0.0`), so the code that runs next to an uploaded file no longer changes between visits.
- The demo page sets a Content-Security-Policy whose `connect-src` only allows the page itself, jsDelivr and PyPI; it also applies to the Pyodide worker.
- The upload screen shows a data-use notice naming the third parties that receive the visitor's IP address (jsDelivr, PyPI, Google Fonts).

## [1.2.0] - 2026-10-16

### Added
- MVP for real plants: "Tus datos" mode in the dashboard with an Excel template (`scrap_copq/intake.py`), row-level validation with Spanish messages, and processing in the browser on the live demo.
- Generic diagnosis (`scrap_copq/diagnose.py`): no plant-specific names; per-line maintenance thresholds by minimum deviance; levers reported only when significant, with P10–P90 annual savings and an out-of-sample check against the line average.
- One-page report with the 8D action and IATF 16949 / ISO 9001 references (`scrap_copq/report.py`).
- Pilot protocol with success and stop criteria (`docs/MVP_PILOTO.md`); seven tests on clean, dirty and minimal workbooks; a one-click example with capture errors.

## [1.1.0] - 2026-10-16

### Added
- Second baseline (line × 50 h maintenance band): mean absolute error 1.18 / 1.04 / 0.65 pp for the two baselines and the GLM.
- Dashboard Docker image with a health-check job in CI.
- English README with the Spanish version kept as `README.es.md`.
- Project page on GitHub Pages and a live demo on Hugging Face Spaces, published automatically from `main`.
- Release workflow: notes from this changelog and an evidence bundle attached to every tag.

## [1.0.0] - 2026-10-04

### Added
- Synthetic auto-parts plant data with seeded patterns; cleaning with a logged quality report.
- Cost of poor quality, double Pareto, Laney p′ charts and binomial GLM validated out of sample.
- Savings simulation: three levers worth MXN 1.23 M a year; Streamlit dashboard; SQL for PostgreSQL.
