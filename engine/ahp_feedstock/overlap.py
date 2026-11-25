"""Diagnósticos de sobreposição de evidência e testes aditivos de AHP.

Não estimam independência estatística ou redundância causal a partir de um só caso.
Qualquer correlação entre critérios requer observações independentes / especialistas.
"""
from __future__ import annotations
from itertools import combinations
from typing import Any
import numpy as np
from .core import evaluate, rank
from .evidence import _leaf_nodes

# C2 tem significado DIFERENTE nos modelos M0 e M1. As comparações são
# explicitamente documentais, sem alegar equivalência entre conceitos M0/M1.
DEFAULT_PAIRS = (('C1', 'C3a'), ('C2', 'C3b'), ('C3a', 'C4a'))


def _reference_keys(record: dict) -> tuple[set[str], set[tuple[str,str]], set[str]]:
    """Retorna fontes, passagens específicas, e fatos com IDs explicitamente dados.

    source_id repetido não é prova de reutilização do MESMO fato.
    """
    sources: set[str] = set()
    passages: set[tuple[str,str]] = set()
    facts: set[str] = set()
    for fid in record.get('fact_ids', []) or []:
        if isinstance(fid, str) and fid.strip():
            facts.add(fid.strip())
    for ref in record.get('references', []) or []:
        if not isinstance(ref, dict):
            continue
        source = ref.get('source_id')
        locator = ref.get('locator')
        if isinstance(source, str) and source.strip():
            sources.add(source.strip())
            if isinstance(locator, str) and locator.strip():
                passages.add((source.strip(), locator.strip()))
        fact = ref.get('fact_id')
        if isinstance(fact, str) and fact.strip():
            facts.add(fact.strip())
    return sources, passages, facts


def audit_evidence_overlap(config: dict, case: dict | None = None,
                           pairs: tuple[tuple[str,str], ...] = DEFAULT_PAIRS) -> dict:
    """Auditoria da proveniência; não interpreta texto livre por ML/heurística.

    fact_ids (opcional) deve identificar uma observação concreta, e NÃO o
    conceito do critério. A ausência de fato ID implica 'não determinado'.
    """
    if not isinstance(config, dict) or not isinstance(config.get('root'), dict):
        raise ValueError('Configuração inválida')
    if case is None:
        case = config.get('case', {})
    if not isinstance(case, dict) or not isinstance(case.get('evidence_records'), dict):
        raise ValueError('Caso com registros de evidência é obrigatório')
    leaves = _leaf_nodes(config['root'])
    records = case['evidence_records']
    if not isinstance(pairs, (list,tuple)):
        raise ValueError('Pares devem ser uma sequência')
    outcomes=[]
    seen=set()
    for pair in pairs:
        if not isinstance(pair, (list,tuple)) or len(pair)!=2:
            raise ValueError('Cada par deve conter dois critérios')
        a,b=pair
        if not isinstance(a,str) or not isinstance(b,str) or a==b or a not in leaves or b not in leaves:
            raise ValueError('Pares precisam usar critérios terminais distintos e existentes')
        key=tuple(sorted((a,b)))
        if key in seen:
            raise ValueError('Pares duplicados')
        seen.add(key)
        ar=records.get(a);br=records.get(b)
        if not isinstance(ar,dict) or not isinstance(br,dict):
            classification='incomplete_evidence'
            shared_sources=[];shared_passages=[];shared_facts=[]
        else:
            a_sources,a_passages,a_facts=_reference_keys(ar)
            b_sources,b_passages,b_facts=_reference_keys(br)
            shared_sources=sorted(a_sources&b_sources)
            shared_passages=[{'source_id':s,'locator':l} for s,l in sorted(a_passages&b_passages)]
            shared_facts=sorted(a_facts&b_facts)
            if shared_facts:
                classification='shared_observation_id'
            elif shared_passages:
                classification='shared_source_passage'
            elif shared_sources:
                classification='shared_source_only'
            elif not a_sources or not b_sources:
                classification='insufficient_references'
            else:
                classification='different_sources_reported'
        outcomes.append({'criteria':[a,b],'evidence_overlap_level':classification,
                         'shared_sources':shared_sources,'shared_passages':shared_passages,
                         'shared_fact_ids':shared_facts,
                         'duplicate_fact_proven':False,
                         'requires_human_review':classification in ('shared_observation_id','shared_source_passage',
                                                           'shared_source_only','incomplete_evidence','insufficient_references')})
    return {'method':'documentary_evidence_overlap', 'pairs':outcomes,
            'fact_id_protocol':'ID representa a MESMA observação material, não a categoria nem a mesma publicação',
            'limits':['Mesma fonte não equivale a mesmo fato.',
                      'Mesmo fact_id declarado aciona auditoria; não valida que a observação foi interpretada corretamente.',
                      'Não estima correlação, redundância causal ou independência estatística.']}


