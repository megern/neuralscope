import numpy as np
from fastapi.testclient import TestClient
from app.main import Request, analyze, app

def dataset():
    x=np.column_stack([np.arange(60),np.random.default_rng(8).normal(size=60)])
    return x, 5+3*x[:,0]

def test_reviewer_linear_truth_and_importance():
    x,y=dataset(); r=analyze(Request(features=x.tolist(),target=y.tolist(),feature_names=['cause_like','noise'],seed=7,repeats=5))
    coefficients={i['feature']:i['coefficient'] for i in r['importance']}
    assert abs(coefficients['cause_like']-3)<1e-10 and abs(coefficients['noise'])<1e-10
    assert abs(r['intercept']-5)<1e-10
    assert r['held_out_mse']<1e-18 and abs(r['held_out_r2']-1)<1e-12
    assert r['importance'][0]['feature']=='cause_like'

def test_reviewer_holdout_target_never_changes_fit():
    x,y=dataset(); a=analyze(Request(features=x.tolist(),target=y.tolist(),seed=42,repeats=1))
    y[a['test_indices']]+=1000
    b=analyze(Request(features=x.tolist(),target=y.tolist(),seed=42,repeats=1))
    assert np.allclose(a['predictions'],b['predictions'])
    assert np.isclose(a['intercept'],b['intercept'])
    assert b['held_out_mse']>100000

def test_reviewer_rank_deficient_features_rejected():
    x=np.column_stack([np.arange(30),np.arange(30)])
    assert TestClient(app).post('/analyze',json={'features':x.tolist(),'target':list(range(30))}).status_code==422
