"""Computational equivalence is not external scientific validation."""
from copy import deepcopy
import itertools
import json
import math
import pytest
from fastapi.testclient import TestClient
from app.server import app, load_profile
from app.sensitivity import analyze, geometry, weighted_profile
from ahp_feedstock.core import aggregate, rank
from ahp_feedstock.m2 import evaluate_m2

client = TestClient(app)


@pytest.fixture(autouse=True)
def enabled(monkeypatch):
    monkeypatch.setenv('AHP_ENABLE_DRAFT', '1')


def request(weights):
    case = load_profile()['case']
    for ev in case['state_evidence'].values():
        ev['status'] = 'user_reported_unverified'
    return {'case': case, 'allow_draft': True, 'weights': weights}


def assert_candidate(actual, expected):
    assert actual['priorities'] == pytest.approx(expected['priorities'], abs=1e-12, rel=0)
    assert actual['margin'] == pytest.approx(expected['margin'], abs=1e-12, rel=0)
    assert actual['winner'] == expected['winner']
    assert actual['tie'] == expected['tie']
    assert actual['ranking'] == expected['ranking']


@pytest.mark.parametrize('states', list(itertools.product(
    ['descarte','nao_descarte'],
    ['incidental_comprovada','intencionalidade_demonstrada','evidencia_insuficiente'],
    ['C3a-R1','C3a-R2','C3a-R3'], ['C3b-R1','C3b-R2','C3b-R3'])))
def test_all_54_state_combinations(states):
    profile = load_profile()
    profile['case']['states'] = dict(zip(['C1','C2','C3a','C3b'], states))
    before = deepcopy(profile)
    geom = geometry(json.dumps(profile, sort_keys=True))
    classes = profile['classes']
    weights_list = [[.6,.2,.2], [1,0,0], [0,1,0], [0,0,1], [0,.5,.5],
                    [.1,.7,.2], [.333,.333,.334], [.999,.0005,.0005]]
    for weights in weights_list:
        # Full original evaluation vs accelerated fixed-priority geometry.
        expected = evaluate_m2(weighted_profile(profile, weights), allow_draft=True)['computational_candidate']
        actual = rank(aggregate(weights, geom['vectors']), classes)
        assert_candidate(actual, expected)
    assert profile == before


def test_full_grid_and_sweeps_against_original():
    profile = load_profile()
    output = analyze(profile, [.6,.2,.2])
    assert_candidate(output['baseline']['computational_candidate'], output['exploratory']['computational_candidate'])
    points = output['grid'] + sum(output['sweeps'].values(), [])
    assert len(points) == 534
    for point in points:
        assert sum(point['weights']) == pytest.approx(1, abs=1e-14)
        expected = evaluate_m2(weighted_profile(profile,point['weights']), allow_draft=True)['computational_candidate']
        assert_candidate(point['candidate'], expected)


def test_api_baseline_unchanged_and_no_final():
    payload = request([.2,.3,.5])
    before = load_profile()
    r = client.post('/api/sensitivity', json=payload)
    assert r.status_code == 200, r.text
    data = r.json()
    baseline = client.post('/api/evaluate', json={k:v for k,v in payload.items() if k!='weights'}).json()
    assert data['baseline'] == baseline
    assert data['baseline_weights'] == pytest.approx([.6,.2,.2])
    for mode in ['baseline','exploratory']:
        assert data[mode]['final_classification'] is None
        assert not data[mode]['separation']['acv_boundary_inferred']
    assert not data['scientific_validation']
    assert data['exploratory']['ahp']['terminal_weights']['C3a'] == pytest.approx(.375)
    assert data['exploratory']['ahp']['terminal_weights']['C3b'] == pytest.approx(.125)
    assert 'root' not in data['exploratory']['ahp']['consistency']
    assert load_profile() == before


@pytest.mark.parametrize('weights', [[0,0,0],[-.1,.5,.6],[1,1,1],[.5,.5], [1.1,0,-.1]])
def test_invalid_api_weights(weights):
    assert client.post('/api/sensitivity', json=request(weights)).status_code == 422


def test_nonfinite_weights():
    for bad in [math.nan,math.inf,-math.inf]:
        with pytest.raises(ValueError): weighted_profile(load_profile(), [bad,0,1])


def test_consent_and_environment(monkeypatch):
    payload=request([.6,.2,.2]); payload['allow_draft']=False
    assert client.post('/api/sensitivity',json=payload).status_code == 400
    payload['allow_draft']=True;monkeypatch.delenv('AHP_ENABLE_DRAFT')
    assert client.post('/api/sensitivity',json=payload).status_code == 403


def test_tie_uses_original_tolerance():
    assert rank([.4,.4,.2])['tie']
    assert rank([.4,.4,.2])['winner'] is None
