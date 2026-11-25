"""Exploratory scenario robustness diagnostics for the AHP engine.

IMPORTANT: random perturbations are hypothetical scenario generators. The resulting
class frequencies are NOT empirical probabilities, scientific validation, expert
agreement, confidence intervals, or regulatory decisions.
"""
from __future__ import annotations

import copy
from itertools import combinations
import numpy as np

from .core import consistency, evaluate, validate_matrix, _normalized_weights


def _all_reachable_nodes(root):
    stack = [root]
    while stack:
        node = stack.pop()
        yield node
        stack.extend(reversed(node.get('children', [])))


def _descendant_leaf_ids(root):
    return [node['id'] for node in _all_reachable_nodes(root) if 'children' not in node]


def _active_matrices(config, states):
    """Collect mutable matrix lists by node+state, including each hierarchy level."""
    locations = []
    for node in _all_reachable_nodes(config['root']):
        if 'pairwise' in node:
            locations.append((node['id'], None))
        if 'children' not in node:
            state_id = states.get(node['id'])
            if state_id not in node.get('states', {}):
                raise ValueError(f"Missing/invalid state for {node['id']}")
            if 'pairwise' in node['states'][state_id]:
                locations.append((node['id'], state_id))
    return locations


def _modify_matrix(config, node_id, state_id, i, j, value):
    for node in _all_reachable_nodes(config['root']):
        if node['id'] == node_id:
            matrix = node['pairwise'] if state_id is None else node['states'][state_id]['pairwise']
            matrix[i][j] = float(value)
            matrix[j][i] = float(1/value)
            return
    raise ValueError('Unknown matrix node')


def joint_judgment_scenarios(config, states, *, iterations=500,
                             max_relative_change=0.20, seed=20261028,
                             consistency_filter=True):
    """Repeatable, all-active-comparisons-at-once log-uniform hypothetical stress test.

    For comparison a_ij, a'_ij = clip(a_ij * exp(U[-ln(1+h), ln(1+h)]), 1/9, 9).
    The reciprocal entry is set exactly to 1/a'_ij. Each upper-triangle entry is
    drawn independently. For 0<h<=1 this ensures a symmetric multiplicative
    *factor* in log-space, not a uniform distribution in Saaty score.
    Rejected runs (CR>0.10) are counted separately and excluded when the filter
    is active. This conditional sampling changes the assumed sampling law.
    """
    if not isinstance(iterations, int) or isinstance(iterations, bool) or iterations < 1 or iterations > 100_000:
        raise ValueError('iterations must be an integer between 1 and 100000')
    if not np.isfinite(max_relative_change) or not 0 < max_relative_change <= 1:
        raise ValueError('max_relative_change must lie in (0,1]')
    if not isinstance(seed, int) or isinstance(seed, bool) or seed < 0:
        raise ValueError('seed must be a nonnegative integer')
    if not isinstance(consistency_filter, bool):
        raise ValueError('consistency_filter must be a boolean')

    baseline = evaluate(config, states, consistency_policy='warn')
    labels = list(config.get('classes',['resíduo','subproduto','coproduto']))
    locations = _active_matrices(config, states)
    rng = np.random.default_rng(seed)
    log_delta = float(np.log1p(max_relative_change))
    accepted = 0
    rejected_inconsistent = 0
    clipped = 0
    winners = {lab:0 for lab in labels}
    winners['EMPATE'] = 0
    priority_samples=[]
    margin_samples=[]
    rejection_CR=[]
    original_snapshot=copy.deepcopy(config)

    for _ in range(iterations):
        sample=copy.deepcopy(config)
        for node_id, sid in locations:
            node=next(n for n in _all_reachable_nodes(sample['root']) if n['id']==node_id)
            mat = node['pairwise'] if sid is None else node['states'][sid]['pairwise']
            source=validate_matrix(mat)
            for i,j in combinations(range(len(source)),2):
                value=source[i,j] * float(np.exp(rng.uniform(-log_delta, log_delta)))
                bounded=float(np.clip(value,1/9,9))
                clipped+=int(not np.isclose(value,bounded,atol=1e-14,rtol=0))
                mat[i][j],mat[j][i] = bounded,1/bounded
        r=evaluate(sample, states,consistency_policy='warn')
        if r['issues'] and consistency_filter:
            rejected_inconsistent+=1
            rejection_CR.append(len(r['issues']))
            continue
        accepted+=1
        winner=r['result']['winner'] or 'EMPATE'
        winners[winner]+=1
        priority_samples.append([r['result']['priorities'][lab] for lab in labels])
        margin_samples.append(r['result']['margin'])

    assert original_snapshot==config, 'Perturbation must not mutate user configuration'
    values=np.asarray(priority_samples,dtype=float)
    if accepted:
        quantiles = {lab:dict(zip(('min','p05','median','p95','max'),
                                 np.percentile(values[:,i],[0,5,50,95,100]).tolist()))
                     for i,lab in enumerate(labels)}
        margin_quantiles = dict(zip(('min','p05','median','p95','max'),
                                     np.percentile(margin_samples,[0,5,50,95,100]).tolist()))
        frequencies={lab:count/accepted for lab,count in winners.items()}
    else:
        quantiles = None
        margin_quantiles = None
        frequencies = None
    return {
        'method': 'hypothetical_simultaneous_log_uniform_pairwise_perturbation',
        'baseline':baseline['result'],
        'assumptions': {
            'perturbed_matrices': [f'{nid}:{sid}' if sid else nid for nid,sid in locations],
            'interval_multiplier':[1/(1+max_relative_change), 1+max_relative_change],
            'independent_upper_triangle_draws':True,
            'clamped_to_classical_Saaty_bounds':True,
            'consistency_filter':consistency_filter,
            'interpretation':'frequency over hypothetical parameter scenarios, NOT class probability or empirical uncertainty'
        },
        'seed':seed,'iterations_requested':iterations,
        'iterations_used':accepted,
        'iterations_rejected_inconsistent':rejected_inconsistent,
        'comparisons_clipped_to_Saaty_bounds':clipped,
        'counts':winners,'scenario_frequencies':frequencies,
        'priority_range_and_scenario_quantiles':quantiles,
        'classification_margin_scenario_quantiles':margin_quantiles,
        'not_validated':'No expert-derived probability distributions or labels were used.'
    }


