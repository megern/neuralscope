import math
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

    @model_validator(mode="after")
    def valid(self):
        matrix(self.features)
        finite(self.target)
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

    prediction = predict(x[test])
    mse = float(np.mean((prediction - y[test]) ** 2))
    variance = float(np.sum((y[test] - y[test].mean()) ** 2))
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
                "coefficient": float(beta[j + 1] / scale[j]),
            }
        )
    return {
        "held_out_mse": mse,
        "held_out_r2": (
            1 - float(np.sum((prediction - y[test]) ** 2)) / variance
            if variance > 1e-12
            else None
        ),
        "train_rows": len(train),
        "test_rows": len(test),
        "test_indices": test.tolist(),
        "predictions": prediction.tolist(),
        "intercept": float(beta[0] - mean @ (beta[1:] / scale)),
        "importance": sorted(importance, key=lambda i: i["mse_increase"], reverse=True),
        "limitations": "Random holdout assumes independent observations; use chronological evaluation for time series. Linear model explains association, not causation. Correlated features can dilute permutation importance. All preprocessing is fit only on training rows.",
    }


app = FastAPI(title="NeuralScope", version="0.2.0")


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


from .guard import InputGuard

app.add_middleware(InputGuard)
