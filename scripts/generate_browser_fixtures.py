from pathlib import Path
import sys,itertools,json
root=Path(__file__).resolve().parents[1]
sys.path[:0]=[str(root),str(root/'engine')]
from app.server import load_profile
from ahp_feedstock.m2 import evaluate_m2
fixtures=[]
for states in itertools.product(['descarte','nao_descarte'],['incidental_comprovada','intencionalidade_demonstrada','evidencia_insuficiente'],['C3a-R1','C3a-R2','C3a-R3'],['C3b-R1','C3b-R2','C3b-R3']):
 profile=load_profile();profile['case']['states']=dict(zip(['C1','C2','C3a','C3b'],states))
 for item in profile['case']['state_evidence'].values():item['status']='user_reported_unverified'
 fixtures.append({'case':profile['case'],'candidate':evaluate_m2(profile,allow_draft=True,consistency_policy='block')['computational_candidate']})
out=root/'local-private/browser-audit';out.mkdir(parents=True,exist_ok=True)
(out/'native-fixtures.json').write_text(json.dumps(fixtures,ensure_ascii=False),encoding='utf-8')
print('Native browser references generated:',len(fixtures))
