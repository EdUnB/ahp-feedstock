"""Exploratory layer; original engine and configuration remain unchanged."""
from copy import deepcopy
from functools import lru_cache
import json
import math

from ahp_feedstock.core import aggregate, rank, consistency
from ahp_feedstock.m2 import evaluate_m2
from .stability import analytical_stability, path_weights


def root_weights(profile):
    root = profile['root']
    return consistency(root['pairwise'])['weights'] if 'pairwise' in root else root['weights']


def weighted_profile(profile, weights):
    if len(weights) != 3 or any(not math.isfinite(w) or w < 0 or w > 1 for w in weights):
        raise ValueError('Forneça três pesos finitos entre 0 e 1.')
    if abs(sum(weights) - 1) > 1e-8:
        raise ValueError('Os pesos devem somar 100%.')
    changed = deepcopy(profile)
    changed['root'].pop('pairwise', None)
    changed['root']['weights'] = list(weights)
    changed['root']['justification'] = 'Exploração de sensibilidade; não constitui reelicitação ou validação.'
    return changed


@lru_cache(maxsize=64)
def geometry(serialized):
    profile = json.loads(serialized)
    classes = profile['classes']
    baseline = evaluate_m2(profile, allow_draft=True, consistency_policy='block')
    base_weights = root_weights(profile)
    # Unit-weight evaluations preserve every local matrix and C3 internal split.
    vectors = []
    for i in range(3):
        unit = [float(j == i) for j in range(3)]
        candidate = evaluate_m2(weighted_profile(profile, unit), allow_draft=True,
                                consistency_policy='block')['computational_candidate']
        vectors.append([candidate['priorities'][name] for name in classes])

    def point(weights):
        candidate = rank(aggregate(weights, vectors), classes)
        ordered = sorted(candidate['priorities'].values())
        # Floating point regrouping can reorder tied classes. Preserve original
        # engine ordering at all near-ties, including ties below first place.
        if any(abs(a-b) <= 1e-9 for a,b in zip(ordered, ordered[1:])):
            candidate = evaluate_m2(weighted_profile(profile, weights), allow_draft=True,
                                    consistency_policy='block')['computational_candidate']
        return {'weights': weights, 'candidate': candidate}

    # One-at-a-time paths anchored at baseline; other two retain their ratio.
    sweeps = {}
    for i in range(3):
        points = []
        for step in range(101):
            value = step / 100
            weights = path_weights(base_weights, i, value)
            points.append(point(weights))
        sweeps[f'C{i+1}'] = points
    grid = []
    for a in range(21):
        for b in range(21-a):
            grid.append(point([a/20, b/20, (20-a-b)/20]))
    return {'baseline': baseline, 'baseline_weights': base_weights, 'vectors': vectors,
            'sweeps': sweeps, 'grid': grid,
            'stability': analytical_stability(base_weights, vectors, classes)}


def analyze(profile, weights):
    geom = geometry(json.dumps(profile, sort_keys=True, ensure_ascii=False))
    exploratory = evaluate_m2(weighted_profile(profile, weights), allow_draft=True,
                              consistency_policy='block')
    return {**geom, 'exploratory': exploratory, 'exploratory_weights': weights,
            'method': {'sweep_step_pp': 1, 'simplex_step_pp': 5, 'tie_tolerance': 1e-9,
                       'other_weights': 'proportional_redistribution',
                       'scope': 'Fixed local priorities, states and internal C3 weights; root weights only.',
                       'notice': 'Estabilidade condicional, calculada sob prioridades locais fixas, não equivale a validação científica. Pesos de referência provisórios, não necessariamente definitivos para o artigo.'},
            'scientific_validation': False}
