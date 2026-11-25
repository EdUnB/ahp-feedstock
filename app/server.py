"""AHP Feedstock: interface web local, independente da ferramenta ACV.

O motor AHP original está em engine/ahp_feedstock, sem modificações.
Baseline M2 interno preservado; pesos diretos apenas em cenários exploratórios.
Esta aplicação é experimental e NÃO deve ser exposta publicamente sem revisão.
"""
from __future__ import annotations

import hashlib
import json
import os
import sys
from datetime import datetime, timezone
from uuid import uuid4
from copy import deepcopy
from pathlib import Path
from typing import Any

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, ConfigDict, Field, ValidationError

ROOT = Path(__file__).resolve().parent.parent
ENGINE_DIR = ROOT / 'engine'
if str(ENGINE_DIR) not in sys.path:
    sys.path.insert(0, str(ENGINE_DIR))
from ahp_feedstock.m2 import evaluate_m2  # noqa: E402

CONFIG = ENGINE_DIR / 'config' / 'm2_DEMO_SINTETICO.json'
STATIC = ROOT / 'app' / 'static'
MAX_PAYLOAD_BYTES = 80_000

app = FastAPI(
    title='LEA / AHP Feedstock Classification · interface experimental',
    description='Motor Python original; M2 exploratory; no legal or LCA boundary inference.',
    version='2.0.0-ui-sensitivity-research',
    docs_url='/api/docs', redoc_url=None, openapi_url='/api/openapi.json',
)
app.mount('/assets', StaticFiles(directory=str(STATIC)), name='assets')

class Evidence(BaseModel):
    model_config = ConfigDict(extra='forbid')
    status: str = 'user_reported_unverified'
    claim: str = Field(min_length=5, max_length=3500)

class States(BaseModel):
    model_config = ConfigDict(extra='forbid')
    C1: str
    C2: str
    C3a: str
    C3b: str

class ContextItem(BaseModel):
    model_config = ConfigDict(extra='forbid')
    status: str
    assessment: str = Field(min_length=3, max_length=2500)
    source: str = Field(min_length=3, max_length=1500)

class C4(BaseModel):
    model_config = ConfigDict(extra='forbid')
    technology: ContextItem
    logistics: ContextItem

class Processing(BaseModel):
    model_config = ConfigDict(extra='forbid')
    type: str
    assessment: str = Field(min_length=3, max_length=2500)
    source: str = Field(min_length=3, max_length=1500)

class RegulatoryBasis(BaseModel):
    model_config = ConfigDict(extra='forbid')
    framework: str = Field(min_length=3, max_length=1000)
    status: str

class Checks(BaseModel):
    model_config = ConfigDict(extra='forbid')
    C4: C4
    processing: Processing
    regulatory_basis: RegulatoryBasis

class Case(BaseModel):
    model_config = ConfigDict(extra='forbid')
    material: str = Field(min_length=2, max_length=300)
    classification_point: str = Field(min_length=5, max_length=900)
    region: str = Field(default='', max_length=300)
    states: States
    state_evidence: dict[str, Evidence]
    complementary_checks: Checks

class EvaluateRequest(BaseModel):
    model_config = ConfigDict(extra='forbid')
    case: Case
    allow_draft: bool = False

ALLOWED = {
    'C1': {'descarte', 'nao_descarte'},
    'C2': {'incidental_comprovada', 'intencionalidade_demonstrada', 'evidencia_insuficiente'},
    'C3a': {'C3a-R1', 'C3a-R2', 'C3a-R3'},
    'C3b': {'C3b-R1', 'C3b-R2', 'C3b-R3'},
}

def load_profile() -> dict[str, Any]:
    return json.loads(CONFIG.read_text(encoding='utf-8'))

@app.get('/', include_in_schema=False)
def home():
    return FileResponse(str(STATIC / 'index.html'), headers={'Cache-Control': 'no-store', 'X-Content-Type-Options': 'nosniff'})

@app.get('/api/health')
def health():
    return {
        'status': 'operational',
        'software_version': '2.0.0',
        'instance_id': os.environ.get('AHP_INSTANCE_ID'),
        'local_research_preview_enabled': os.environ.get('AHP_ENABLE_DRAFT') == '1',
        'scientific_validation': False,
        'lca_integration': False,
    }


@app.get('/styles.css', include_in_schema=False)
def root_styles():
    return FileResponse(STATIC / 'styles.css', media_type='text/css', headers={'Cache-Control': 'no-store'})


@app.get('/app.js', include_in_schema=False)
def root_script():
    return FileResponse(STATIC / 'app.js', media_type='text/javascript', headers={'Cache-Control': 'no-store'})


