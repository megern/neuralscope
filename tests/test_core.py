import numpy as np
import pytest
from fastapi.testclient import TestClient
from app.main import Request, analyze, app


def test_known_linear_signal_and_noise():
    rng = np.random.default_rng(3)
    x = rng.normal(size=(300, 2))
    y = 2 + 4 * x[:, 0]
    result = analyze(
        Request(
            features=x.tolist(), target=y.tolist(), feature_names=["signal", "noise"]
        )
    )
    assert result["held_out_mse"] < 1e-20
    assert result["held_out_r2"] == pytest.approx(1)
    assert result["importance"][0]["feature"] == "signal"
    assert result["importance"][0]["coefficient"] == pytest.approx(4)
    assert result["importance"][1]["mse_increase"] == pytest.approx(0, abs=1e-20)


def test_constant_feature_rejected():
    with pytest.raises(ValueError, match="constant"):
        analyze(Request(features=[[1]] * 30, target=list(range(30))))


def test_api_and_ui():
    import json
    from pathlib import Path

    client = TestClient(app)
    payload = json.loads(
        (Path(__file__).parents[1] / "examples/synthetic.json").read_text()
    )
    response = client.post("/analyze", json=payload)
    assert response.status_code == 200, response.text
    assert isinstance(response.json(), dict)
    assert client.get("/health").json() == {"status": "ok"}
    assert client.get("/").status_code == 200
    assert client.post("/analyze", json={}).status_code == 422


def test_nonfinite_rejected():
    import json
    from pathlib import Path

    payload = json.loads(
        (Path(__file__).parents[1] / "examples/synthetic.json").read_text()
    )
    key = next(iter(payload))
    if isinstance(payload[key][0], list):
        payload[key][0][0] = "nan"
    else:
        payload[key][0] = "nan"
    assert TestClient(app).post("/analyze", json=payload).status_code == 422


def test_split_and_result_reproducible():
    rng = np.random.default_rng(9)
    x = rng.normal(size=(60, 2))
    req = Request(features=x.tolist(), target=(x[:, 0] + rng.normal(size=60)).tolist())
    a, b = analyze(req), analyze(req)
    assert a == b
    assert len(set(a["test_indices"])) == a["test_rows"]
    assert a["train_rows"] + a["test_rows"] == 60


def test_holdout_target_not_used_for_fit():
    rng = np.random.default_rng(12)
    x = rng.normal(size=(60, 2))
    y = (3 * x[:, 0]).tolist()
    original = analyze(Request(features=x.tolist(), target=y))
    for index in original["test_indices"]:
        y[index] += 100
    changed = analyze(Request(features=x.tolist(), target=y))
    assert changed["predictions"] == original["predictions"]
    assert changed["held_out_mse"] == pytest.approx(10000)


def test_name_count_rejected():
    from pydantic import ValidationError

    with pytest.raises(ValidationError):
        Request(features=[[1, 2]] * 20, target=list(range(20)), feature_names=["only"])
