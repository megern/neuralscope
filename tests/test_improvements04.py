import numpy as np
from fastapi.testclient import TestClient
from app.main import app


def nonlinear():
    rng = np.random.default_rng(9)
    x = rng.uniform(-2, 2, (400, 1))
    y = x[:, 0] ** 2
    return x, y


def test_real_random_forest_learns_nonlinear_relation():
    x, y = nonlinear()
    base = {
        "features": x.tolist(),
        "target": y.tolist(),
        "repeats": 2,
        "trees": 40,
        "max_depth": 8,
    }
    ols = TestClient(app).post("/analyze", json=base).json()
    response = TestClient(app).post("/analyze", json={**base, "model": "random_forest"})
    assert response.status_code == 200, response.text
    forest = response.json()
    assert (
        forest["held_out_r2"] > 0.95
        and forest["held_out_r2"] > ols["held_out_r2"] + 0.8
    )
    assert (
        forest["intercept"] is None and forest["importance"][0]["coefficient"] is None
    )
    assert forest["model_configuration"]["n_jobs"] == 1


def test_forest_heldout_target_never_trains_trees():
    x, y = nonlinear()
    data = {
        "features": x.tolist(),
        "target": y.tolist(),
        "model": "random_forest",
        "repeats": 1,
        "trees": 20,
    }
    first = TestClient(app).post("/analyze", json=data).json()
    y[first["test_indices"]] += 100
    data["target"] = y.tolist()
    second = TestClient(app).post("/analyze", json=data).json()
    assert first["predictions"] == second["predictions"]
    assert second["held_out_mse"] > 9000


def test_forest_work_and_parameters_bounded():
    x, y = nonlinear()
    data = {
        "features": x.tolist(),
        "target": y.tolist(),
        "model": "random_forest",
        "trees": 101,
    }
    assert TestClient(app).post("/analyze", json=data).status_code == 422
    data.update(trees=100, repeats=100, features=[row * 10 for row in x.tolist()])
    assert TestClient(app).post("/analyze", json=data).status_code == 422


def test_documented_synthetic_feature_request_is_runnable():
    import json
    from pathlib import Path

    data = json.loads(
        (Path(__file__).parents[1] / "examples/synthetic-forest.json").read_text()
    )
    response = TestClient(app).post("/analyze", json=data)
    assert response.status_code == 200, response.text
    assert isinstance(response.json(), dict)


def test_forest_training_only_scaling_preserves_small_feature_units():
    x, y = nonlinear()
    response = TestClient(app).post(
        "/analyze",
        json={
            "features": (x * 1e-12).tolist(),
            "target": y.tolist(),
            "model": "random_forest",
            "repeats": 1,
            "trees": 30,
        },
    )
    assert response.status_code == 200, response.text
    assert response.json()["held_out_r2"] > 0.95


def test_forest_target_unit_conversion_restores_predictions_and_error_units():
    x = np.linspace(-2, 2, 120)[:, None]
    y = x[:, 0] ** 2
    client = TestClient(app)
    request = {
        "features": x.tolist(),
        "target": y.tolist(),
        "model": "random_forest",
        "trees": 10,
        "max_depth": 6,
        "repeats": 1,
    }
    ordinary = client.post("/analyze", json=request).json()
    request["target"] = (y * 1e-8).tolist()
    tiny = client.post("/analyze", json=request).json()
    np.testing.assert_allclose(
        np.asarray(tiny["predictions"]) / 1e-8, ordinary["predictions"], rtol=1e-12
    )
    np.testing.assert_allclose(tiny["held_out_r2"], ordinary["held_out_r2"], rtol=1e-12)
    np.testing.assert_allclose(
        tiny["held_out_mse"] / 1e-16, ordinary["held_out_mse"], rtol=1e-12
    )
