"""Independent nonlinear holdout-feature isolation and CPU rejection checks."""

import numpy as np
import pytest
from fastapi.testclient import TestClient
from app.main import app

client = TestClient(app)


def test_forest_heldout_feature_extreme_cannot_change_other_predictions_or_training():
    x = np.linspace(-2, 2, 120)
    y = x * x
    data = {
        "features": x[:, None].tolist(),
        "target": y.tolist(),
        "model": "random_forest",
        "trees": 10,
        "repeats": 1,
        "max_depth": 6,
        "seed": 12,
    }
    response = client.post("/analyze", json=data)
    assert response.status_code == 200, response.text
    a = response.json()
    modified = a["test_indices"][0]
    data["features"][modified] = [1e10]
    response = client.post("/analyze", json=data)
    assert response.status_code == 200, response.text
    b = response.json()
    assert (
        a["test_indices"] == b["test_indices"]
        and a["predictions"][1:] == b["predictions"][1:]
    )
    train_values = [v for i, v in enumerate(y) if i not in a["test_indices"]]
    assert min(train_values) <= b["predictions"][0] <= max(train_values)
    assert b["intercept"] is None and all(
        row["coefficient"] is None for row in b["importance"]
    )
    assert b["model_configuration"]["n_jobs"] == 1


def test_forest_permutation_budget_rejects_before_any_fit():
    from unittest.mock import patch

    data = {
        "features": [[float(i)] for i in range(1000)],
        "target": list(range(1000)),
        "model": "random_forest",
        "trees": 100,
        "repeats": 9,
    }
    with patch(
        "sklearn.ensemble.RandomForestRegressor.fit",
        side_effect=AssertionError("Fit must not execute over budget"),
    ):
        response = client.post("/analyze", json=data)
    assert response.status_code == 422 and "permutation work" in response.text


def test_forest_tiny_outcome_units_keep_nonlinear_fit_and_defined_r2():
    x = np.linspace(-2, 2, 120)
    y = x * x
    response = client.post(
        "/analyze",
        json={
            "features": x[:, None].tolist(),
            "target": (y * 1e-8).tolist(),
            "model": "random_forest",
            "trees": 10,
            "repeats": 1,
            "max_depth": 6,
            "seed": 42,
        },
    )
    assert response.status_code == 200, response.text
    result = response.json()
    assert result["held_out_r2"] is not None and result["held_out_r2"] > 0.9


def test_ols_nonconstant_small_outcome_has_defined_unit_invariant_r2():
    x = np.linspace(-2, 2, 40)
    response = client.post(
        "/analyze",
        json={
            "features": x[:, None].tolist(),
            "target": (x * 1e-8).tolist(),
            "model": "ols",
            "repeats": 1,
        },
    )
    assert response.status_code == 200, response.text
    assert response.json()["held_out_r2"] == pytest.approx(1, abs=1e-10)
