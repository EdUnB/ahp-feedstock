"""AHP multiavaliador: AIJ, AIP, divergência e trilha completa.

Amostras e pesos dos especialistas não são medidas de verdade ou precisão.
AIJ: agregação geométrica das comparações (reciprocidade preservada).
AIP: agregação aritmética das prioridades locais individuais.
Não se imputam julgamentos ausentes; usos parciais exigem autorização explícita.
"""
from __future__ import annotations
import copy
import hashlib
import json
import math
import re
from collections import Counter

import numpy as np

from .core import consistency, evaluate, priority_vector, validate_matrix, rank


def _fingerprint(obj):
    s = json.dumps(obj, ensure_ascii=False, sort_keys=True, allow_nan=False, separators=(',', ':'))
    return hashlib.sha256(s.encode('utf-8')).hexdigest()


def _matrix_locations(config):
    """Aponta locais existentes do AHP, sem modificar a configuração original."""
    if not isinstance(config, dict) or 'root' not in config:
        raise ValueError('Configuração AHP inválida')
    found = {}
    def walk(node):
        nid = node.get('id')
        if not isinstance(nid, str) or not nid:
            raise ValueError('Identificador de nó ausente')
        if 'children' in node:
            if nid in found:
                raise ValueError('Identificadores repetidos')
            found[nid] = node
            for c in node['children']:
                walk(c)
        else:
            for sid, state in node.get('states', {}).items():
                key = f'{nid}:{sid}'
                if key in found:
                    raise ValueError('Identificadores repetidos')
                found[key] = state
    walk(config['root'])
    return found


def _positive_number(x, name):
    if isinstance(x, bool):
        raise ValueError(f'{name} inválido')
    try:
        val = float(x)
    except (ValueError, TypeError) as exc:
        raise ValueError(f'{name} não numérico') from exc
    if not math.isfinite(val) or val <= 0:
        raise ValueError(f'{name} deve ser positivo e finito')
    return val


def _rationale_valid(value):
    if not isinstance(value, str) or len(value.strip()) < 15:
        return False
    s=value.strip().lower()
    return not ('[preencher]' in s or 'a preencher' in s or re.search(r'\b(tbd|todo|pendente|placeholder)\b', s))


def _pair_ids(config, target, node):
    """Identidades estáveis por alternativa; números de linhas não bastam para auditar."""
    if 'children' in node:
        labels = [child['id'] for child in node['children']]
    else:
        labels = config.get('classes')
    size = len(validate_matrix(node['pairwise']))
    if not isinstance(labels, list) or len(labels) != size or any(not isinstance(z, str) or not z.strip() or '|' in z for z in labels) or len(set(labels)) != len(labels):
        raise ValueError(f'{target}: IDs de alternativas inválidos ou incompatíveis com matriz')
    return [f'{labels[i]}|{labels[j]}' for i in range(size) for j in range(i+1, size)]


def pairwise_rationale_template(config, targets=None):
    """Modelo de justificativas POR PAR; não constitui evidência preenchida."""
    locs = _matrix_locations(config)
    select = list(targets) if targets is not None else [k for k, v in locs.items() if 'pairwise' in v]
    if len(set(select)) != len(select) or any(k not in locs or 'pairwise' not in locs[k] for k in select):
        raise ValueError('Alvos de justificativa inválidos')
    return {t:{pair:{'reason':'[PREENCHER]', 'basis':'[PREENCHER]'} for pair in _pair_ids(config, t, locs[t])} for t in select}


def _empirical_flag(panel):
    flag = panel.get('elicitation_is_empirical', False)
    if type(flag) is not bool:
        raise ValueError('elicitation_is_empirical deve ser booleano JSON true/false')
    if flag:
        record = panel.get('elicitation_metadata')
        if not isinstance(record, dict) or not all(_rationale_valid(record.get(k)) for k in ('collection_protocol', 'data_provenance')):
            raise ValueError('Elicitação empírica exige collection_protocol e data_provenance documentados')
        d = record.get('collection_date')
        if not isinstance(d, str):
            raise ValueError('Elicitação empírica exige collection_date YYYY-MM-DD')
        from datetime import date
        try:
            if d != date.fromisoformat(d).isoformat():
                raise ValueError()
        except ValueError as exc:
            raise ValueError('collection_date deve ser YYYY-MM-DD válido') from exc
    return flag


