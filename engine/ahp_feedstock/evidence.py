"""Auditoria separada da matemática AHP: proveniência, hipótese e julgamentos.

Não verifica a verdade de fontes, nem concede validade legal ou ambiental.
A ausência de informação nunca é substituída silenciosamente por um estado.
"""
from __future__ import annotations
from itertools import combinations
import copy
import math

VALID_BASES = {'primary_record', 'secondary_source', 'expert_judgment',
               'assumption', 'not_assessed'}
VALID_UNCERTAINTY = {'low', 'medium', 'high', 'unknown'}
VALID_SOURCE_TYPES = {'unpublished_manuscript', 'technical_supplement',
                      'primary_record', 'peer_reviewed', 'official_statistics',
                      'regulatory', 'industry_report', 'expert_opinion', 'other'}


def _leaf_nodes(root):
    """Percorre a hierarquia sem decidir estados ou estimar prioridades."""
    nodes = {}
    stack = [root]
    while stack:
        node = stack.pop()
        if not isinstance(node, dict) or not isinstance(node.get('id'), str):
            raise ValueError('Nó inválido para auditoria')
        nid = node['id']
        if nid in nodes:
            raise ValueError('IDs de nós duplicados')
        nodes[nid] = node
        stack.extend(node.get('children', []))
    return {nid: node for nid, node in nodes.items() if 'children' not in node}


def _finding(code, level, message, criterion=None):
    out = {'code': code, 'level': level, 'message': message}
    if criterion is not None:
        out['criterion'] = criterion
    return out


