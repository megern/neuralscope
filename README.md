# NeuralScope

Train a local ordinary-least-squares regression model and inspect repeated held-out permutation importance and original-unit coefficients.

**Version0.2.0: local CPU research workbench.** Import a CSV, map the relevant columns, run the real calculation and inspect plots, tables and method assumptions. Export a JSON result report or exact replayable input. No API key, GPU, paid service or external model call is required.

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

Node is needed only for frontend development checks. Fresh rebuild evidence is in `evidence/rebuild/`. No Docker runtime, remote CI, publication or human review is implied merely by creating files. Required CI must pass before merging. Containers bind localhost and run nonroot; add authentication, HTTPS and deployment resource limits before external access. MIT license.
