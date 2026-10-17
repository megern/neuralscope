import numpy as np
import pytest
from fastapi.testclient import TestClient
from app.main import app, Request, analyze


def dataset(rows=100):
    rng = np.random.default_rng(11)
    features = rng.normal(size=(rows, 2))
    target = 2 * features[:, 0] + features[:, 1] ** 2 + rng.normal(0, 0.1, rows)
    return features, target


def test_predictions_and_residuals_match_original_rows():
    x, y = dataset()
    result = analyze(Request(features=x.tolist(), target=y.tolist(), repeats=2))
    diagnostics = result["held_out_diagnostics"]
    assert [r["row_index"] for r in diagnostics] == result["test_indices"]
    for row, prediction in zip(diagnostics, result["predictions"]):
        assert row["actual"] == y[row["row_index"]]
        assert row["predicted"] == prediction
        assert row["residual"] == pytest.approx(row["actual"] - row["predicted"])
        assert row["absolute_error"] == abs(row["residual"])
    summary = result["diagnostic_summary"]
    errors = [r["absolute_error"] for r in diagnostics]
    assert summary["mean_absolute_error"] == pytest.approx(np.mean(errors))
    assert summary["max_absolute_error"] == max(errors)
    assert summary["mean_residual"] == pytest.approx(
        np.mean([r["residual"] for r in diagnostics])
    )
    assert result["held_out_mse"] == pytest.approx(
        np.mean([r["residual"] ** 2 for r in diagnostics])
    )
    assert [r["absolute_error"] for r in result["worst_cases"]] == sorted(
        errors, reverse=True
    )[:20]


def test_new_diagnostics_bounded_but_worst_cases_use_all_holdout():
    x, y = dataset(2100)
    request = {
        "features": x.tolist(),
        "target": y.tolist(),
        "test_fraction": 0.5,
        "repeats": 1,
    }
    response = TestClient(app).post("/analyze", json=request)
    assert response.status_code == 200, response.text
    result = response.json()
    assert result["diagnostic_summary"]["truncated"] is True
    assert len(result["held_out_diagnostics"]) == 1000
    assert len(result["test_indices"]) == len(result["predictions"]) == 1050
    assert len(result["worst_cases"]) == 20
    all_errors = sorted(
        (abs(y[i] - p) for i, p in zip(result["test_indices"], result["predictions"])),
        reverse=True,
    )
    assert [r["absolute_error"] for r in result["worst_cases"]] == pytest.approx(
        all_errors[:20]
    )


def test_holdout_changes_do_not_train_model_but_change_diagnostics():
    x, y = dataset()
    req = Request(features=x.tolist(), target=y.tolist(), repeats=1)
    first = analyze(req)
    y[first["test_indices"]] += 100
    second = analyze(Request(features=x.tolist(), target=y.tolist(), repeats=1))
    assert first["predictions"] == second["predictions"]
    assert second["diagnostic_summary"]["mean_residual"] == pytest.approx(
        first["diagnostic_summary"]["mean_residual"] + 100
    )
