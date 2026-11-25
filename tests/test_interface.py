"""Verificação funcional e científica da camada HTML/API, sem alterar o motor original."""
import hashlib
import json
import os
from copy import deepcopy
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.server import ROOT, CONFIG, app, load_profile, validate_case, Case
from ahp_feedstock.m2 import evaluate_m2

client = TestClient(app)

@pytest.fixture(autouse=True)
def experimental_mode(monkeypatch):
    monkeypatch.setenv('AHP_ENABLE_DRAFT', '1')


def synthetic_case():
    case = load_profile()['case']
    for record in case['state_evidence'].values():
        record['status'] = 'user_reported_unverified'
    return case


def test_root_serves_html():
    response = client.get('/')
    assert response.status_code == 200
    assert 'Classificação de matérias-primas' in response.text
    assert 'Versão experimental' in response.text
    assert client.get('/assets/app.js').status_code == 200
    assert client.get('/assets/styles.css').status_code == 200


def test_metadata_is_grounded_in_config():
    response = client.get('/api/metadata')
    assert response.status_code == 200
    body = response.json()
    assert body['model_version'] == load_profile()['version']
    assert body['config_sha256'] == hashlib.sha256(CONFIG.read_bytes()).hexdigest()
    assert body['root_pairwise'] == [[1,3,3],[1/3,1,1],[1/3,1,1]]
    assert not body['lca_automatic_boundary_selection']


def test_direct_engine_regression():
    case = synthetic_case()
    reference = evaluate_m2(load_profile(), allow_draft=True)
    response = client.post('/api/evaluate', json={'case':case,'allow_draft':True})
    assert response.status_code == 200, response.text
    body = response.json()
    assert body['computational_candidate']['winner'] == reference['computational_candidate']['winner']
    for name, val in reference['computational_candidate']['priorities'].items():
        assert body['computational_candidate']['priorities'][name] == pytest.approx(val,abs=1e-12)
    assert body['computational_candidate']['margin'] == pytest.approx(reference['computational_candidate']['margin'],abs=1e-12)
    assert body['final_classification'] is None
    assert not body['separation']['acv_boundary_inferred']
    assert sum(body['computational_candidate']['priorities'].values()) == pytest.approx(1,abs=1e-12)


def test_synthetic_known_values():
    body = client.post('/api/evaluate',json={'case':synthetic_case(),'allow_draft':True}).json()
    scores=body['computational_candidate']['priorities']
    assert scores['resíduo'] == pytest.approx(.17723886059712776,abs=1e-10)
    assert scores['subproduto'] == pytest.approx(.45275257261821233,abs=1e-10)
    assert scores['coproduto'] == pytest.approx(.3700085667846598,abs=1e-10)
    assert body['ahp']['terminal_weights']['C3a'] == pytest.approx(.15)
    assert body['ahp']['terminal_weights']['C3b'] == pytest.approx(.05)
    assert all(x['acceptable'] for x in body['ahp']['consistency'].values())


def test_context_does_not_affect_ahp():
    case = synthetic_case()
    base = client.post('/api/evaluate',json={'case':case,'allow_draft':True}).json()
    changed = deepcopy(case)
    changed['complementary_checks']['C4']['technology']['status'] = 'nonviable'
    changed['complementary_checks']['C4']['logistics']['status'] = 'limited'
    changed['complementary_checks']['processing']['type'] = 'dedicated_conversion'
    changed['complementary_checks']['regulatory_basis']['status'] = 'assessed'
    other = client.post('/api/evaluate',json={'case':changed,'allow_draft':True}).json()
    assert other['computational_candidate'] == base['computational_candidate']


def test_missing_draft_consent_rejected():
    r=client.post('/api/evaluate',json={'case':synthetic_case(),'allow_draft':False})
    assert r.status_code == 400


def test_disabled_by_default_when_env_unset(monkeypatch):
    monkeypatch.delenv('AHP_ENABLE_DRAFT',raising=False)
    r=client.post('/api/evaluate',json={'case':synthetic_case(),'allow_draft':True})
    assert r.status_code == 403


def test_root_configuration_client_override_rejected():
    r=client.post('/api/evaluate',json={'case':synthetic_case(),'allow_draft':True,'root':{'pairwise':[[1,9,9],[1/9,1,1],[1/9,1,1]]}})
    assert r.status_code == 422


def test_reject_unknown_states():
    case=synthetic_case();case['states']['C3a']='C3a-R99'
    r=client.post('/api/evaluate',json={'case':case,'allow_draft':True})
    assert r.status_code == 422


def test_requires_evidence_for_all_criteria():
    case=synthetic_case();case['state_evidence'].pop('C3b')
    r=client.post('/api/evaluate',json={'case':case,'allow_draft':True})
    assert r.status_code == 422


def test_known_original_source_hashes():
    ref=(ROOT/'engine/HASHES_MOTOR_ORIGINAL.txt').read_text(encoding='utf-8').strip().splitlines()
    assert len(ref)==12
    for line in ref:
        expected,rel=line.split('  ',1)
        assert hashlib.sha256((ROOT/rel).read_bytes()).hexdigest()==expected


def test_different_states_change_numerical_response():
    case=synthetic_case()
    base=client.post('/api/evaluate',json={'case':case,'allow_draft':True}).json()['computational_candidate']
    case['states']['C1']='descarte'
    changed=client.post('/api/evaluate',json={'case':case,'allow_draft':True}).json()['computational_candidate']
    assert base['priorities'] != changed['priorities']