def audit_case_evidence(config, case=None):
    """Checa rastreabilidade de cada estado selecionado, sem validar conteúdo.

    case.evidence_records[leaf_id] = {
      'selected_state': '...', 'assessment': '...',
      'evidence_basis': 'primary_record|secondary_source|expert_judgment|assumption|not_assessed',
      'uncertainty': 'low|medium|high|unknown',
      'references': [{'source_id': '...', 'source_type': '...', 'locator': '...'}],
      'alternative_states': ['...']
    }

    Retorna problemas severos de rastreabilidade e advertências científicas.
    Inferências ou hipóteses explícitas nunca são chamadas de validação externa.
    """
    if not isinstance(config, dict) or 'root' not in config:
        raise ValueError('Configuração inválida')
    if case is None:
        case = config.get('case', {})
    if not isinstance(case, dict):
        raise ValueError('Caso deve ser um objeto')
    leaves = _leaf_nodes(config['root'])
    chosen = case.get('states', {})
    records = case.get('evidence_records', {})
    if not isinstance(chosen, dict) or not isinstance(records, dict):
        raise ValueError('Estados e registros devem ser objetos')
    findings = []
    metadata = {}
    for field in ('material', 'classification_point', 'region', 'time_period'):
        val = case.get(field)
        if not isinstance(val, str) or not val.strip():
            findings.append(_finding('CONTEXT_MISSING', 'warning',
                                     f'Contexto {field} não documentado'))
        else:
            metadata[field] = val.strip()
    extras = sorted(set(records) - set(leaves))
    for key in extras:
        findings.append(_finding('UNKNOWN_CRITERION', 'error',
                                 'Registro para critério não existente', key))
    items = []
    for lid, node in leaves.items():
        selected = chosen.get(lid)
        if selected not in node.get('states', {}):
            findings.append(_finding('STATE_INVALID', 'error',
                                     'Estado escolhido ausente ou inválido', lid))
            continue
        rec = records.get(lid)
        if not isinstance(rec, dict):
            findings.append(_finding('EVIDENCE_MISSING', 'error',
                                     'Não existe registro de evidência para o estado', lid))
            items.append({'criterion': lid, 'state': selected, 'traceable': False})
            continue
        errors_before = sum(x['level'] == 'error' for x in findings)
        if rec.get('selected_state') != selected:
            findings.append(_finding('STATE_MISMATCH', 'error',
                                     'Estado no registro difere do selecionado', lid))
        assessment = rec.get('assessment')
        if not isinstance(assessment, str) or len(assessment.strip()) < 15:
            findings.append(_finding('ASSESSMENT_MISSING', 'error',
                                     'Justificativa específica ausente ou insuficiente', lid))
        basis = rec.get('evidence_basis')
        if basis not in VALID_BASES:
            findings.append(_finding('EVIDENCE_BASIS_INVALID', 'error',
                                     'Natureza da evidência não identificada', lid))
        uncertainty = rec.get('uncertainty')
        if uncertainty not in VALID_UNCERTAINTY:
            findings.append(_finding('UNCERTAINTY_MISSING', 'error',
                                     'Incerteza qualitativa não documentada', lid))
        references = rec.get('references', [])
        if not isinstance(references, list):
            findings.append(_finding('REFERENCES_INVALID', 'error',
                                     'Referências devem formar uma lista', lid))
            references = []
        for ref in references:
            if not isinstance(ref, dict) or any(
                not isinstance(ref.get(f), str) or not ref.get(f).strip()
                for f in ('source_id', 'source_type', 'locator')
            ) or (isinstance(ref, dict) and ref.get('source_type') not in VALID_SOURCE_TYPES):
                findings.append(_finding('REFERENCE_INCOMPLETE', 'error',
                                         'Referência sem ID, tipo ou localização verificável', lid))
        if basis in ('primary_record', 'secondary_source') and not references:
            findings.append(_finding('SOURCE_REQUIRED', 'error',
                                     'Declaração baseada em dados/fontes exige referência', lid))
        if basis in ('assumption', 'expert_judgment', 'not_assessed'):
            findings.append(_finding('JUDGMENT_NOT_VERIFIED', 'warning',
                                     'Hipótese ou julgamento não é evidência empírica validada', lid))
        if uncertainty in ('high', 'unknown'):
            findings.append(_finding('UNCERTAINTY_REVIEW', 'warning',
                                     'Estado requer exame de incerteza', lid))
        alt = rec.get('alternative_states', [])
        if not isinstance(alt, list) or len(set(map(str, alt))) != len(alt):
            findings.append(_finding('ALTERNATIVES_INVALID', 'error',
                                     'Alternativas devem formar lista sem duplicatas', lid))
            alt = []
        for a in alt:
            if not isinstance(a, str) or a == selected or a not in node['states']:
                findings.append(_finding('ALTERNATIVE_STATE_INVALID', 'error',
                                         'Alternativa precisa ser outro estado cadastrado', lid))
        if uncertainty in ('high', 'unknown') and not alt:
            findings.append(_finding('ALTERNATIVES_NOT_RECORDED', 'warning',
                                     'Considerar estados alternativos para incerteza elevada', lid))
        items.append({'criterion': lid, 'state': selected,
                      'evidence_basis': basis, 'uncertainty': uncertainty,
                      'source_count': len(references),
                      'alternatives': alt,
                      'traceable': errors_before == sum(x['level'] == 'error' for x in findings)})
    errors = [x for x in findings if x['level'] == 'error']
    warnings = [x for x in findings if x['level'] == 'warning']
    # Um registro completo não prova que suas referências são corretas.
    if errors:
        status = 'INCOMPLETE_EVIDENCE'
    elif any(x['code'] in ('JUDGMENT_NOT_VERIFIED', 'UNCERTAINTY_REVIEW') for x in warnings):
        status = 'TRACEABLE_BUT_PROVISIONAL'
    else:
        status = 'TRACEABLE_NOT_INDEPENDENTLY_VALIDATED'
    return {'status': status, 'case_context': metadata,
            'criteria_expected': len(leaves), 'records_present': len(set(records) & set(leaves)),
            'error_count': len(errors), 'warning_count': len(warnings),
            'findings': findings, 'criteria': items,
            'limitations': 'Auditoria documental; não verifica veracidade de fontes, categorias legais ou validade de pesos.'}