def root_weight_decision_boundaries(config, states):
    """Exact analytical pairwise class-tie thresholds under one-root-weight reweighting.

    For a main criterion i assign t in [0,1] and proportionally distribute
    1-t to all other root criteria. Local matrices/states are held fixed.
    Reports pairwise ties with the baseline winning class and distinguishes
    a genuine interior classification reversal from a boundary-only tie at
    t=0 or t=1, where no strict reversal may be reachable.
    """
    if len(config['root'].get('children',[]))<2:
        raise ValueError('At least two top-level criteria required')
    baseline=evaluate(config,states)
    classes=list(config.get('classes',['resíduo','subproduto','coproduto']))
    if baseline['result']['winner'] is None:
        raise ValueError('No unique baseline winner for threshold analysis')
    root=config['root']
    if 'pairwise' in root:
        w=np.asarray(consistency(root['pairwise'])['weights'],dtype=float)
    else:
        w=_normalized_weights(root['weights'],len(root['children']),allow_rounded=config.get('allow_rounded',False))
    original=np.asarray([baseline['result']['priorities'][k] for k in classes],dtype=float)
    winner_idx=classes.index(baseline['result']['winner'])
    results=[]
    for i,child in enumerate(root['children']):
        if w[i]>=1:
            raise ValueError('Criterion weight 1 prevents proportional adjustment')
        relevant_states={n:states[n] for n in _descendant_leaf_ids(child)}
        standalone={'root':copy.deepcopy(child), 'classes':classes,
                    'allow_rounded':config.get('allow_rounded',False)}
        branch=evaluate(standalone,relevant_states)
        self_prior=np.asarray([branch['result']['priorities'][x] for x in classes])
        other=(original-w[i]*self_prior)/(1-w[i])
        crossings=[]
        for j,alternative in enumerate(classes):
            if j==winner_idx:continue
            self_diff=self_prior[winner_idx]-self_prior[j]
            other_diff=other[winner_idx]-other[j]
            denominator=self_diff-other_diff
            if abs(denominator)<1e-13:
                continue
            t=float(-other_diff/denominator)
            if not -1e-12<=t<=1+1e-12:
                continue
            t=float(np.clip(t,0,1))
            at=t*self_prior+(1-t)*other
            at_top=bool(np.max(at)-at[j] < 1e-9 and np.max(at)-at[winner_idx] < 1e-9)
            interior = bool(1e-9 < t < 1-1e-9)
            crossings.append({'against':alternative,'criterion_weight_at_tie':t,
                              'change_in_weight_percentage_points':(t-w[i])*100,
                              'upper_envelope_tie':at_top,
                              'interior_class_reversal_boundary':bool(at_top and interior),
                              'endpoint_only_tie':bool(at_top and not interior),
                              'priorities_at_tie':dict(zip(classes,at.tolist()))})
        crossings.sort(key=lambda x:abs(x['change_in_weight_percentage_points']))
        actual=[x for x in crossings if x['interior_class_reversal_boundary']]
        endpoints=[x for x in crossings if x['endpoint_only_tie']]
        results.append({'criterion':child['id'],'baseline_weight':float(w[i]),
                        'self_branch_priorities':dict(zip(classes,self_prior.tolist())),
                        'pairwise_crossings':crossings,
                        'nearest_interior_reversal_boundary':actual[0] if actual else None,
                        'endpoint_only_ties':endpoints,
                        'no_interior_reversal_boundary':not bool(actual)})
    return {'method':'exact_one_root_weight_vary_others_proportionally',
            'baseline':baseline['result'],'criteria':results,
            'interpretation':'A hypothetical weight-adjustment threshold, NOT a prescribed judgment or scientifically valid alternative classification.'}


def state_assignment_counterfactuals(config, states, *, consistency_policy='block'):
    """Change one selected categorical state at a time to every documented alternative.

    This is a counterfactual logic diagnostic, not a claim that states are
    equally likely, mutually interchangeable, or supported by case evidence.
    State changes can be incoherent with a given scenario; interpretation
    must refer back to the evidence/point of classification.
    """
    baseline=evaluate(config,states,consistency_policy=consistency_policy)['result']
    scenarios=[]
    for node in _all_reachable_nodes(config['root']):
        if 'children' in node:continue
        nid=node['id']; old=states.get(nid)
        for candidate in node['states']:
            if candidate==old:continue
            changed=dict(states);changed[nid]=candidate
            result=evaluate(config,changed,consistency_policy=consistency_policy)['result']
            scenarios.append({'criterion':nid,'original_state':old,
                              'counterfactual_state':candidate,
                              'result':result,'winner_changed':result['winner']!=baseline['winner'],
                              'warning':'hypothetical evidence/state change, not an observed fact'})
    return {'method':'one_at_a_time_counterfactual_state_assignment',
            'baseline':baseline,'counterfactuals':scenarios,
            'n_changed_winner':sum(s['winner_changed'] for s in scenarios),
            'interpretation':'Not class uncertainty estimates: counterfactual states may conflict with evidence.'}
