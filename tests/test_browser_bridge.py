from copy import deepcopy
from itertools import product
import sys
from pathlib import Path
import pytest
from app.server import load_profile
from ahp_feedstock.m2 import evaluate_m2
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'web'))
from bridge import handle

@pytest.mark.parametrize('states',list(product(['descarte','nao_descarte'],['incidental_comprovada','intencionalidade_demonstrada','evidencia_insuficiente'],['C3a-R1','C3a-R2','C3a-R3'],['C3b-R1','C3b-R2','C3b-R3'])))
def test_browser_transport_matches_original(states):
 profile=load_profile()
 profile['case']['states']=dict(zip(['C1','C2','C3a','C3b'],states))
 for item in profile['case']['state_evidence'].values(): item['status']='user_reported_unverified'
 expected=evaluate_m2(deepcopy(profile),allow_draft=True,consistency_policy='block')
 actual=handle('/api/evaluate',{'case':profile['case'],'allow_draft':True})
 assert actual==expected
 assert actual['final_classification'] is None

@pytest.mark.parametrize('weights',[[1,0,0],[0,1,0],[0,0,1],[.6,.2,.2]])
def test_browser_transport_sensitivity(weights):
 profile=load_profile()
 for item in profile['case']['state_evidence'].values(): item['status']='user_reported_unverified'
 actual=handle('/api/sensitivity',{'case':profile['case'],'allow_draft':True,'weights':weights})
 assert actual['exploratory']['final_classification'] is None
 assert sum(actual['exploratory']['computational_candidate']['priorities'].values())==pytest.approx(1)
 assert actual['engine_source_sha256']
