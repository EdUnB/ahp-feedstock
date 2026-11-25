import json,hashlib
from pathlib import Path
from copy import deepcopy
from datetime import datetime,timezone
from uuid import uuid4
from ahp_feedstock.m2 import evaluate_m2
from app.sensitivity import analyze
ROOT=Path(__file__).resolve().parent
if not (ROOT/'engine').is_dir(): ROOT=ROOT.parent
CONFIG=ROOT/'engine/config/m2_DEMO_SINTETICO.json'
ALLOWED={'C1':{'descarte','nao_descarte'},'C2':{'incidental_comprovada','intencionalidade_demonstrada','evidencia_insuficiente'},'C3a':{'C3a-R1','C3a-R2','C3a-R3'},'C3b':{'C3b-R1','C3b-R2','C3b-R3'}}
def handle(path,payload):
 profile=json.loads(CONFIG.read_text(encoding='utf-8'))
 if path=='/api/health':return {'status':'operational','software_version':'0.1.0-browser-preview','local_research_preview_enabled':True,'scientific_validation':False,'lca_integration':False,'execution':'browser-python'}
 if path=='/api/metadata':return {'model_version':profile['version'],'classes':profile['classes'],'calibration_status':profile['calibration']['status'],'calibration_notice':profile['calibration']['warning'],'root_pairwise':profile['root']['pairwise'],'config_sha256':hashlib.sha256(CONFIG.read_bytes()).hexdigest(),'classification_status':'EXPLORATORIO_NAO_VALIDADO','states':{k:sorted(v) for k,v in ALLOWED.items()},'lca_automatic_boundary_selection':False}
 if path not in ('/api/evaluate','/api/sensitivity'):raise ValueError('Unknown operation')
 if payload.get('allow_draft') is not True:raise ValueError('Confirmar natureza exploratória da análise.')
 case=payload['case']
 for key,allowed in ALLOWED.items():
  if case['states'].get(key) not in allowed:raise ValueError('Estado inválido: '+key)
  evidence=case['state_evidence'].get(key,{})
  if evidence.get('status')!='user_reported_unverified' or not evidence.get('claim','').strip():raise ValueError('Informar justificativa: '+key)
 profile['case']=case
 if path=='/api/evaluate':return evaluate_m2(profile,allow_draft=True,consistency_policy='block')
 output=analyze(profile,payload['weights'])
 output.update(configuration_sha256=hashlib.sha256(CONFIG.read_bytes()).hexdigest(),software_version='0.1.0-browser-preview',engine_model_version=profile['version'],run_id=str(uuid4()),calculated_at_utc=datetime.now(timezone.utc).isoformat(),user_case=deepcopy(case),reference_configuration=deepcopy(profile),engine_source_sha256={p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in sorted((ROOT/'engine/ahp_feedstock').glob('*.py'))})
 base=output['baseline']['computational_candidate'];adjusted=output['exploratory']['computational_candidate']
 output['classification_changed']=(base['winner'],base['tie'])!=(adjusted['winner'],adjusted['tie'])
 output['priority_delta']={name:adjusted['priorities'][name]-value for name,value in base['priorities'].items()}
 return output