def audit_judgment_ledger(config):
    """Confere documentação par-a-par das matrizes Saaty (opcional, sem alterar cálculos).

    config.judgment_ledger = [{matrix_id: 'root' ou 'C2:estado',
                              i: 0, j: 1, value: 3,
                              justification: '...', references: [...]}]
    """
    leaves = _leaf_nodes(config['root'])
    matrices = {}
    stack = [config['root']]
    while stack:
        node = stack.pop()
        stack.extend(node.get('children', []))
        if 'pairwise' in node:
            matrices[node['id']] = node['pairwise']
        if node['id'] in leaves:
            for sid, state in node.get('states', {}).items():
                if 'pairwise' in state:
                    matrices[node['id'] + ':' + sid] = state['pairwise']
    expected = {(k, i, j) for k, a in matrices.items()
                for i, j in combinations(range(len(a)), 2)}
    supplied = config.get('judgment_ledger', [])
    if not isinstance(supplied, list):
        raise ValueError('judgment_ledger deve ser lista')
    findings = []
    observed = set()
    for item in supplied:
        if not isinstance(item, dict):
            findings.append(_finding('LEDGER_RECORD_INVALID', 'error', 'Registro não é objeto'))
            continue
        mid = item.get('matrix_id')
        i, j = item.get('i'), item.get('j')
        if not isinstance(i, int) or isinstance(i, bool) or not isinstance(j, int) or isinstance(j, bool):
            findings.append(_finding('LEDGER_PAIR_INVALID', 'error', 'Índices inválidos', mid))
            continue
        key = (mid, i, j)
        if key not in expected:
            findings.append(_finding('LEDGER_PAIR_INVALID', 'error', 'Comparação inexistente ou invertida', mid))
            continue
        if key in observed:
            findings.append(_finding('LEDGER_DUPLICATE', 'error', 'Comparação documentada duas vezes', mid))
        observed.add(key)
        try:
            val = float(item.get('value'))
        except (TypeError, ValueError):
            val = float('nan')
        if not math.isfinite(val) or not math.isclose(val, float(matrices[mid][i][j]), rel_tol=1e-9, abs_tol=1e-9):
            findings.append(_finding('LEDGER_VALUE_MISMATCH', 'error', 'Valor difere da matriz', mid))
        text = item.get('justification')
        if (not isinstance(text, str) or len(text.strip()) < 15
                or text.strip().lower().startswith(('[preencher', 'preencher:', 'todo:', 'tbd:', '[todo'))):
            findings.append(_finding('LEDGER_REASON_MISSING', 'error', 'Justificativa ausente ou ainda não preenchida', mid))
    missing = sorted(expected-observed)
    if missing:
        findings.append(_finding('LEDGER_INCOMPLETE', 'warning',
                                 f'{len(missing)} comparações ainda não documentadas'))
    return {'status': ('INVALID_LEDGER' if any(x['level']=='error' for x in findings)
                       else 'INCOMPLETE_LEDGER' if missing else 'DOCUMENTED_NOT_SCIENTIFICALLY_VALIDATED'),
            'expected_comparisons': len(expected), 'documented_comparisons': len(observed & expected),
            'missing_comparisons': [{'matrix_id': k, 'i': i, 'j': j} for k,i,j in missing],
            'findings': findings,
            'limitations': 'Justificativas documentadas não constituem elicitação independente.'}


def state_switch_sensitivity(config, case=None, *, recorded_alternatives_only=False, max_scenarios=200):
    """Troca UM estado de cada vez; cenário contrafactual, não probabilidade."""
    from .core import evaluate
    if case is None:
        case = config.get('case', {})
    if not isinstance(case, dict) or not isinstance(case.get('states'), dict):
        raise ValueError('Caso precisa conter estados')
    if not isinstance(max_scenarios, int) or max_scenarios < 1:
        raise ValueError('max_scenarios deve ser inteiro positivo')
    leaves = _leaf_nodes(config['root'])
    chosen = case['states']
    original = evaluate(config, chosen)
    original_r = original['result']
    records = case.get('evidence_records', {})
    scenarios=[]
    for lid, node in leaves.items():
        if lid not in chosen or chosen[lid] not in node['states']:
            raise ValueError(f'{lid}: estado original inválido')
        possible = (records.get(lid, {}).get('alternative_states', [])
                    if recorded_alternatives_only else list(node['states']))
        if not isinstance(possible, list):
            raise ValueError(f'{lid}: alternativas inválidas')
        for alternate in possible:
            if alternate == chosen[lid]:
                continue
            if alternate not in node['states']:
                raise ValueError(f'{lid}: alternativa inválida {alternate}')
            if len(scenarios) >= max_scenarios:
                raise ValueError('Limite de cenários excedido; especifique alternativas')
            states = dict(chosen)
            states[lid] = alternate
            alternative_r = evaluate(config, states)['result']
            scenarios.append({'criterion': lid, 'from_state': chosen[lid],
                              'to_state': alternate, 'winner': alternative_r['winner'],
                              'margin_pp': 100*alternative_r['margin'],
                              'changed_classification': alternative_r['winner'] != original_r['winner'],
                              'priority_delta_pp': {
                                  c: 100*(alternative_r['priorities'][c] - original_r['priorities'][c])
                                  for c in original_r['priorities']},
                              'priorities': alternative_r['priorities']})
    return {'baseline': original_r, 'scenarios': scenarios,
            'reversals': sum(x['changed_classification'] for x in scenarios),
            'scenario_count': len(scenarios),
            'method': 'one_at_a_time_reference_state_counterfactual',
            'scope': 'recorded_alternatives_only' if recorded_alternatives_only else 'all_catalog_states',
            'limitations': 'Mudanças hipotéticas de estado, não frequências empíricas nem probabilidades.'}


