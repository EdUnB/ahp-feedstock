"""Motor AHP independente de material, rota, classificação ou resultado esperado.

As fórmulas não presumem que as matrizes ou os critérios de qualquer manuscrito
sejam corretos. Matrizes numéricas e evidências pertencem à configuração.
"""
from __future__ import annotations
import copy
from itertools import combinations
import numpy as np

# Tabela clássica de índices aleatórios (RI) de Saaty, n=1..10.
# Caso a ordem >10 seja necessária, exigiremos política explícita.
RI = {1: 0., 2: 0., 3: 0.58, 4: 0.90, 5: 1.12, 6: 1.24,
      7: 1.32, 8: 1.41, 9: 1.45, 10: 1.49}


def validate_matrix(matrix, tol=1e-8, enforce_scale=True):
    """Verifica reciprocidade, diagonal unitária e intervalo 1/9..9.

    Valores intermediários e reciprocais são permitidos; o motor não impõe
    exclusivamente intensidades inteiras. O relatório deve registrar seu uso.
    """
    try:
        a = np.asarray(matrix, dtype=float)
    except (ValueError, TypeError) as exc:
        raise ValueError('Matriz contém valores não numéricos') from exc
    if a.ndim != 2 or a.shape[0] != a.shape[1] or a.shape[0] < 1:
        raise ValueError('Matriz deve ser quadrada e não vazia')
    if not np.isfinite(a).all() or np.any(a <= 0):
        raise ValueError('Comparações devem ser finitas e positivas')
    if not np.allclose(np.diag(a), 1., atol=tol, rtol=0.):
        raise ValueError('Diagonal deve ser unitária')
    if not np.allclose(a*a.T, 1., atol=tol, rtol=tol):
        raise ValueError('Matriz não recíproca')
    if enforce_scale and (np.any(a < 1./9. - tol) or np.any(a > 9. + tol)):
        raise ValueError('Intensidade fora do intervalo de Saaty [1/9, 9]')
    return a


def pairwise_matrix(n, comparisons):
    """Comparações: {(índice_i, índice_j): valor}; não supõe ausentes = 1."""
    if not isinstance(n, int) or isinstance(n, bool) or n < 1:
        raise ValueError('n deve ser inteiro positivo')
    a = np.ones((n, n), dtype=float)
    seen = set()
    for key, value in comparisons.items():
        if not isinstance(key, tuple) or len(key) != 2:
            raise ValueError('Chave deve ser par de índices')
        i, j = key
        if not isinstance(i, int) or not isinstance(j, int) or i == j or not (0 <= i < n and 0 <= j < n):
            raise ValueError('Índices inválidos')
        unordered = tuple(sorted((i, j)))
        if unordered in seen:
            raise ValueError('Comparação duplicada')
        seen.add(unordered)
        try:
            v = float(value)
        except (ValueError, TypeError) as exc:
            raise ValueError('Intensidade não numérica') from exc
        if not np.isfinite(v) or not 1/9 <= v <= 9:
            raise ValueError('Comparação fora da escala de Saaty [1/9,9]')
        a[i, j], a[j, i] = v, 1/v
    if len(seen) != n*(n-1)//2:
        raise ValueError('Informe todas as comparações; não imputar ausentes')
    return a


def priority_vector(matrix):
    a = validate_matrix(matrix)
    eigvals, eigvecs = np.linalg.eig(a)
    idx = int(np.argmax(eigvals.real))
    if abs(eigvals[idx].imag) > 1e-8:
        raise ValueError('Autovalor principal não real')
    v = eigvecs[:, idx].real
    if v.sum() < 0:
        v = -v
    if np.any(v <= 0) or not np.isfinite(v).all():
        raise ValueError('Autovetor principal inválido')
    return v/v.sum()


