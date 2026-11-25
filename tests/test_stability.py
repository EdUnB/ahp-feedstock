import json
import shutil
import subprocess
import io
import os
import csv
from pathlib import Path
import pytest
from fastapi.testclient import TestClient
from app.server import app,load_profile
from app.sensitivity import analyze
from app.stability import analytical_stability,path_weights,TIE_TOL
from ahp_feedstock.core import aggregate,rank
from ahp_feedstock.m2 import evaluate_m2


def test_analytic_identity_vectors_have_known_transition():
    vectors=[[1,0,0],[0,1,0],[0,0,1]]
    data=analytical_stability([.6,.2,.2],vectors,['W','B','C'])
    # With w2=w3=(1-w1)/2, unique W starts at w1>(1+2tol)/3.
    intervals=data['paths']['C1']['intervals']
    assert intervals[0]['tie']
    assert intervals[-1]['winner']=='W'
    assert intervals[-1]['lower']==pytest.approx((1+2*TIE_TOL)/3,abs=1e-15,rel=0)
    for region in data['regions']:
        assert region['vertices']
        center=[sum(p[i] for p in region['vertices'])/len(region['vertices']) for i in range(3)]
        assert rank(aggregate(center,vectors),['W','B','C'])['winner']==region['winner']


def test_all_equal_vectors_have_only_tie_intervals_and_empty_winner_regions():
    data=analytical_stability([.6,.2,.2],[[.3,.3,.4]]*3,['W','B','C'])
    # Constant unique C is independent of root weights.
    assert all(p['intervals']==[{'lower':0.,'upper':1.,'winner':'C','tie':False}] for p in data['paths'].values())
    tie=analytical_stability([1,0,0],[[.4,.4,.2]]*3,['W','B','C'])
    assert all(p['intervals'][0]['tie'] for p in tie['paths'].values())
    assert all(not r['vertices'] for r in tie['regions'])
    assert path_weights([1,0,0],0,.5)==[.5,.25,.25]


def test_computed_intervals_cover_domain_and_match_engine_at_interior_points():
    output=analyze(load_profile(),[.2,.3,.5])
    for i,path in enumerate(output['stability']['paths'].values()):
        intervals=path['intervals']
        assert intervals[0]['lower']==0 and intervals[-1]['upper']==1
        for a,b in zip(intervals,intervals[1:]): assert a['upper']==b['lower']
        for interval in intervals:
            for fraction in [.2,.5,.8]:
                x=interval['lower']+(interval['upper']-interval['lower'])*fraction
                result=rank(aggregate(path_weights(output['baseline_weights'],i,x),output['vectors']),list(output['baseline']['computational_candidate']['priorities']))
                assert result['winner']==interval['winner']
                assert result['tie']==interval['tie']


def test_api_and_csv_exports_reproduce_execution(monkeypatch):
    monkeypatch.setenv('AHP_ENABLE_DRAFT','1')
    case=load_profile()['case']
    for ev in case['state_evidence'].values(): ev['status']='user_reported_unverified'
    client=TestClient(app)
    response=client.post('/api/sensitivity',json={'case':case,'allow_draft':True,'weights':[.1,.1,.8]})
    assert response.status_code==200
    data=response.json()
    assert data['software_version']=='2.0.0'
    assert len(data['engine_source_sha256'])==12
    assert data['run_id'] and data['calculated_at_utc']
    assert data['user_case']==case
    assert evaluate_m2(data['reference_configuration'],allow_draft=True)==data['baseline']
    node=shutil.which('node')
    if not node: pytest.fail('Node.js is required for production control/export verification')
    run=subprocess.run([node,str(Path(__file__).with_name('check_controls_exports.cjs'))],
                       input=json.dumps(data,ensure_ascii=False),text=True,encoding='utf-8',capture_output=True)
    assert run.returncode==0,run.stderr
    result=json.loads(run.stdout)
    assert result['rows']==537
    assert evaluate_m2(result['metadata']['reference_configuration'],allow_draft=True)==data['baseline']
    json_export=json.loads(result['exports'][0]['content'])
    csv_export=list(csv.reader(io.StringIO(result['exports'][1]['content'].lstrip('\ufeff')),delimiter=';'))
    assert json_export['run_id']==data['run_id']
    assert json_export['user_case']==case
    assert len(csv_export)==537
    metadata=json.loads(csv_export[1][csv_export[0].index('execution_metadata_json')])
    assert metadata['run_id']==json_export['run_id']
    assert metadata['reference_configuration']==json_export['reference_configuration']


def test_launcher_waits_for_own_instance_before_opening_browser(monkeypatch):
    import iniciar
    import uvicorn
    callbacks=[];opened=[];checks=[];server=[]
    class FakeThread:
        def __init__(self,target,daemon): callbacks.append(target)
        def start(self): pass
    def health(url,timeout):
        checks.append(url)
        token='old-instance' if len(checks)==1 else os.environ['AHP_INSTANCE_ID']
        return io.BytesIO(json.dumps({'instance_id':token}).encode())
    def start_server(target,host,port):
        server.append((target,host,port))
        callbacks[0]()
    monkeypatch.setattr(iniciar.threading,'Thread',FakeThread)
    monkeypatch.setattr(iniciar.urllib.request,'urlopen',health)
    monkeypatch.setattr(iniciar.webbrowser,'open',opened.append)
    monkeypatch.setattr(iniciar.time,'sleep',lambda _:None)
    monkeypatch.setattr(iniciar.os,'chdir',lambda _:None)
    monkeypatch.setattr(uvicorn,'run',start_server)
    monkeypatch.setenv('AHP_INSTANCE_ID','before-test')
    monkeypatch.setenv('AHP_ENABLE_DRAFT','0')
    iniciar.main()
    assert len(checks)==2 and len(opened)==1
    assert opened[0]==f'http://127.0.0.1:{server[0][2]}'
    assert checks[1]==opened[0]+'/api/health'
    assert server[0][0]=='app.server:app' and server[0][1]=='127.0.0.1'
