# NeuralScope user guide — v0.3.0

## What this tool does

Train a local ordinary-least-squares regression model and inspect repeated held-out permutation importance and original-unit coefficients.

Use case: An analyst has numeric independent observations and a numeric target, and wants a reproducible baseline with an understandable explanation of which columns affect held-out accuracy.

## Quickstart

Requires Docker Compose, or Python3.12+ for the installed pinned NumPy dependency. No API key, remote model, GPU or paid service is used.

```sh
docker compose up --build
```

Open http://127.0.0.1:8000. The interactive workbench loads a clearly labeled synthetic example. API docs: http://127.0.0.1:8000/docs. Change the host port in compose if running several tools together.

Without Docker:

```sh
python3 -m venv .venv
. .venv/bin/activate
pip install '.[dev]'
uvicorn app.main:app --host 127.0.0.1 --port 8000
```

## Walkthrough

1. Load the synthetic 100-row dataset. Map `target`, then select `signal` and `noise`.
2. Keep a25% holdout,10 permutation repeats and seed42.
3. Train and explain. Inspect held-out MSE/R² and the feature table. The constructed signal should dominate the constructed noise.
4. Compare another seed to understand split variability; larger repeats reduce permutation sampling noise, not data uncertainty.
5. Export the full response and replayable selected data.

## Import and mapping

Import UTF-8 CSV with unique, nonempty header names. A BOM, CRLF, quoted commas, doubled quote escapes and quoted multiline fields are supported. Every data row must contain the same number of fields. Blank physical lines are ignored; empty fields within rows are not silently removed. The preview displays the first eight rows, while analysis uses all imported rows. Use mapping controls to select numeric columns; extra columns can remain unused. Import provenance is displayed as unverified, and imported values render as text.

Files and API requests are bounded at2MiB. CSV permits up to100 columns and100,000 rows; selected numeric matrices permit at most50 columns. Numbers must be finite with magnitude at most1e100. Imported files are read locally by the browser; selected data are sent to the local FastAPI service. The service holds requests in memory and does not persist them. No external network request is required by the workbench.

CSV format illustration (this fragment may be below the minimum sample size):

```csv
target,signal,noise
2,0,1.1
4.8,0.7,2.2
7.6,1.4,0.4
```

Input requirements: At least20 rows, a finite numeric target, and1–50 numeric features. Training rows must outnumber intercept plus features, and the training design must be full rank. Target must not be selected as a feature. Missing/categorical values are rejected rather than silently encoded.

## Methods

A seeded random split reserves held-out rows before preprocessing. Training means/scales standardize the inputs; OLS is fitted only to training rows. Held-out MSE measures prediction error. R² compares against the held-out target mean. Each selected held-out feature is shuffled repeatedly, and MSE increase is averaged. Coefficients are returned in original feature units.

## Read the output

Positive permutation importance means shuffling that feature degraded this model’s predictions. Negative or near-zero importance can reflect noise, redundancy or variability. Repeat standard deviation quantifies permutation spread, not a confidence interval for population importance. R² can be negative and is null when held-out targets are constant. Returned test_indices are zero-based original row indices.

The workbench provides metric cards, a plot, interpretation and exact result table. For long time sequences, the table shows the first300 rows; the API report includes the complete arrays. Charts summarize calculations, not additional fitted models. The expandable API response exposes exact values. Change any mapping or parameter to clear old results, then rerun; an in-flight result is discarded if settings changed.

## Export and replay

**Export result report (JSON)** downloads application/version, timestamp, provenance label, mapping/settings and computed result. **Export replayable input (JSON)** includes selected numeric data and is exactly the `/analyze` request format. Exports are local downloads; review them for sensitive data before sharing. There is no result CSV export and therefore no spreadsheet-formula export interpretation. Synthetic example CSV uses only fixed headers/numeric values.

```sh
curl --fail -H 'Content-Type: application/json' --data-binary @examples/synthetic.json http://127.0.0.1:8000/analyze
curl --fail -H 'Content-Type: application/json' --data-binary @downloaded-analysis-input.json http://127.0.0.1:8000/analyze
```

See examples/synthetic.json for a valid complete regression request; at least20 rows are required.

## Assumptions and limits

Random split assumes independent observations; it is unsuitable for autocorrelated sequences, grouped observations or repeated entities without a justified split strategy. Correlated features can obscure individual importance. Explanations describe this fitted linear baseline, not causation or an arbitrary uploaded neural network. No opaque model loading, classification, SHAP or model registry is implemented.

These are bounded local research tools. Synthetic fixtures do not establish external scientific validity. No domain expert or human audit is claimed. For network exposure, configure authentication, HTTPS, rate limits and deployment concurrency/memory bounds. Defaults bind to localhost and containers run without root privileges.

## Troubleshooting

Constant/collinear features: remove redundant columns. Too many features: reduce selected columns or collect more observations. Low/negative R²: the model may be misspecified or noisy; do not treat an explanation ranking as evidence of good prediction. Direct target leakage: deselect the target and other features derived from unavailable future labels.

CSV row/column error: fix the named row; do not convert a missing observation to zero automatically. HTTP422: inspect the specific schema/algorithm message and adjust mapping or input. HTTP413: reduce selected rows/columns below the2MiB request bound. File parse errors clear the usable dataset and results. For a browser error, inspect local service availability; restart only after reviewing the service log. If a download fails, check browser download permissions.

## Reproducibility and checks

```sh
pytest -q
node tools/test_ui.mjs
pip-audit --strict
bandit -r app -ll
```

Python tests exercise numerical results and actual HTTP endpoints. Node tests exercise CSV parsing, column mapping, numeric rejection and the synthetic analysis payload. Node22+ is used for development checks; it is not a runtime service dependency. Fresh v0.3.0 developer evidence is under `evidence/improvements-0.3/`; it records what was run and does not establish unexecuted Docker, GitHub CI or human validation. Configure required CI checks and never merge a failing release.

MIT license; see LICENSE.

## v0.3.0: held-out error diagnostics

The workbench now adds an actual-versus-predicted scatter with a perfect-agreement reference, absolute-error summary and the20 worst held-out cases. Each row carries the **zero-based original input `row_index`** in API output; UI data-row labels add1 and exclude the CSV header. Residual = actual−predicted, so positive residuals indicate underprediction. Each diagnostic supplies actual, predicted, residual and absolute error.

`diagnostic_summary` computes mean/median/max absolute error and mean residual across **all** held-out rows. `held_out_diagnostics` includes at most the first1,000 observations in seeded holdout order (not sorted chronologically or by error); the summary explicitly marks truncation. The scatter uses this bounded sample. `worst_cases` contains at most20 observations selected across the entire holdout, sorted by absolute error, with stable ordering for ties. These are inspection aids, not outlier labels or a claim of diagnostic representativeness. No held-out target is used for model fitting or preprocessing.

Existing `test_indices`, `predictions`, coefficients and importance remain for compatibility, and all new diagnostics export with the report. No pickle, executable model upload, arbitrary estimator loading, classification or neural-network explanation is added.
