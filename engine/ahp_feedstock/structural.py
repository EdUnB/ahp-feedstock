"""Diagnósticos estruturais para o AHP, sem modificar o núcleo matemático.

Modelos contrafactuais NÃO são revisões aprovadas dos critérios. Ao excluir um
critério principal, os restantes são renormalizados; ao torná-lo neutro, seus
pesos são mantidos, porém seu vetor local torna-se uniforme. As operações
possuem significados matemáticos distintos e nunca implicam elegibilidade ACV.
"""
from __future__ import annotations
import copy
from typing import Any
import numpy as np

from .core import evaluate, consistency, _normalized_weights


def _descendant_leaves(node: dict) -> list[str]:
    if 'children' not in node:
        return [node['id']]
    return [lid for child in node['children'] for lid in _descendant_leaves(child)]


def _root_weights(root: dict, allow_rounded: bool) -> np.ndarray:
    if 'pairwise' in root and 'weights' not in root:
        return np.asarray(consistency(root['pairwise'])['weights'], dtype=float)
    if 'weights' in root and 'pairwise' not in root:
        return _normalized_weights(root['weights'], len(root['children']), allow_rounded)
    raise ValueError('Raiz precisa usar exclusivamente pairwise ou weights')


def _priority_array(result: dict, labels: list[str]) -> np.ndarray:
    return np.asarray([result['priorities'][lab] for lab in labels], dtype=float)


def _state_subtree_uniform(node: dict, state_ids: dict, n_classes: int) -> None:
    if 'children' in node:
        for child in node['children']:
            _state_subtree_uniform(child, state_ids, n_classes)
    else:
        selected = state_ids[node['id']]
        state = node['states'][selected]
        state.pop('pairwise', None)
        state.pop('priorities', None)
        state['priorities'] = [1/n_classes]*n_classes


def criterion_structure_scenarios(config: dict, states: dict, criterion_id: str,
                                  *, consistency_policy: str = 'block') -> dict:
    """Compara manter, excluir/renormalizar e neutralizar um critério raiz.

    Excluir não equivale a atribuir peso zero na matriz original de Saaty, pois
    uma matriz estritamente positiva nunca produz peso zero. A exclusão é um
    NOVO modelo contrafactual. 'Context-only' reaproveita a classificação sem
    o critério, guardando o estado de infraestrutura para análise externa,
    SEM interpretar automaticamente esse estado como elegibilidade legal.
    """
    if not isinstance(config, dict) or 'root' not in config:
        raise ValueError('Configuração inválida')
    root = config['root']
    children = root.get('children', [])
    if not isinstance(children, list) or len(children) < 2:
        raise ValueError('Exclusão exige pelo menos dois critérios raiz')
    ids = [child['id'] for child in children]
    if ids.count(criterion_id) != 1:
        raise ValueError('Critério principal não encontrado ou duplicado')
    labels = list(config.get('classes', ['resíduo','subproduto','coproduto']))
    baseline = evaluate(config, states, consistency_policy=consistency_policy)
    original_weights = _root_weights(root, config.get('allow_rounded', False))
    idx = ids.index(criterion_id)
    excluded_weight = float(original_weights[idx])
    if excluded_weight >= 1 - 1e-13:
        raise ValueError('Não é possível excluir o único critério com peso positivo')

    # Contribution decomposition uses the actual global weights and active
    # vectors recorded by evaluate(), not rounded manuscript values.
    baseline_audit = {a['node']: a for a in baseline['audit'] if a['kind'] == 'state'}
    contributions = {}
    for child, w in zip(children, original_weights):
        leaf_ids = _descendant_leaves(child)
        arr = sum((baseline['terminal_weights'][lid] *
                   np.asarray(baseline_audit[lid]['local_priorities'], dtype=float)
                   for lid in leaf_ids), np.zeros(len(labels)))
        contributions[child['id']] = {
            'main_weight':float(w),
            'global_priority_contribution':dict(zip(labels,arr.tolist())),
            'delta_coproduct_minus_byproduct':float(arr[labels.index('coproduto')] - arr[labels.index('subproduto')])
              if 'coproduto' in labels and 'subproduto' in labels else None}

    ablated = copy.deepcopy(config)
    del ablated['root']['children'][idx]
    ablated['root'].pop('pairwise', None)
    ablated['root']['weights'] = (np.delete(original_weights, idx) / (1-excluded_weight)).tolist()
    active_leaf_ids = set(_descendant_leaves(ablated['root']))
    active_states = {k:v for k,v in states.items() if k in active_leaf_ids}
    excluded = evaluate(ablated, active_states, consistency_policy=consistency_policy)

    neutral = copy.deepcopy(config)
    _state_subtree_uniform(neutral['root']['children'][idx], states, len(labels))
    neutralized = evaluate(neutral, states, consistency_policy=consistency_policy)

    orig = _priority_array(baseline['result'], labels)
    branch = _priority_array(excluded['result'], labels)
    neutral_p = _priority_array(neutralized['result'], labels)
    # Exact identities: ablation (orig - excluded contribution)/(1-w),
    # neutralization (orig - excluded contribution) + w*[1/k].
    removed = np.asarray([contributions[criterion_id]['global_priority_contribution'][lab]
                          for lab in labels], dtype=float)
    np.testing.assert_allclose(branch, (orig-removed)/(1-excluded_weight), atol=5e-12)
    np.testing.assert_allclose(neutral_p,orig-removed+excluded_weight/len(labels), atol=5e-12)
    return {
        'method':'structural_root_criterion_counterfactuals',
        'criterion':criterion_id,
        'baseline':baseline['result'],
        'original_root_weights':dict(zip(ids,original_weights.tolist())),
        'contributions_by_main_criterion':contributions,
        'excluded_and_renormalized':{
            'result':excluded['result'],
            'new_root_weights':dict(zip([x for x in ids if x!=criterion_id],
                                         ablated['root']['weights'])),
            'excluded_weight':excluded_weight,
            'remaining_states':active_states,
            'note':'Novo modelo hipotético sem o critério; não é edição da matriz original.'},
        'retained_but_uniform':{
            'result':neutralized['result'],
            'note':'Mantém o peso do critério e substitui apenas seus vetores ativos por prioridades uniformes.'},
        'context_only':{
            'result':excluded['result'],
            'excluded_criterion_states':{lid:states[lid] for lid in _descendant_leaves(children[idx])},
            'evidence_gate':'NOT_ASSESSED',
            'note':'Estado registrado como contexto; não calculamos viabilidade, fronteira, alocação ou direito a crédito.'},
        'interpretation':'Diagnóstico de arquitetura, não validação empírica nem mudança aprovada de classificação.'}


