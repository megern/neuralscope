from .access import AccessControl
import math
from typing import Literal
from .guard import InputGuard
import numpy as np
from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pathlib import Path
from pydantic import BaseModel, Field, model_validator


def finite(values):
    if not all(abs(v) <= 1e100 and math.isfinite(v) for v in values):
        raise ValueError("numeric values must be finite with magnitude at most 1e100")


def matrix(rows):
    if (
        not rows
        or not rows[0]
        or len(rows[0]) > 50
        or any(len(row) != len(rows[0]) for row in rows)
    ):
        raise ValueError("numeric matrix must be rectangular with 1 to 50 columns")
    finite([v for row in rows for v in row])


class Request(BaseModel):
    features: list[list[float]] = Field(min_length=20, max_length=100000)
    target: list[float] = Field(min_length=20, max_length=100000)
    feature_names: list[str] | None = None
    test_fraction: float = Field(default=0.25, ge=0.1, le=0.5)
    seed: int = Field(default=42, ge=0, le=4294967295)
    repeats: int = Field(default=10, ge=1, le=100)

    model: Literal["ols", "random_forest"] = "ols"
    trees: int = Field(default=50, ge=10, le=100)
    max_depth: int = Field(default=8, ge=2, le=12)
    min_samples_leaf: int = Field(default=2, ge=1, le=50)

    @model_validator(mode="after")
    def valid(self):
        matrix(self.features)
        finite(self.target)
        if self.model == "random_forest":
            rows, width = len(self.features), len(self.features[0])
            test_rows = max(2, int(rows * self.test_fraction))
            if (
                rows > 3000
                or width > 20
                or (rows * width * self.trees * self.max_depth) > 20_000_000
                or (test_rows * width * self.repeats * self.trees) > 200_000
            ):
                raise ValueError(
                    "random forest exceeds CPU budget: max 3000 rows/20 features, fit work 20 million and permutation work 200 thousand; reduce rows, columns, trees, depth or repeats"
                )
            if any(abs(v) > 1e20 for row in self.features for v in row) or any(
                abs(v) > 1e20 for v in self.target
            ):
                raise ValueError(
                    "rescale random forest inputs/target to magnitude at most 1e20"
                )
        if len(self.features) != len(self.target):
            raise ValueError("row counts must match")
        if self.feature_names is not None and (
            len(self.feature_names) != len(self.features[0])
            or len(set(self.feature_names)) != len(self.feature_names)
        ):
            raise ValueError("feature names must be unique and match column count")
        return self