def additive_pair_sensitivity(config: dict, states: dict, left_id: str, right_id: str,
                              left_alternative: str, right_alternative: str,
                              *, consistency_policy: str = 'block') -> dict:
    """Decompõe efeitos de duas trocas de estados com demais estados e pesos fixos.

    Para AHP absoluto agregativo, interação de prioridades é ZERO por construção.
    Isso NÃO mostra independência empírica; categoria vencedora é não linear.
    """
    leaves=_leaf_nodes(config['root'])
    if left_id == right_id or left_id not in leaves or right_id not in leaves:
        raise ValueError('Dois critérios terminais distintos são obrigatórios')
    if left_id not in states or right_id not in states:
        raise ValueError('Estado de referência ausente')
    for crit,alt in ((left_id,left_alternative),(right_id,right_alternative)):
        if alt not in leaves[crit].get('states',{}) or alt == states[crit]:
            raise ValueError('Alternativa deve ser um estado diferente e cadastrado')
    labels=list(config.get('classes', ['resíduo','subproduto','coproduto']))
    scenarios={}
    for tag,changes in (('base',{}),('left_only',{left_id:left_alternative}),
                        ('right_only',{right_id:right_alternative}),
                        ('both',{left_id:left_alternative,right_id:right_alternative})):
        chosen={**states,**changes}
        scenarios[tag]=evaluate(config,chosen,consistency_policy=consistency_policy)['result']
    def vec(name):return np.asarray([scenarios[name]['priorities'][lab] for lab in labels],dtype=float)
    base=vec('base');dl=vec('left_only')-base;dr=vec('right_only')-base
    interaction=vec('both')-base-dl-dr
    if np.max(abs(interaction))>1e-10:
        raise AssertionError('Agregação não aditiva inesperada')
    effects={k:dict(zip(labels,v.tolist())) for k,v in
             [('left_only',dl),('right_only',dr),('interaction',interaction)]}
    return {'method':'paired_state_additive_decomposition', 'criteria':[left_id,right_id],
            'scenarios':scenarios,'priority_effects':effects,
            'max_abs_interaction':float(np.max(abs(interaction))),
            'structural_additivity':'CONFIRMED_BY_CONSTRUCTION',
            'empirical_independence':'NOT_ASSESSED',
            'interpretation':'Interação nula nas prioridades decorre da soma ponderada; não demonstra independência dos critérios nem ausência de dupla contagem.'}


def terminal_ablation_diagnostic(config:dict, states:dict, terminal_id:str,
                                 *,consistency_policy:str='block') -> dict:
    """Retira contribuição terminal e renormaliza os DEMAIS pesos globais.

    Contrafactual algébrico, NÃO é uma nova matriz AHP elicitada para os critérios
    remanescentes. Especialmente cuidado ao excluir apenas parte de C3/C4.
    """
    leaves=_leaf_nodes(config['root'])
    if terminal_id not in leaves:
        raise ValueError('Critério terminal não encontrado')
    result=evaluate(config,states,consistency_policy=consistency_policy)
    weights=result['terminal_weights'];w=float(weights[terminal_id]);
    if w >=1 - 1e-13:
        raise ValueError('Não há peso residual suficiente')
    item=next(a for a in result['audit'] if a['kind']=='state' and a['node']==terminal_id)
    labels=list(config.get('classes', ['resíduo','subproduto','coproduto']))
    baseline=np.asarray([result['result']['priorities'][k] for k in labels])
    local=np.asarray(item['local_priorities'],dtype=float)
    new=(baseline-w*local)/(1-w)
    # Restaura valores em 0 apenas quando as diferenças são ruído numérico.
    if (new < -1e-10).any():
        raise AssertionError('Ablation gerou prioridade negativa')
    new=np.maximum(new,0);new/=new.sum()
    newrank=rank(new, labels)
    return {'method':'one_terminal_leaf_removal_global_weight_renormalization',
            'terminal_id':terminal_id, 'removed_weight':w,
            'baseline':result['result'],'without_terminal':newrank,
            'margin_change':newrank['margin']-result['result']['margin'],
            'winner_changed':newrank['winner']!=result['result']['winner'],
            'warning':'Diagnóstico algébrico, NÃO re-elicitação de Saaty ou evidência de redundância.'}