def joint_state_scenarios(config, case=None, *, max_combinations=512):
    """Varre combinações de estados selecionados e alternativos DOCUMENTADOS.

    Todas combinações têm PESO MATEMÁTICO IGUAL somente para enumeração.
    Frequências NÃO são probabilidades, cenários não são necessariamente viáveis
    em conjunto e nenhum resultado valida a escolha dos estados originais.
    """
    from itertools import product
    from .core import evaluate
    if case is None:
        case = config.get('case', {})
    if not isinstance(case, dict) or not isinstance(case.get('states'), dict):
        raise ValueError('Caso precisa conter estados')
    if not isinstance(max_combinations, int) or isinstance(max_combinations, bool) or max_combinations < 1:
        raise ValueError('max_combinations deve ser inteiro positivo')
    records = case.get('evidence_records', {})
    if not isinstance(records, dict):
        raise ValueError('evidence_records deve ser objeto')
    leaves = _leaf_nodes(config['root'])
    choices = []
    for lid, node in leaves.items():
        selected = case['states'].get(lid)
        if selected not in node.get('states', {}):
            raise ValueError(f'{lid}: estado escolhido inválido')
        alts = records.get(lid, {}).get('alternative_states', [])
        if not isinstance(alts, list):
            raise ValueError(f'{lid}: alternativas devem ser lista')
        if any(not isinstance(a, str) or a not in node['states'] or a == selected for a in alts):
            raise ValueError(f'{lid}: alternativas inválidas')
        if len(set(alts)) != len(alts):
            raise ValueError(f'{lid}: alternativas duplicadas')
        choices.append((lid, [selected, *alts]))
    count = math.prod(len(opts) for _,opts in choices)
    if count > max_combinations:
        raise ValueError(f'{count} combinações excedem o limite {max_combinations}')
    scenarios=[]
    classes = config.get('classes',['resíduo','subproduto','coproduto'])
    extrema = {cl:[1., 0.] for cl in classes}
    winner_counts = {cl:0 for cl in classes}
    winner_counts['empate'] = 0
    for state_values in product(*[opts for _,opts in choices]):
        states = dict(zip((lid for lid,_ in choices),state_values))
        result = evaluate(config, states)['result']
        winner = result['winner']
        winner_counts[winner if winner is not None else 'empate'] += 1
        for cl,p in result['priorities'].items():
            extrema[cl][0] = min(extrema[cl][0],p)
            extrema[cl][1] = max(extrema[cl][1],p)
        scenarios.append({'states':states, 'winner':winner,
                          'margin_pp':100*result['margin'],
                          'priorities':result['priorities'],
                          'changed_from_baseline': states!=case['states']})
    baseline = evaluate(config,case['states'])['result']
    return {'baseline':baseline,'scenarios':scenarios,
            'combination_count':len(scenarios), 'winner_counts':winner_counts,
            'priority_ranges':{k:{'min':v[0],'max':v[1]} for k,v in extrema.items()},
            'method':'exhaustive_documented_reference_state_combinations',
            'limitations':('Cenários hipotéticos enumerados SEM distribuição probabilística. '
                           'Contagens não são probabilidades; combinações podem ser inviáveis conjuntamente.')}
