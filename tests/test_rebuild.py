"""Fresh 0.2.0 HTTP and synthetic CSV integration checks."""

import csv
import io
import json
from pathlib import Path
from fastapi.testclient import TestClient
from app.main import app

BASE = Path(__file__).parents[1]


def synthetic_request():
    config = json.loads(
        (BASE / "app/static/config.js").read_text().split(" = ", 1)[1].rstrip(";\n")
    )
    rows = list(csv.DictReader(io.StringIO(config["sample"])))
    column = lambda name: [float(row[name]) for row in rows]
    request = {p[0]: p[2] for p in config["params"]}
    kind = config["slug"]
    if kind == "quantforge":
        request.update(prices=column("prices"), signals=column("signals"))
    elif kind == "causallab":
        request.update(
            outcome=column("outcome"),
            treatment=[int(x) for x in column("treatment")],
            confounders=[
                [float(row["baseline"]), float(row["experience"])] for row in rows
            ],
        )
    elif kind == "neuralscope":
        request.update(
            target=column("target"),
            features=[[float(row["signal"]), float(row["noise"])] for row in rows],
            feature_names=["signal", "noise"],
        )
    else:
        request.update(values=column("values"), method="drift")
    return kind, request


def test_rebuild_static_workbench_and_packaged_guide():
    client = TestClient(app)
    response = client.get("/")
    assert response.status_code == 200
    assert 'id="csv-file"' in response.text
    assert 'id="mapping"' in response.text
    assert 'id="chart"' in response.text
    assert "textarea" not in response.text
    for asset in ["data.js", "workbench.js", "config.js", "style.css"]:
        assert client.get("/static/" + asset).status_code == 200
    guide = client.get("/guide")
    assert guide.status_code == 200
    assert "text/plain" in guide.headers["content-type"]
    assert "Export and replay" in guide.text
    assert (BASE / "docs/USER_GUIDE.md").read_text() == (
        BASE / "app/USER_GUIDE.md"
    ).read_text()
    assert app.version == "0.4.0"


def test_rebuild_synthetic_csv_payload_and_replay():
    kind, request = synthetic_request()
    client = TestClient(app)
    first = client.post("/analyze", json=request)
    assert first.status_code == 200, first.text
    # Downloaded input is serialized JSON; exact replay must preserve computation.
    replay = client.post(
        "/analyze",
        content=json.dumps(request),
        headers={"Content-Type": "application/json"},
    )
    assert replay.json() == first.json()
    result = first.json()
    if kind == "quantforge":
        assert len(result["equity"]) == len(request["prices"])
        assert result["turnover"] > 0
    elif kind == "causallab":
        assert abs(result["treatment_effect"] - 3) < 0.1
        assert result["robust_standard_error"] > 0
    elif kind == "neuralscope":
        assert result["held_out_r2"] > 0.99
        assert result["importance"][0]["feature"] == "signal"
    else:
        assert len(result["holdout_prediction"]) == request["holdout"]
        assert len(result["future_forecast"]) == request["horizon"]
        assert result["mae"] > 0


def test_rebuild_asset_escape_and_no_remote_dependency():
    client = TestClient(app)
    assert client.get("/static/../main.py").status_code == 404
    html = client.get("/").text
    assert 'src="https://' not in html
    assert 'href="https://' not in html
    js = client.get("/static/workbench.js").text
    assert ".innerHTML" not in js
    assert ".textContent" in js