def analyze(req: Request):
    x, y = np.asarray(req.features), np.asarray(req.target)
    rng = np.random.default_rng(req.seed)
    order = rng.permutation(len(y))
    size = max(2, int(len(y) * req.test_fraction))
    test, train = order[:size], order[size:]
    beta = None
    if req.model == "ols":
        if len(train) <= x.shape[1] + 1:
            raise ValueError("training data must have more rows than model parameters")
        mean, scale = x[train].mean(0), x[train].std(0)
        scale = np.where(scale > 1e-12, scale, 1)
        a = np.column_stack([np.ones(len(train)), (x[train] - mean) / scale])
        if np.linalg.matrix_rank(a) < a.shape[1]:
            raise ValueError("features are constant or collinear in training data")
        beta = np.linalg.lstsq(a, y[train], rcond=None)[0]

        def predict(data):
            return beta[0] + ((data - mean) / scale) @ beta[1:]

    else:
        from sklearn.ensemble import RandomForestRegressor

        forest = RandomForestRegressor(
            n_estimators=req.trees,
            max_depth=req.max_depth,
            min_samples_leaf=req.min_samples_leaf,
            n_jobs=1,
            random_state=req.seed,
        )
        forest_center = x[train].mean(axis=0)
        forest_range = np.max(np.abs(x[train] - forest_center), axis=0)
        forest_scale = np.where(forest_range > 0, forest_range, 1.0)
        target_center = float(y[train].mean())
        target_range = float(np.max(np.abs(y[train] - target_center)))
        target_scale = target_range if target_range > 0 else 1.0
        forest.fit(
            (x[train] - forest_center) / forest_scale,
            (y[train] - target_center) / target_scale,
        )

        def predict(data):
            return (
                forest.predict((data - forest_center) / forest_scale) * target_scale
                + target_center
            )

    prediction = predict(x[test])
    mse = float(np.mean((prediction - y[test]) ** 2))
    # Normalize before squaring so changing target units cannot erase variance.
    target_magnitude = float(np.max(np.abs(y[test])))
    if np.all(y[test] == y[test][0]):
        r2 = None
    else:
        normalized_target = y[test] / target_magnitude
        variance = float(np.sum((normalized_target - normalized_target.mean()) ** 2))
        if variance == 0:
            raise ValueError(
                "held-out target variation cannot be represented; rescale target"
            )
        squared_error = float(np.sum(((prediction - y[test]) / target_magnitude) ** 2))
        r2 = 1 - squared_error / variance
    importance = []
    names = req.feature_names or [f"feature_{i}" for i in range(x.shape[1])]
    for j, name in enumerate(names):
        scores = []
        for _ in range(req.repeats):
            shuffled = x[test].copy()
            shuffled[:, j] = rng.permutation(shuffled[:, j])
            scores.append(float(np.mean((predict(shuffled) - y[test]) ** 2) - mse))
        importance.append(
            {
                "feature": name,
                "mse_increase": float(np.mean(scores)),
                "std": float(np.std(scores)),
                "coefficient": (
                    float(beta[j + 1] / scale[j]) if beta is not None else None
                ),
            }
        )
    residuals = y[test] - prediction
    absolute_errors = np.abs(residuals)

    def diagnostic(index):
        return {
            "row_index": int(test[index]),
            "actual": float(y[test[index]]),
            "predicted": float(prediction[index]),
            "residual": float(residuals[index]),
            "absolute_error": float(absolute_errors[index]),
        }

    diagnostic_limit = 1000
    worst = np.argsort(-absolute_errors, kind="stable")[:20]
    return {
        "model": req.model,
        "model_configuration": (
            {
                "trees": req.trees,
                "max_depth": req.max_depth,
                "min_samples_leaf": req.min_samples_leaf,
                "n_jobs": 1,
            }
            if req.model == "random_forest"
            else {}
        ),
        "diagnostic_summary": {
            "evaluated_rows": len(test),
            "reported_rows": min(len(test), diagnostic_limit),
            "diagnostic_limit": diagnostic_limit,
            "truncated": len(test) > diagnostic_limit,
            "mean_absolute_error": float(absolute_errors.mean()),
            "median_absolute_error": float(np.median(absolute_errors)),
            "max_absolute_error": float(absolute_errors.max()),
            "mean_residual": float(residuals.mean()),
            "residual_definition": "actual minus predicted; positive values mean underprediction",
        },
        "held_out_diagnostics": [
            diagnostic(i) for i in range(min(len(test), diagnostic_limit))
        ],
        "worst_cases": [diagnostic(int(i)) for i in worst],
        "held_out_mse": mse,
        "held_out_r2": r2,
        "train_rows": len(train),
        "test_rows": len(test),
        "test_indices": test.tolist(),
        "predictions": prediction.tolist(),
        "intercept": (
            float(beta[0] - mean @ (beta[1:] / scale)) if beta is not None else None
        ),
        "importance": sorted(importance, key=lambda i: i["mse_increase"], reverse=True),
        "limitations": "Random holdout assumes independent observations; use chronological evaluation for time series. Models explain predictive association, not causation. Random forest has no linear coefficients; training-only feature and target centering/range scaling fits the trees; predictions and errors use original target units. Correlated features can dilute permutation importance. All preprocessing is fit only on training rows.",
    }


app = FastAPI(title="NeuralScope", version="0.4.0")


STATIC = Path(__file__).parent / "static"
app.mount("/static", StaticFiles(directory=STATIC), name="static")


@app.get("/")
def home():
    return FileResponse(STATIC / "index.html")


@app.get("/guide")
def user_guide():
    return FileResponse(
        Path(__file__).parent / "USER_GUIDE.md", media_type="text/plain"
    )


@app.get("/health")
def health():
    return {"status": "ok"}


@app.post("/analyze")
def run_analysis(req: Request):
    try:
        result = analyze(req)

        def check(value):
            if isinstance(value, float) and not math.isfinite(value):
                raise ValueError("numeric overflow; rescale input values")
            if isinstance(value, dict):
                for item in value.values():
                    check(item)
            elif isinstance(value, list):
                for item in value:
                    check(item)

        check(result)
        return result
    except (ValueError, np.linalg.LinAlgError, OverflowError) as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


app.add_middleware(InputGuard)


app.add_middleware(AccessControl)