def consistency(matrix, threshold=0.10, ri_table=None):
    a = validate_matrix(matrix)
    n = len(a)
    ri_values = RI if ri_table is None else ri_table
    if n not in ri_values:
        raise ValueError('RI indisponível para esta ordem')
    ri_value = float(ri_values[n])
    if not np.isfinite(ri_value) or ri_value < 0 or (n >= 3 and ri_value == 0):
        raise ValueError('RI deve ser finito e não negativo; positivo para n >= 3')
    w = priority_vector(a)
    lam = float(np.mean((a@w)/w))
    ci = max(0., (lam-n)/(n-1)) if n > 1 else 0.
    cr = ci/ri_value if ri_value else 0.
    return {'lambda_max':lam, 'CI':ci, 'CR':cr,
            'acceptable':bool(cr <= threshold), 'weights':w.tolist(),
            'threshold':threshold, 'RI':ri_value}


def inconsistency_triads(matrix, limit=5):
    """Diagnóstico, NÃO correção: tríades discrepantes por |ln(aij ajk/aik)|."""
    a = validate_matrix(matrix)
    triads=[]
    for i,j,k in combinations(range(len(a)),3):
        residual=float(np.log(a[i,j]*a[j,k]/a[i,k]))
        triads.append({'indices':[i,j,k], 'log_residual':residual,
                       'abs_log_residual':abs(residual)})
    return sorted(triads, key=lambda t:t['abs_log_residual'], reverse=True)[:limit]


def _normalized_weights(values, count, allow_rounded=False):
    try:
        w = np.asarray(values, dtype=float)
    except (TypeError, ValueError) as exc:
        raise ValueError('Pesos não numéricos') from exc
    if w.shape != (count,) or not np.isfinite(w).all() or np.any(w < 0):
        raise ValueError('Pesos devem ser finitos, não negativos e completos')
    tolerance = .002 if allow_rounded else 1e-8
    if not np.isclose(w.sum(), 1, atol=tolerance, rtol=0):
        raise ValueError('Pesos devem somar 1; arredondamento acima da tolerância')
    return w/w.sum()


def aggregate(weights, local_vectors):
    try:
        w=np.asarray(weights,dtype=float)
        l=np.asarray(local_vectors,dtype=float)
    except (ValueError,TypeError) as exc:
        raise ValueError('Prioridades não numéricas') from exc
    if w.ndim!=1 or l.ndim!=2 or l.shape[0]!=len(w) or l.shape[1]<2:
        raise ValueError('Dimensões de pesos/vetores incompatíveis')
    if not np.isfinite(w).all() or not np.isfinite(l).all() or np.any(w<0) or np.any(l<0):
        raise ValueError('Pesos/vetores inválidos')
    if not np.isclose(w.sum(),1,atol=1e-8) or not np.allclose(l.sum(axis=1),1,atol=1e-8):
        raise ValueError('Pesos e vetores devem somar 1')
    return w@l


def rank(priorities, names=('resíduo','subproduto','coproduto'), tie_tol=1e-9):
    p=np.asarray(priorities,dtype=float)
    if p.ndim!=1 or p.size<2 or len(p)!=len(names) or not np.isfinite(p).all() or np.any(p<0) or not np.isclose(p.sum(),1,atol=1e-8):
        raise ValueError('Prioridades de classificação inválidas')
    if len(set(names))!=len(names):
        raise ValueError('Nomes de classes duplicados')
    order=np.argsort(-p,kind='stable')
    margin=float(p[order[0]]-p[order[1]])
    return {'priorities':dict(zip(names,p.tolist())),'ranking':[names[i] for i in order],
            'winner':None if margin<=tie_tol else names[order[0]],
            'margin':margin, 'tie':margin<=tie_tol}