def paired_state_grid(config: dict, states: dict, left_id: str, right_id: str,
                      left_alternative: str, right_alternative: str,
                      *, consistency_policy: str = 'block') -> dict:
    """Grade 2×2 para identificar sensibilidade a mudanças conjuntas de estados.

    As quatro combinações não possuem probabilidades. Nem mesmo uma grade
    completamente calculada mede correlação ou independência empírica.
    """
    if left_id == right_id:
        raise ValueError('Use critérios terminais distintos')
    leaf_nodes = {}
    def collect(node):
        if 'children' in node:
            for child in node['children']: collect(child)
        else: leaf_nodes[node['id']] = node
    collect(config['root'])
    if left_id not in leaf_nodes or right_id not in leaf_nodes:
        raise ValueError('Os pares devem ser critérios terminais existentes')
    if left_id not in states or right_id not in states:
        raise ValueError('Estado de referência ausente')
    for name, alternative in [(left_id,left_alternative),(right_id,right_alternative)]:
        if alternative not in leaf_nodes[name]['states'] or alternative == states[name]:
            raise ValueError('Estado alternativo distinto deve existir no catálogo')
    original = copy.deepcopy(states)
    combos=[]
    for l_idx,l_state in enumerate((states[left_id],left_alternative)):
        for r_idx,r_state in enumerate((states[right_id],right_alternative)):
            new_states = dict(states)
            new_states[left_id] = l_state
            new_states[right_id] = r_state
            result = evaluate(config, new_states,consistency_policy=consistency_policy)['result']
            combos.append({'left_alternative':bool(l_idx),'right_alternative':bool(r_idx),
                           'states':{left_id:l_state,right_id:r_state}, 'result':result,
                           'empirical_coherence':'NOT_ASSESSED'})
    assert original == states
    return {'method':'two_by_two_categorical_state_counterfactuals',
            'criteria':[left_id,right_id], 'scenarios':combos,
            'warnings':['Combinações podem ser impossíveis em um caso real.',
                        'Não estima correlação, independência estatística ou probabilidades.',
                        'Qualquer dependência entre critérios requer evidências de vários casos ou revisão de especialistas.']}