def _check_pair_rationales(config, targets, all_targets, expert):
    """Distingue razão geral da matriz de cada julgamento efetivamente documentado."""
    supplied = expert.get('pair_rationales', {})
    if not isinstance(supplied, dict) or set(supplied)-set(targets):
        raise ValueError(f'{expert["id"]}: pair_rationales possui alvo inválido')
    issues = []
    for t in targets:
        expected = _pair_ids(config, t, all_targets[t])
        rows = supplied.get(t, {})
        if not isinstance(rows, dict) or set(rows)-set(expected):
            raise ValueError(f'{expert["id"]}:{t}: identificador de par inválido')
        for pair in expected:
            entry = rows.get(pair)
            if not isinstance(entry, dict) or not _rationale_valid(entry.get('reason')) or not _rationale_valid(entry.get('basis')):
                issues.append({'expert_id':expert['id'], 'target':t, 'pair':pair, 'issue':'MISSING_REASON_OR_BASIS'})
    return issues


def _panel_preflight(config, panel, *, consistency_policy, require_rationales):
    if consistency_policy not in ('warn', 'block'):
        raise ValueError('consistency_policy precisa ser warn ou block')
    if not isinstance(panel, dict):
        raise ValueError('Painel deve ser um objeto')
    _empirical_flag(panel)
    all_targets = _matrix_locations(config)
    if any('pairwise' not in s for s in all_targets.values()):
        # Nós com pesos diretos são suportados como base, porém não podem ser alvos de elicitação.
        pass
    eligible = {k for k, v in all_targets.items() if 'pairwise' in v}
    targets = panel.get('targets')
    if not isinstance(targets, list) or not targets or any(not isinstance(t, str) or not t for t in targets):
        raise ValueError('targets deve ser uma lista não vazia de IDs')
    if len(targets) != len(set(targets)) or not set(targets) <= eligible:
        raise ValueError('Alvo duplicado, inexistente ou sem matriz de Saaty')
    partial = set(targets) != eligible
    if partial and panel.get('allow_partial') is not True:
        raise ValueError('Painel parcial requer allow_partial=true e relato explícito')
    experts = panel.get('experts')
    if not isinstance(experts, list) or len(experts) < 2:
        raise ValueError('São necessários pelo menos 2 avaliadores')
    names = [e.get('id') if isinstance(e, dict) else None for e in experts]
    if any(not isinstance(n, str) or not n.strip() for n in names) or len(set(names)) != len(names):
        raise ValueError('IDs de avaliadores obrigatórios e distintos')
    raw_w = [_positive_number(e.get('weight', 1), 'peso do avaliador') for e in experts]
    if max(raw_w) - min(raw_w) > 1e-12:
        if not isinstance(panel.get('weighting_rationale'), str) or len(panel['weighting_rationale'].strip()) < 15:
            raise ValueError('Pesos diferenciados exigem justificativa específica')
    weights = np.array(raw_w, dtype=float)
    weights /= weights.sum()
    records = {}
    rationale_errors=[]
    pair_rationale_errors=[]
    inconsistent=[]
    leaves={k.split(':',1)[0]:set() for k in all_targets if ':' in k}
    for k in all_targets:
        if ':' in k:
            leaf, sid=k.split(':',1)
            leaves[leaf].add(sid)
    for exp in experts:
        if 'states' in exp:
            selected=exp['states']
            if not isinstance(selected,dict) or set(selected)!=set(config['case']['states']):
                raise ValueError(f'{exp["id"]}: estados individuais precisam conter exatamente os critérios terminais')
            for leaf,sid in selected.items():
                if leaf not in leaves or sid not in leaves[leaf]:
                    raise ValueError(f'{exp["id"]}: estado individual inválido {leaf}:{sid}')
        decisions=exp.get('judgments')
        if not isinstance(decisions, dict) or set(decisions) != set(targets):
            raise ValueError(f'{exp["id"]}: todas as matrizes dos alvos são obrigatórias, sem imputação')
        checked={}
        rationales=exp.get('rationales',{})
        if not isinstance(rationales,dict):
            raise ValueError(f'{exp["id"]}: rationales precisa ser objeto')
        if any(key not in targets for key in rationales):
            raise ValueError(f'{exp["id"]}: justificativa aponta para alvo não selecionado')
        for target in targets:
            if not _rationale_valid(rationales.get(target)):
                rationale_errors.append({'expert_id':exp['id'],'target':target})
        pair_rationale_errors.extend(_check_pair_rationales(config,targets,all_targets,exp))
        for target in targets:
            a=validate_matrix(decisions[target])
            ref=validate_matrix(all_targets[target]['pairwise'])
            if a.shape != ref.shape:
                raise ValueError(f'{exp["id"]}:{target}: ordem da matriz incompatível')
            c=consistency(a)
            if not c['acceptable']:
                inconsistent.append({'expert_id':exp['id'], 'target':target,'CR':c['CR']})
            checked[target] = {'matrix': a, 'consistency': c}
        records[exp['id']]=checked
    if require_rationales and pair_rationale_errors:
        raise ValueError(f'Justificativas por comparação incompletas: {len(pair_rationale_errors)} pares')
    if inconsistent and consistency_policy == 'block':
        raise ValueError('Matrizes individuais inconsistentes: '+', '.join(f'{r["expert_id"]}:{r["target"]}' for r in inconsistent))
    return all_targets, targets, experts, weights, records, inconsistent, partial, rationale_errors, pair_rationale_errors