def evaluate(config, state_ids, consistency_policy='warn'):
    """Avaliação com auditoria e política de consistência warn|block.

    'warn' calcula e marca resultado provisório caso haja CR>10%; não diz validado.
    'block' recusa qualquer matriz ativa inconsistente.
    """
    if consistency_policy not in ('warn','block'):
        raise ValueError('Política deve ser warn ou block')
    if not isinstance(config,dict) or 'root' not in config:
        raise ValueError('Configuração requer root')
    classes = config.get('classes',['resíduo','subproduto','coproduto'])
    if len(classes)<2 or len(set(classes))!=len(classes):
        raise ValueError('Classes inválidas ou duplicadas')
    # Preflight completo: detectar IDs duplicados antes de selecionar os estados.
    all_ids=[]
    queue=[config['root']]
    while queue:
        item=queue.pop()
        all_ids.append(item.get('id'))
        queue.extend(item.get('children',[]))
    if any(not isinstance(id_,str) or not id_ for id_ in all_ids) or len(set(all_ids))!=len(all_ids):
        raise ValueError('IDs de nós obrigatórios e únicos')
    findings={}; audit=[]; visited=set(); leaves=[]; problems=[]

    def visit(node, scale):
        nid=node.get('id')
        if not isinstance(nid,str) or not nid or nid in visited:
            raise ValueError('IDs de nós obrigatórios e únicos')
        visited.add(nid)
        if 'children' in node:
            children=node['children']
            if not isinstance(children,list) or len(children)<1:
                raise ValueError(f'Filhos inválidos em {nid}')
            if 'pairwise' in node and 'weights' in node:
                raise ValueError(f'{nid}: use pairwise OU weights')
            if 'pairwise' in node:
                cr=consistency(node['pairwise'])
                if len(cr['weights'])!=len(children): raise ValueError(f'{nid}: dimensão inválida')
                findings[nid]=cr
                if not cr['acceptable']:
                    problems.append(f'{nid}: CR {cr["CR"]:.5f} acima do limite')
                w=np.array(cr['weights'])
                audit.append({'node':nid,'kind':'criterion','method':'eigenvector',
                              'matrix':node['pairwise'],'weights':w.tolist(),
                              'CR':cr['CR'],'justification':node.get('justification')})
            elif 'weights' in node:
                w=_normalized_weights(node['weights'],len(children),allow_rounded=config.get('allow_rounded',False))
                audit.append({'node':nid,'kind':'criterion','method':'direct_weights',
                              'weights':w.tolist(),'justification':node.get('justification')})
            else:
                raise ValueError(f'{nid}: informe matriz ou pesos')
            for child, wi in zip(children,w):
                visit(child,scale*float(wi))
        else:
            states=node.get('states')
            if not isinstance(states,dict) or not states:
                raise ValueError(f'{nid}: estados ausentes')
            sid=state_ids.get(nid)
            if sid not in states:
                raise ValueError(f'{nid}: estado obrigatório/inválido')
            state=states[sid]
            if ('pairwise' in state)==('priorities' in state):
                raise ValueError(f'{nid}:{sid}: informe matriz OU prioridades')
            if 'pairwise' in state:
                cr=consistency(state['pairwise'])
                p=np.asarray(cr['weights'])
                findings[nid+':'+sid]=cr
                if not cr['acceptable']:
                    problems.append(f'{nid}:{sid}: CR {cr["CR"]:.5f} acima do limite')
                if len(p)!=len(classes): raise ValueError(f'{nid}: dimensão classes inválida')
                source='eigenvector'
            else:
                p=_normalized_weights(state['priorities'],len(classes),allow_rounded=config.get('allow_rounded',False))
                source='direct_priorities'
            audit.append({'node':nid,'kind':'state','state':sid,'method':source,
                          'matrix':state.get('pairwise'),'local_priorities':p.tolist(),
                          'global_weight':scale,'evidence':state.get('evidence'),
                          'justification':state.get('justification')})
            leaves.append((nid,scale,p,sid))
    visit(config['root'],1.)
    extra=set(state_ids)-{name for name,_,_,_ in leaves}
    if extra: raise ValueError(f'Estados para critérios inexistentes: {sorted(extra)}')
    if abs(sum(item[1] for item in leaves)-1)>1e-8:
        raise ValueError('Pesos globais não somam 1')
    if problems and consistency_policy=='block':
        raise ValueError('Matrizes inconsistentes: '+'; '.join(problems))
    p=aggregate([e[1] for e in leaves],[e[2] for e in leaves])
    return {'result':rank(p,classes),'terminal_weights':{e[0]:e[1] for e in leaves},
            'states':dict(state_ids),'consistency':findings,
            'validation_status':'NEEDS_REVIEW' if problems else 'COMPUTATION_OK_NOT_EMPIRICALLY_VALIDATED',
            'issues':problems,'audit':audit,
            'model_version':config.get('version'),
            'source':config.get('source'),
            'consistency_policy':consistency_policy}


