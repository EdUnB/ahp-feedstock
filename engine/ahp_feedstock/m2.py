"""Arquitetura experimental M2: AHP de classificação + verificações contextuais separadas.

Mantém core.evaluate() intocado e não presume que C2/C4 estejam cientificamente calibrados.
"""
from __future__ import annotations
from copy import deepcopy
import argparse
import json
from pathlib import Path
from .core import evaluate

C4_STATUS = frozenset({'viable','limited','nonviable','unknown'})
PROCESSING_TYPES = frozenset({'direct_use','normal_industrial_practice','dedicated_conversion','unknown'})
REGULATORY_STATUS = frozenset({'assessed','not_assessed','conflicting'})


def evaluate_m2(profile, *, allow_draft=False, consistency_policy='block'):
    """Return a *candidate* AHP ranking and separate complementary checks.

    Draft weights must be explicitly enabled for a computational preview. Even
    with allow_draft=True, final_classification is None until calibrated and
    evidentially supported. C4, processing and ACV never modify AHP priorities.
    """
    if not isinstance(profile, dict) or not str(profile.get('version','')).startswith('M2-'):
        raise ValueError('É necessária uma configuração M2 explícita')
    calib = profile.get('calibration')
    if not isinstance(calib,dict) or 'status' not in calib:
        raise ValueError('M2 requer status explícito da calibração')
    pending = calib['status']!='APROVADA_COM_JUSTIFICATIVAS'
    if pending and not allow_draft:
        raise ValueError('Matriz M2 ainda não foi relicitada: use allow_draft=True apenas para simulação exploratória')
    root=profile.get('root')
    if not isinstance(root,dict) or [x.get('id') for x in root.get('children',[])]!=['C1','C2','C3']:
        raise ValueError('AHP M2 deve conter exatamente C1, C2 e C3 nesta ordem; C4 pertence às verificações contextuais')
    case=profile.get('case')
    if not isinstance(case,dict) or not all(case.get(key) for key in ('material','classification_point','states')):
        raise ValueError('Material, ponto de classificação e estados obrigatórios')
    states=case['states']
    if set(states)!={'C1','C2','C3a','C3b'}:
        raise ValueError('Estados M2 precisam ser C1, C2, C3a e C3b, sem C4')
    c2=states['C2']
    if c2 not in ('incidental_comprovada','intencionalidade_demonstrada','evidencia_insuficiente'):
        raise ValueError('Estado C2 não reconhecido')
    checks=case.get('complementary_checks')
    if not isinstance(checks,dict) or not all(k in checks for k in ('C4','processing','regulatory_basis')):
        raise ValueError('C4, processamento e referencial regulatório devem constar separadamente')
    c4=checks['C4']
    if not isinstance(c4,dict) or set(c4)!={'technology','logistics'}:
        raise ValueError('C4 deve conter tecnologia e logística')
    for k in ('technology','logistics'):
        item=c4[k]
        if not isinstance(item,dict) or item.get('status') not in C4_STATUS:
            raise ValueError(f'C4.{k} precisa ter status entre {sorted(C4_STATUS)}')
        if not all(isinstance(item.get(field),str) and item[field].strip() for field in ('assessment','source')):
            raise ValueError(f'C4.{k} precisa ter avaliação e fonte')
    processing=checks['processing']
    if not isinstance(processing,dict) or processing.get('type') not in PROCESSING_TYPES:
        raise ValueError('Tipo de processamento inválido/ausente')
    if not all(isinstance(processing.get(field),str) and processing[field].strip() for field in ('assessment','source')):
        raise ValueError('Verificação de processamento precisa ter avaliação e fonte')
    basis=checks['regulatory_basis']
    if not isinstance(basis,dict) or basis.get('status') not in REGULATORY_STATUS or not basis.get('framework'):
        raise ValueError('Informar referencial regulatório e status de avaliação')
    result=evaluate({'version':profile['version'],'classes':profile.get('classes'),
                     'root':deepcopy(root)}, states, consistency_policy=consistency_policy)
    flags=[]
    if pending:
        if calib.get('status')=='PROVISORIA_APROVADA_PARA_SIMULACAO':
            flags.append('PESOS_M2_APROVADOS_PROVISORIAMENTE_SEM_VALIDACAO_EXTERNA')
        else:
            flags.append('PESOS_M2_AINDA_NAO_REELICITADOS')
    if c2=='evidencia_insuficiente': flags.append('C2_EVIDENCIA_INSUFICIENTE_NAO_EQUIVALE_A_GERACAO_INCIDENTAL')
    ev=case.get('state_evidence',{}).get('C2',{})
    if c2=='incidental_comprovada' and (not ev or ev.get('status') in ('hypothesis_not_verified','missing',None)):
        flags.append('C2_INCIDENTAL_DECLARADA_SEM_COMPROVACAO')
    if c2=='intencionalidade_demonstrada' and (not ev or ev.get('status') in ('hypothesis_not_verified','missing',None)):
        flags.append('C2_INTENCIONALIDADE_DECLARADA_SEM_COMPROVACAO')
    if any(c4[k]['status']=='unknown' for k in ('technology','logistics')):
        flags.append('C4_VIABILIDADE_NAO_DETERMINADA')
    if processing['type']=='unknown': flags.append('PROCESSAMENTO_NAO_CARACTERIZADO')
    if basis['status']!='assessed': flags.append('REFERENCIAL_REGULATORIO_SEM_AVALIACAO')
    # Even when all checks are known, an experimental research model is NOT validated.
    candidate=result['result']
    return {
      'model_version':profile['version'],
      'computational_candidate':candidate,
      'final_classification':None,
      'classification_status':'EXPLORATORIO_NAO_VALIDADO',
      'calibration':deepcopy(calib),
      'ahp':{'terminal_weights':result['terminal_weights'],
             'consistency':result['consistency'], 'audit':result['audit']},
      'complementary_checks':deepcopy(checks),
      'flags':flags,
      'separation':{'C4_affects_ahp':False,'processing_affects_ahp':False,
                    'acv_boundary_inferred':False,'upstream_burdens_allocated_automatically':False},
      'case':{'material':case['material'],'classification_point':case['classification_point'],
              'states':deepcopy(states)},
    }


def main(argv=None):
    parser=argparse.ArgumentParser(description='Avaliação experimental M2 (sem conclusão científica)')
    parser.add_argument('config', help='JSON M2 com pesos e verificações complementares')
    parser.add_argument('--allow-draft',action='store_true',help='Permite simular calibração M2 pendente; saída permanece NÃO VALIDADA')
    parser.add_argument('--output',help='Caminho do JSON de resultado')
    args=parser.parse_args(argv)
    profile=json.loads(Path(args.config).read_text(encoding='utf-8'))
    result=evaluate_m2(profile,allow_draft=args.allow_draft)
    payload=json.dumps(result,ensure_ascii=False,indent=2)+'\n'
    if args.output:
        Path(args.output).write_text(payload,encoding='utf-8')
    else:
        print(payload,end='')
    return 0

if __name__=='__main__':
    raise SystemExit(main())
