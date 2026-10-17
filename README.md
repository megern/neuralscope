# NeuralScope

Train a local ordinary-least-squares regression model and inspect repeated held-out permutation importance and original-unit coefficients.

**Version 0.3.0: local CPU research workbench.** Import a CSV, map the relevant columns, run the real calculation and inspect plots, tables and method assumptions. Export a JSON result report or exact replayable input. No API key, GPU, paid service or external model call is required.

## Why use it

An analyst has numeric independent observations and a numeric target, and wants a reproducible baseline with an understandable explanation of which columns affect held-out accuracy.

## Start

```sh
docker compose up --build
```

Open http://127.0.0.1:8000 and choose **Load synthetic example**. All bundled data are explicitly synthetic. Import your own UTF-8 CSV to use actual observations; their provenance remains unverified by the application.

Python3.12+ alternative:

```sh
python3 -m venv .venv
. .venv/bin/activate
pip install '.[dev]'
uvicorn app.main:app --host 127.0.0.1 --port 8000
```

API example:

```sh
curl --fail -H 'Content-Type: application/json' --data-binary @examples/synthetic.json http://127.0.0.1:8000/analyze
```

## Inputs, outputs and scientific scope

At least20 rows, a finite numeric target, and1–50 numeric features. Training rows must outnumber intercept plus features, and the training design must be full rank. Target must not be selected as a feature. Missing/categorical values are rejected rather than silently encoded.

Positive permutation importance means shuffling that feature degraded this model’s predictions. Negative or near-zero importance can reflect noise, redundancy or variability. Repeat standard deviation quantifies permutation spread, not a confidence interval for population importance. R² can be negative and is null when held-out targets are constant. Returned test_indices are zero-based original row indices.

Random split assumes independent observations; it is unsuitable for autocorrelated sequences, grouped observations or repeated entities without a justified split strategy. Correlated features can obscure individual importance. Explanations describe this fitted linear baseline, not causation or an arbitrary uploaded neural network. No opaque model loading, classification, SHAP or model registry is implemented.

Read the [complete user guide](docs/USER_GUIDE.md) for the walkthrough, methods, export/replay, data limits and troubleshooting. A CSV sample is in `examples/synthetic.csv`; the JSON example calls the same API.

## Validate

```sh
pip install '.[dev]'
pytest -q
node tools/test_ui.mjs
pip-audit --strict
bandit -r app -ll
```

Node is needed only for frontend development checks. Fresh v0.3.0 developer evidence is in `evidence/improvements-0.3/`; previous v0.2 records remain historical. No Docker runtime, remote CI, publication or human review is implied merely by creating files. Required CI must pass before merging. Containers bind localhost and run nonroot; add authentication, HTTPS and deployment resource limits before external access. MIT license.

## v0.3.0: held-out error diagnostics

The workbench now adds an actual-versus-predicted scatter with a perfect-agreement reference, absolute-error summary and the20 worst held-out cases. Each row carries the **zero-based original input `row_index`** in API output; UI data-row labels add1 and exclude the CSV header. Residual = actual−predicted, so positive residuals indicate underprediction. Each diagnostic supplies actual, predicted, residual and absolute error.

`diagnostic_summary` computes mean/median/max absolute error and mean residual across **all** held-out rows. `held_out_diagnostics` includes at most the first1,000 observations in seeded holdout order (not sorted chronologically or by error); the summary explicitly marks truncation. The scatter uses this bounded sample. `worst_cases` contains at most20 observations selected across the entire holdout, sorted by absolute error, with stable ordering for ties. These are inspection aids, not outlier labels or a claim of diagnostic representativeness. No held-out target is used for model fitting or preprocessing.

Existing `test_indices`, `predictions`, coefficients and importance remain for compatibility, and all new diagnostics export with the report. No pickle, executable model upload, arbitrary estimator loading, classification or neural-network explanation is added.