def sensitivity_weights(weights, vectors, fraction=.10, names=('resíduo','subproduto','coproduto')):
    """Sensibilidade univariada dos pesos, sem refazer comparações Saaty."""
    if not np.isfinite(fraction) or not 0 <= fraction <= 1:
        raise ValueError('Fração de sensibilidade deve estar entre 0 e 1')
    w=np.asarray(weights,dtype=float)
    l=np.asarray(vectors,dtype=float)
    baseline=rank(aggregate(w,l), names)
    if len(w)<2: raise ValueError('Sensibilidade exige >=2 critérios')
    scenarios=[]
    for i in range(len(w)):
        for change in (-fraction,fraction):
            nw=w.copy(); new_i=w[i]*(1+change)
            if w[i]>=1: raise ValueError('Critério unitário não perturbável')
            nw*= (1-new_i)/(1-w[i]); nw[i]=new_i
            if np.any(nw<0): raise ValueError('Fração inviabiliza peso')
            scenarios.append({'criterion_index':i,'change':change,
                              'weights':nw.tolist(), 'ranking':rank(aggregate(nw,l),names)})
    return {'baseline':baseline,'scenarios':scenarios,'method':'one_at_a_time_weight_perturbation'}


def sensitivity_main_criteria(config, state_ids, fraction=.10):
    """Perturba um dos pesos do nível raiz, preserva todos os estados e subpesos.
    Propriedade: esta sensibilidade NÃO altera a matriz de Saaty original; peso
    perturbado é um cenário hipotético, com registro explícito de substituição.
    """
    if not np.isfinite(fraction) or not 0 <= fraction <= 1:
        raise ValueError('Fração deve estar entre 0 e 1')
    root=config['root']
    children=root.get('children',[])
    if len(children)<2: raise ValueError('Exige ao menos dois critérios principais')
    if 'pairwise' in root:
        base_weights=consistency(root['pairwise'])['weights']
    elif 'weights' in root:
        base_weights=_normalized_weights(root['weights'],len(children),config.get('allow_rounded',False))
    else: raise ValueError('Raiz sem pesos')
    baseline=evaluate(config,state_ids)
    scenario_values=[]
    for i in range(len(children)):
        for chg in (-fraction,fraction):
            w=np.array(base_weights,dtype=float)
            nw=w.copy(); new_i=w[i]*(1+chg)
            if w[i]>=1 or new_i>1: raise ValueError('Perturbação inviável')
            nw*= (1-new_i)/(1-w[i]); nw[i]=new_i
            c=copy.deepcopy(config)
            c['root'].pop('pairwise',None)
            c['root']['weights']=nw.tolist()
            result=evaluate(c,state_ids)
            scenario_values.append({'criterion':children[i]['id'], 'change':chg,
                                    'main_weights':nw.tolist(),
                                    'result':result['result'],
                                    'validation_status':result['validation_status']})
    return {'baseline':baseline['result'],'scenarios':scenario_values,
            'method':'main_criterion_weights_perturbed_one_at_a_time',
            'fraction':fraction}


