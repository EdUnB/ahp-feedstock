"""Diagnóstico de sensibilidade C3a/C3b para M2 experimental.

Análises de cenários de julgamentos, NÃO probabilidades de classificação.
O programa nunca torna uma classificação experimental automaticamente válida.
"""
from __future__ import annotations
from copy import deepcopy
from .core import priority_vector, consistency
from .m2 import evaluate_m2

def configure_c3(profile, c3a_over_c3b:float):
    """Cria variante isolada com comparação recíproca C3a/C3b."""
    v=float(c3a_over_c3b)
    if not 1/9<=v<=9:
        raise ValueError('Comparação precisa estar na escala de Saaty [1/9, 9]')
    p=deepcopy(profile)
    root=p['root']
    if [ch['id'] for ch in root['children']]!=['C1','C2','C3']:
        raise ValueError('Esta análise requer C1/C2/C3')
    c3=root['children'][2]
    if [ch['id'] for ch in c3['children']]!=['C3a','C3b']:
        raise ValueError('Esta análise requer C3a/C3b')
    c3['pairwise']=[[1.0,v],[1/v,1.0]]
    return p

def evaluate_c3_sweep(profile, ratios=(1,1.5,2,3,4,5)):
    records=[]
    for ratio in ratios:
        p=configure_c3(profile,float(ratio))
        out=evaluate_m2(p,allow_draft=True)
        rank=out['computational_candidate']
        weights=consistency(p['root']['children'][2]['pairwise'])['weights']
        records.append({'saaty_c3a_over_c3b':float(ratio),
                        'weight_C3a':weights[0], 'weight_C3b':weights[1],
                        'residuo':rank['priorities']['resíduo'],
                        'subproduto':rank['priorities']['subproduto'],
                        'coproduto':rank['priorities']['coproduto'],
                        'coproduto_minus_subproduto':rank['priorities']['coproduto']-rank['priorities']['subproduto'],
                        'candidate_winner':rank['winner'],
                        'final_classification':out['final_classification'],
                        'classification_status':out['classification_status']})
    return records

def c3_bc_crossover(profile):
    """Limite algébrico B=C para estados ativos, pesos raiz fixos.

    Linearidade: D(B,C)=F + w_C3 * [alpha * (C_a-B_a) + (1-alpha) * (C_b-B_b)].
    Um cruzamento B=C não garante que B ou C sejam a classe vencedora.
    """
    out=evaluate_m2(profile,allow_draft=True)
    if out['computational_candidate']['tie']:
        pass
    c3=profile['root']['children'][2]
    states=profile['case']['states']
    a=priority_vector(c3['children'][0]['states'][states['C3a']]['pairwise'])
    b=priority_vector(c3['children'][1]['states'][states['C3b']]['pairwise'])
    old_alpha=consistency(c3['pairwise'])['weights'][0]
    w_c3=consistency(profile['root']['pairwise'])['weights'][2]
    p=out['computational_candidate']['priorities']
    current_diff=p['coproduto']-p['subproduto']
    da=float(a[2]-a[1]); db=float(b[2]-b[1])
    fixed_part=current_diff-w_c3*(old_alpha*da+(1-old_alpha)*db)
    slope=w_c3*(da-db)
    intercept=fixed_part+w_c3*db
    alpha=(-intercept/slope) if abs(slope)>1e-14 else None
    valid=alpha is not None and 0 < alpha < 1
    ratio=(alpha/(1-alpha)) if valid else None
    same_winner=False; cr=None; at_crossing=None
    if valid and 1/9<=ratio<=9:
        p_cross=configure_c3(profile,ratio)
        at_crossing=evaluate_m2(p_cross,allow_draft=True)['computational_candidate']
        same_winner=at_crossing['priorities']['resíduo']>at_crossing['priorities']['subproduto']
        cr=consistency(p_cross['root']['children'][2]['pairwise'])['CR']
    return {'alpha_c3a_equal_BC':float(alpha) if alpha is not None else None,
            'saaty_ratio_equal_BC':float(ratio) if ratio is not None else None,
            'within_unit_weights':bool(valid),
            'within_saaty_range':bool(ratio is not None and 1/9<=ratio<=9),
            'residuo_dominates_at_crossover':bool(same_winner),
            'local_c3a_C_minus_B':da,'local_c3b_C_minus_B':db,
            'other_criteria_BC_offset':float(fixed_part),
            'root_weight_C3':float(w_c3),
            'consistency_ratio_at_crossover':cr,
            'class_priorities_at_crossover':at_crossing['priorities'] if at_crossing else None,
            'interpretation':'Cruzamento de prioridades B/C; não probabilidade, nem validação científica'}
