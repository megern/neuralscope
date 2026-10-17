"""Independent held-out-label perturbations verify diagnostic indexing and no fit leakage."""
import pytest
from fastapi.testclient import TestClient
from app.main import app
client=TestClient(app)


def test_independent_heldout_outlier_outside_preview_is_in_global_worst_case_summary():
    n=2200
    data={'features':[[i] for i in range(n)],'target':[2+3*i for i in range(n)],'test_fraction':0.5,'seed':42,'repeats':1,'feature_names':['Synthetic slope']}
    first=client.post('/analyze',json=data)
    assert first.status_code==200
    baseline=first.json();outlier=baseline['test_indices'][1080]
    data['target'][outlier]+=500
    second=client.post('/analyze',json=data)
    assert second.status_code==200
    result=second.json()
    assert result['predictions']==pytest.approx(baseline['predictions'])
    assert result['diagnostic_summary']['evaluated_rows']==1100
    assert result['diagnostic_summary']['reported_rows']==1000
    assert result['diagnostic_summary']['truncated']
    assert outlier not in [row['row_index'] for row in result['held_out_diagnostics']]
    assert result['worst_cases'][0]['row_index']==outlier
    assert result['worst_cases'][0]['residual']==pytest.approx(500)
    assert result['worst_cases'][0]['absolute_error']==pytest.approx(500)
    assert result['diagnostic_summary']['mean_absolute_error']==pytest.approx(500/1100,abs=1e-8)
    assert result['held_out_mse']==pytest.approx(500**2/1100)
    assert len(result['worst_cases'])==20