def _apply_local(config, targets, values, method):
    new=copy.deepcopy(config)
    locations=_matrix_locations(new)
    for target in targets:
        node=locations[target]
        node.pop('pairwise', None)
        if ':' in target:
            node.pop('priorities', None)
            if method=='aij': node['pairwise']=values[target]
            else: node['priorities']=values[target]
        else:
            node.pop('weights', None)
            if method=='aij': node['pairwise']=values[target]
            else: node['weights']=values[target]
    return new


def _pair_dispersion(target, matrices, ids, weights, threshold):
    n=len(matrices[0]); pairs=[]
    for i in range(n):
        for j in range(i+1,n):
            logs=np.array([np.log(a[i,j]) for a in matrices])
            mean=float(np.dot(weights,logs))
            std=float(np.sqrt(np.dot(weights,(logs-mean)**2)))
            non_neutral=logs[np.abs(logs)>1e-9]
            direction_conflict=bool(np.any(non_neutral>0) and np.any(non_neutral<0))
            pairs.append({'indices':[i,j], 'group_geometric_judgment':float(np.exp(mean)),
                          'geometric_standard_deviation':float(np.exp(std)),
                          'minimum_judgment':float(np.exp(logs.min())),
                          'maximum_judgment':float(np.exp(logs.max())),
                          'direction_conflict':direction_conflict,
                          'high_dispersion':bool(np.exp(std)>=threshold),
                          'judgments':{k:float(np.exp(x)) for k,x in zip(ids,logs)}})
    return pairs