@app.get('/sensitivity.js', include_in_schema=False)
def root_sensitivity_script():
    return FileResponse(STATIC / 'sensitivity.js', media_type='text/javascript', headers={'Cache-Control': 'no-store'})

@app.get('/api/metadata')
def metadata():
    profile = load_profile()
    return {
        'model_version': profile['version'],
        'classes': profile['classes'],
        'calibration_status': profile['calibration']['status'],
        'calibration_notice': profile['calibration']['warning'],
        'root_pairwise': profile['root']['pairwise'],
        'config_sha256': hashlib.sha256(CONFIG.read_bytes()).hexdigest(),
        'classification_status': 'EXPLORATORIO_NAO_VALIDADO',
        'states': {k: sorted(v) for k, v in ALLOWED.items()},
        'lca_automatic_boundary_selection': False,
    }

def validate_case(case: Case):
    states = case.states.model_dump()
    for key, value in states.items():
        if value not in ALLOWED[key]:
            raise HTTPException(422, detail=f'Estado inválido para {key}: {value}')
    if set(case.state_evidence) != set(states):
        raise HTTPException(422, detail='Informar fonte/justificativa para C1, C2, C3a e C3b, separadamente.')
    for key, record in case.state_evidence.items():
        if record.status != 'user_reported_unverified':
            raise HTTPException(422, detail=f'Evidência {key}: status não permitido nesta interface.')
        if not record.claim.strip():
            raise HTTPException(422, detail=f'Evidência {key} sem justificativa.')
    checks = case.complementary_checks
    for item in (checks.C4.technology, checks.C4.logistics):
        if item.status not in {'viable','limited','nonviable','unknown'}:
            raise HTTPException(422, detail='Estado de tecnologia/logística inválido')
    if checks.processing.type not in {'direct_use','normal_industrial_practice','dedicated_conversion','unknown'}:
        raise HTTPException(422, detail='Processamento inválido')
    if checks.regulatory_basis.status not in {'assessed','not_assessed','conflicting'}:
        raise HTTPException(422, detail='Status regulatório inválido')

@app.post('/api/evaluate')
async def evaluate(request_data: EvaluateRequest):
    if os.environ.get('AHP_ENABLE_DRAFT') != '1':
        raise HTTPException(403, detail='Simulação desativada. Use os lançadores locais de desenvolvimento.')
    if request_data.allow_draft is not True:
        raise HTTPException(400, detail='É obrigatório confirmar a natureza exploratória da análise.')
    case = request_data.case
    validate_case(case)
    profile = load_profile()  # Matriz e pesos SEMPRE vindos do servidor, nunca do navegador.
    profile['case'] = case.model_dump()
    try:
        result = evaluate_m2(profile, allow_draft=True, consistency_policy='block')
    except (ValueError, TypeError, KeyError) as exc:
        raise HTTPException(422, detail=str(exc)) from exc
    # Reafirmação: resultado experimental NÃO se transforma em determinação final.
    assert result['final_classification'] is None
    assert result['separation']['acv_boundary_inferred'] is False
    return result


class SensitivityRequest(EvaluateRequest):
    weights: list[float] = Field(min_length=3, max_length=3)


@app.post('/api/sensitivity')
async def sensitivity(request_data: SensitivityRequest):
    # Reuse original consent, environment and case validation.
    await evaluate(EvaluateRequest(case=request_data.case, allow_draft=request_data.allow_draft))
    from .sensitivity import analyze
    profile = load_profile()
    profile['case'] = request_data.case.model_dump()
    try:
        output = analyze(profile, request_data.weights)
    except (ValueError, TypeError, KeyError) as exc:
        raise HTTPException(422, detail=str(exc)) from exc
    output['configuration_sha256'] = hashlib.sha256(CONFIG.read_bytes()).hexdigest()
    output['software_version'] = '2.0.0'
    output['engine_model_version'] = profile['version']
    output['run_id'] = str(uuid4())
    output['calculated_at_utc'] = datetime.now(timezone.utc).isoformat()
    output['user_case'] = request_data.case.model_dump()
    output['reference_configuration'] = deepcopy(profile)
    output['engine_source_sha256'] = {p.name: hashlib.sha256(p.read_bytes()).hexdigest()
                                      for p in sorted((ENGINE_DIR / 'ahp_feedstock').glob('*.py'))}
    base = output['baseline']['computational_candidate']
    adjusted = output['exploratory']['computational_candidate']
    output['classification_changed'] = (base['winner'], base['tie']) != (adjusted['winner'], adjusted['tie'])
    output['priority_delta'] = {name: adjusted['priorities'][name]-value for name,value in base['priorities'].items()}
    return output