def sensitivity_local_judgments(config, state_ids, leaf_id, fraction=.10):
    """Varia cada julgamento ativo de um estado local, um por vez.

    É um ensaio numérico contínuo; NÃO substitui deliberação discreta Saaty.
    Calcula novamente toda a agregação para cada matriz modificada.
    """
    if not np.isfinite(fraction) or not 0 < fraction <= 1:
        raise ValueError('Fração deve estar entre 0 (exclusivo) e 1')
    baseline=evaluate(config,state_ids)
    node_stack=[config['root']]; target=None
    while node_stack:
        node=node_stack.pop()
        if 'children' in node:
            node_stack.extend(node['children'])
        elif node['id']==leaf_id:
            target=node
            break
    if target is None: raise ValueError(f'Critério terminal não encontrado: {leaf_id}')
    sid=state_ids.get(leaf_id)
    if sid not in target['states']: raise ValueError('Estado inválido')
    if 'pairwise' not in target['states'][sid]:
        raise ValueError('Sensibilidade requer matriz local, não vetor precomputado')
    a=validate_matrix(target['states'][sid]['pairwise'])
    scenarios=[]; skipped=[]
    for i,j in combinations(range(len(a)),2):
        for change in (-fraction, fraction):
            val=a[i,j]*(1+change)
            if val<1/9 or val>9:
                skipped.append({'indices':[i,j],'change':change,'reason':'fora da escala'})
                continue
            modified=copy.deepcopy(config)
            stack=[modified['root']]
            while stack:
                n=stack.pop()
                if n.get('id')==leaf_id:
                    m=n['states'][sid]['pairwise']; m[i][j]=float(val); m[j][i]=float(1/val)
                    break
                stack.extend(n.get('children',[]))
            res=evaluate(modified,state_ids,consistency_policy='warn')
            scenarios.append({'indices':[i,j], 'change':change,'new_comparison':float(val),
                              'local_CR':res['consistency'][leaf_id+':'+sid]['CR'],
                              'result':res['result'], 'validation_status':res['validation_status']})
    return {'baseline':baseline['result'],'scenarios':scenarios,'skipped':skipped,
            'method':'one_at_a_time_local_pairwise_perturbation', 'criterion':leaf_id,
            'state':sid,'fraction':fraction}


def inspect_config(config):
    """Audita TODAS as matrizes (inclusive estados inativos).

    Separada de evaluate(): um estado não selecionado não afeta a classificação
    corrente, mas ainda deve ser revisado antes de disponibilizar a configuração.
    """
    if not isinstance(config,dict) or 'root' not in config:
        raise ValueError('Configuração requer root')
    classes=config.get('classes',['resíduo','subproduto','coproduto'])
    if len(classes)<2 or len(set(classes))!=len(classes):
        raise ValueError('Classes inválidas')
    stack=[config['root']]; seen=set(); reports={}; warnings=[]; metadata=[]
    while stack:
        node=stack.pop()
        nid=node.get('id')
        if not isinstance(nid,str) or not nid or nid in seen:
            raise ValueError('IDs de nós obrigatórios e únicos')
        seen.add(nid)
        if 'children' in node:
            children=node['children']
            if not isinstance(children,list) or not children:
                raise ValueError(f'{nid}: filhos ausentes')
            if ('pairwise' in node)==('weights' in node):
                raise ValueError(f'{nid}: informe matriz OU pesos')
            if 'pairwise' in node:
                r=consistency(node['pairwise'])
                if len(r['weights'])!=len(children): raise ValueError(f'{nid}: dimensão inválida')
                reports[nid]=r
                if not r['acceptable']: warnings.append(f'{nid}: CR {r["CR"]:.5f} acima de 0,10')
            else:
                _normalized_weights(node['weights'],len(children),config.get('allow_rounded',False))
            stack.extend(children)
        else:
            states=node.get('states')
            if not isinstance(states,dict) or not states:
                raise ValueError(f'{nid}: estados ausentes')
            for sid,state in states.items():
                if ('pairwise' in state)==('priorities' in state):
                    raise ValueError(f'{nid}:{sid}: informe matriz OU prioridades')
                label=nid+':'+sid
                if 'pairwise' in state:
                    r=consistency(state['pairwise'])
                    if len(r['weights'])!=len(classes):
                        raise ValueError(f'{label}: dimensão classes inválida')
                    reports[label]=r
                    if not r['acceptable']: warnings.append(f'{label}: CR {r["CR"]:.5f} acima de 0,10')
                else:
                    _normalized_weights(state['priorities'],len(classes),config.get('allow_rounded',False))
                if not state.get('evidence') and not state.get('justification'):
                    metadata.append(label)
    return {'matrix_count':len(reports),'checked_nodes':len(seen),
            'consistency_warnings':warnings,'missing_evidence_or_justification':metadata,
            'configuration_status':'NEEDS_REVIEW' if warnings else 'MATHEMATICALLY_COHERENT_NOT_EMPIRICALLY_VALIDATED',
            'matrices':reports}