def evaluate_expert_panel(config, panel, *, method='both', consistency_policy='warn', dispersion_threshold=1.5, require_rationales=False):
    """Elicitação por avaliadores: retorna diagnósticos e resultados, sem alterar o original.

    'both': retorna AIJ/AIP, além das classificações individuais.
    'aij': agregação de julgamentos por média geométrica ponderada.
    'aip': agregação dos vetores de prioridades locais (média aritmética ponderada).
    """
    if method not in ('aij','aip','both'):
        raise ValueError('Método deve ser aij, aip ou both')
    threshold=_positive_number(dispersion_threshold,'limiar de dispersão')
    if threshold <= 1:
        raise ValueError('Limiar de dispersão deve ser maior que 1')
    locations, targets, experts, weights, records, inconsistent, partial, rationale_errors, pair_rationale_errors = _panel_preflight(config,panel,consistency_policy=consistency_policy,require_rationales=require_rationales)
    names=[e['id'] for e in experts]
    base_states=config['case']['states']
    individual=[]
    for exp in experts:
        local={t:records[exp['id']][t]['matrix'].tolist() for t in targets}
        c=_apply_local(config,targets,local,'aij')
        selected_states=exp.get('states',base_states)
        result=evaluate(c,selected_states,consistency_policy='warn')
        individual.append({'expert_id':exp['id'], 'normalized_weight':float(weights[names.index(exp['id'])]),
                           'states':dict(selected_states),
                           'classification':result['result'],
                           'validation_status':result['validation_status'],
                           'matrices':{t:{'CR':records[exp['id']][t]['consistency']['CR'],
                                         'acceptable':records[exp['id']][t]['consistency']['acceptable'],
                                         'matrix':local[t]} for t in targets}})
    groups={}; disagreements={}; group_inconsistent=[]
    raw_matrices={}
    for t in targets:
        mats=[records[n][t]['matrix'] for n in names]
        logs=np.stack([np.log(a) for a in mats],axis=0)
        group_log=np.tensordot(weights,logs,axes=(0,0))
        gm=np.exp(group_log)
        np.fill_diagonal(gm,1)
        gm=(gm+1/gm.T)/2  # correção de erro de ponto flutuante, preserva reciprocidade
        validate_matrix(gm)
        raw_matrices[t]=gm
        disagreements[t]=_pair_dispersion(t,mats,names,weights,threshold)
    used_methods=['aij','aip'] if method=='both' else [method]
    for mode in used_methods:
        group_values={}
        group_cr={}
        for t in targets:
            if mode=='aij':
                group_values[t]=raw_matrices[t].tolist()
                group_cr[t]=consistency(group_values[t])
            else:
                ps=np.stack([priority_vector(records[n][t]['matrix']) for n in names])
                p=np.tensordot(weights,ps,axes=(0,0))
                group_values[t]=p.tolist()
                group_cr[t]=None
        if mode=='aij':
            for target,c in group_cr.items():
                if not c['acceptable']:
                    group_inconsistent.append({'target':target,'CR':c['CR']})
        group_config=_apply_local(config,targets,group_values,mode)
        grouped=evaluate(group_config,base_states,consistency_policy='warn')
        groups[mode]={'classification':grouped['result'],
                      'validation_status':grouped['validation_status'],
                      'consistency_of_aggregated_matrices':group_cr if mode=='aij' else 'NOT_APPLICABLE_FOR_AIP',
                      'aggregated_values':group_values,
                      'unelicited_targets_retained_from_baseline':sorted(set(locations)-set(targets))}
    state_differences={}
    for leaf,reference_state in base_states.items():
        ids={r['expert_id']:r['states'][leaf] for r in individual}
        if len(set(ids.values()))>1 or any(s!=reference_state for s in ids.values()):
            state_differences[leaf]={'reference_state':reference_state,'expert_states':ids,
                                     'state_counts':dict(Counter(ids.values()))}
    state_status='UNRESOLVED_DISAGREEMENT' if state_differences else 'BASE_CASE_STATES_UNCONTESTED'
    if state_differences and 'state_resolution' in panel:
        resolution=panel['state_resolution']
        if (not isinstance(resolution, dict) or resolution.get('states') != base_states or
            not _rationale_valid(resolution.get('rationale')) or
            not _rationale_valid(resolution.get('reviewer'))):
            raise ValueError('Resolução de divergência exige estados base, justificativa e responsável')
        state_status='RESOLVED_WITH_DOCUMENTED_DECISION'
    if group_inconsistent and consistency_policy=='block':
        raise ValueError('Matrizes agregadas inconsistentes: '+', '.join(g['target'] for g in group_inconsistent))
    leave_one_out=[]
    if len(experts)>=3:
        for drop_idx,dropped in enumerate(names):
            keep_indices=[i for i in range(len(names)) if i!=drop_idx]
            ww=weights[keep_indices]/weights[keep_indices].sum()
            item={'excluded_expert':dropped,'methods':{}}
            for mode in used_methods:
                subset_values={}
                for t in targets:
                    if mode=='aij':
                        logs=np.stack([np.log(records[names[i]][t]['matrix']) for i in keep_indices])
                        gm=np.exp(np.tensordot(ww,logs,axes=(0,0)))
                        np.fill_diagonal(gm,1)
                        subset_values[t]=gm.tolist()
                    else:
                        ps=np.stack([priority_vector(records[names[i]][t]['matrix']) for i in keep_indices])
                        subset_values[t]=np.tensordot(ww,ps,axes=(0,0)).tolist()
                individual_group=_apply_local(config,targets,subset_values,mode)
                reduced=evaluate(individual_group,base_states,consistency_policy='warn')['result']
                item['methods'][mode]={'classification':reduced,
                                       'winner_changed':bool(reduced['winner']!=groups[mode]['classification']['winner'])}
            leave_one_out.append(item)
    class_labels=config.get('classes', list(individual[0]['classification']['priorities']))
    global_means=np.tensordot(weights, np.array([[r['classification']['priorities'][k] for k in class_labels] for r in individual]), axes=(0,0))
    global_mean_diagnostic=rank(global_means, class_labels)
    tally=Counter(r['classification']['winner'] or 'empate' for r in individual)
    weighted={k:float(sum(weights[i] for i,r in enumerate(individual) if (r['classification']['winner'] or 'empate')==k)) for k in tally}
    high=[{'target':t,'indices':p['indices'], 'geometric_standard_deviation':p['geometric_standard_deviation'], 'direction_conflict':p['direction_conflict']}
          for t,ps in disagreements.items() for p in ps if p['high_dispersion'] or p['direction_conflict']]
    return {'panel_id':panel.get('panel_id','NAO_INFORMADO'),
            'input_fingerprints':{'base_configuration_sha256':_fingerprint(config), 'expert_panel_sha256':_fingerprint(panel)},
            'methods':used_methods,
            'status':'EXPLORATORY_PARTIAL' if partial else 'COMPLETE_PANEL_NUMERIC_ONLY',
            'scientific_validation':'NOT_PERFORMED',
            'elicitation_is_empirical': _empirical_flag(panel),
            'targets':targets,'targets_not_elicited':sorted(set(locations)-set(targets)),
            'expert_weights':dict(zip(names,weights.tolist())),
            'individual_inconsistent_matrices':inconsistent,
            'aggregated_inconsistent_matrices':group_inconsistent,
            'leave_one_expert_out':leave_one_out,
            'state_assignment_disagreement':state_differences,
            'case_state_status':state_status,
            'group_classification_is_conditional':bool(state_differences and state_status=='UNRESOLVED_DISAGREEMENT'),
            'group_state_policy':'BASE_CASE_STATES_FIXED_NOT_A_VOTE',
            'rationale_audit':{'matrix_level_missing_or_placeholder':rationale_errors,
                               'missing_or_placeholder':pair_rationale_errors,
                               'status':'COMPLETE' if not pair_rationale_errors else 'INCOMPLETE',
                               'rule':'PAIR_REASON_AND_BASIS_REQUIRED; MATRIX_OVERVIEW_IS_OPTIONAL'},
            'consistency_gate':'WARN_ONLY' if (inconsistent or group_inconsistent) else 'PASSED',
            'dispersion_threshold_heuristic':threshold,
            'disagreement_flags':high,
            'pairwise_disagreement':disagreements,
            'individual':individual,
            'individual_classification_counts':dict(tally),
            'individual_weighted_classification_frequencies':weighted,
            'global_priority_mean_diagnostic':global_mean_diagnostic,
            'global_priority_mean_is_exportable_group_configuration':False,
            'group_method_labels':{'aij':'AIJ: geometric mean of pairwise judgments', 'aip':'AIP_local: arithmetic mean of local priority vectors', 'global_priority_mean_diagnostic':'Arithmetic mean of individual global outputs; not AIP_local'},
            'group':groups,
            'interpretation_limits':['Discordância não é erro e concordância não é validade.',
                                     'Frequências de votos e agrupamentos não são probabilidades de verdade.',
                                     'CR baixo não comprova qualidade dos julgamentos.',
                                     'AIP_local combina prioridades locais, não os resultados globais individuais.',
                                     'A média global de classificações individuais é um diagnóstico separado; não é AIP_local.',
                                     'Resultados parciais preservam julgamentos não elicitados do modelo-base.',
                                     'Quando especialistas escolhem estados diferentes, o grupo conserva os estados do caso-base e sinaliza a divergência.']}


def build_group_configuration(base_config, analysis, method='aij'):
    """Exporta configuração resultante, vinculada à impressão digital da base.

    Não converte resultado de painel parcial em referência universal.
    """
    if method not in analysis.get('group', {}):
        raise ValueError('Método não calculado na análise')
    if _fingerprint(base_config) != analysis['input_fingerprints']['base_configuration_sha256']:
        raise ValueError('Configuração base não corresponde à auditada')
    out=_apply_local(base_config,analysis['targets'],analysis['group'][method]['aggregated_values'],method)
    out['expert_panel_provenance'] = {
        'panel_id':analysis['panel_id'], 'method':method,
        'base_configuration_sha256':analysis['input_fingerprints']['base_configuration_sha256'],
        'panel_sha256':analysis['input_fingerprints']['expert_panel_sha256'],
        'panel_status':analysis['status'], 'scientific_validation':'NOT_PERFORMED',
        'individual_consistency_warnings':analysis['individual_inconsistent_matrices'],
        'individual_rationales_status':analysis['rationale_audit']['status'],
        'case_state_status':analysis['case_state_status'],
        'group_classification_is_conditional':analysis['group_classification_is_conditional'],
    }
    return out
