"""Auditoria estruturada de observações e vínculos com os critérios de AHP.

Somente verifica integridade, rastreabilidade e coerência formal da documentação.
NÃO certifica a verdade dos fatos, validade jurídica ou correlação/independência.
O motor matemático nunca é alterado por esta camada.
"""
from __future__ import annotations

from collections import defaultdict
from datetime import date
from .evidence import _leaf_nodes, VALID_SOURCE_TYPES

OBSERVATION_KINDS = {'reported', 'inference', 'assumption', 'expert_judgment'}
LINK_ROLES = {'supports', 'contradicts', 'context'}
SOURCE_VISIBILITY = {'internal', 'public', 'restricted'}
PLACEHOLDERS = ('[preencher', '[todo', 'todo:', 'tbd:', 'a definir', '<preencher')


def _text_ok(value, min_length=1):
    return (isinstance(value, str) and len(value.strip()) >= min_length and
            not value.strip().lower().startswith(PLACEHOLDERS))


def _date_ok(value):
    if not isinstance(value, str):
        return False
    try:
        return date.fromisoformat(value).isoformat() == value
    except ValueError:
        return False


def _finding(code, level, message, *, entry=None, criterion=None):
    return {'code': code, 'level': level, 'message': message,
            **({'entry': entry} if entry else {}),
            **({'criterion': criterion} if criterion else {})}


def audit_observation_registry(config, case=None):
    """Audita case.evidence_registry: sources, observations e links.

    Esquema:
    sources: [{id, title, source_type, visibility, date?}]
    observations: [{id, statement, kind, applicability: {material, classification_point,
                    region, time_period}, sources:[{id, locator}], limitations}]
    links: [{observation_id, criterion_id, state_id, role, rationale}]

    Cobertura exige ao menos um 'supports' para o estado selecionado de cada folha,
    inclusive quando o suporte é explicitamente classificado como ASSUMPTION.
    Portanto, a cobertura documental NÃO estabelece suficiência científica.
    """
    if not isinstance(config, dict) or not isinstance(config.get('root'), dict):
        raise ValueError('Configuração inválida')
    if case is None:
        case = config.get('case', {})
    if not isinstance(case, dict):
        raise ValueError('Caso precisa ser um objeto')
    leaves = _leaf_nodes(config['root'])
    registry = case.get('evidence_registry')
    if registry is None:
        return {'status': 'NOT_PROVIDED', 'error_count': 0, 'warning_count': 0,
                'findings': [], 'coverage': {}, 'shared_observations': [],
                'limitations': 'Cadastro não fornecido; não significa ausência de risco de sobreposição.'}
    if not isinstance(registry, dict):
        return {'status': 'INVALID_REGISTRY', 'error_count': 1, 'warning_count': 0,
                'findings': [_finding('REGISTRY_INVALID', 'error', 'evidence_registry deve ser objeto')],
                'coverage': {}, 'shared_observations': [],
                'limitations': 'Auditoria exclusivamente documental.'}
    findings = []
    sources = registry.get('sources')
    observations = registry.get('observations')
    links = registry.get('links')
    for label, collection in [('sources', sources), ('observations', observations), ('links', links)]:
        if not isinstance(collection, list):
            findings.append(_finding('REGISTRY_COLLECTION_INVALID', 'error',
                                     f'{label} deve ser uma lista'))
    if any(not isinstance(x, list) for x in (sources, observations, links)):
        return _package(findings, {}, [], {}, {}, empty=False)
    sources_by_id = {}
    obs_by_id = {}
    assessed_at = case.get('assessment_date')
    if assessed_at is not None and not _date_ok(assessed_at):
        findings.append(_finding('ASSESSMENT_DATE_INVALID', 'error',
                                 'assessment_date deve estar em YYYY-MM-DD'))
    temporally_invalid = set()
    selected = case.get('states', {})
    if not isinstance(selected, dict):
        findings.append(_finding('SELECTED_STATES_INVALID', 'error', 'states deve ser objeto'))
        selected = {}

    # Fontes bibliográficas ou registros primários -- a mesma fonte pode suportar vários fatos.
    for idx, source in enumerate(sources):
        pos = f'sources[{idx}]'
        if not isinstance(source, dict):
            findings.append(_finding('SOURCE_INVALID', 'error', 'Fonte não é objeto', entry=pos)); continue
        sid = source.get('id')
        if not _text_ok(sid):
            findings.append(_finding('SOURCE_ID_MISSING', 'error', 'ID da fonte ausente', entry=pos)); continue
        if sid in sources_by_id:
            findings.append(_finding('SOURCE_DUPLICATE', 'error', 'ID de fonte duplicado', entry=sid)); continue
        sources_by_id[sid] = source
        if not _text_ok(source.get('title'), 5):
            findings.append(_finding('SOURCE_TITLE_INVALID', 'error', 'Título insuficiente', entry=sid))
        if source.get('source_type') not in VALID_SOURCE_TYPES:
            findings.append(_finding('SOURCE_TYPE_INVALID', 'error', 'Tipo de fonte inválido', entry=sid))
        if source.get('visibility') not in SOURCE_VISIBILITY:
            findings.append(_finding('SOURCE_VISIBILITY_INVALID', 'error', 'Visibilidade precisa ser explícita', entry=sid))
        if 'date' in source and not _date_ok(source['date']):
            findings.append(_finding('SOURCE_DATE_INVALID', 'error', 'Data ISO YYYY-MM-DD inválida', entry=sid))

    # Cada fato é separado da fonte e tem contexto de aplicabilidade.
    used_sources = set()
    for idx, obs in enumerate(observations):
        pos = f'observations[{idx}]'
        if not isinstance(obs, dict):
            findings.append(_finding('OBSERVATION_INVALID', 'error', 'Observação não é objeto', entry=pos)); continue
        oid = obs.get('id')
        if not _text_ok(oid):
            findings.append(_finding('OBSERVATION_ID_MISSING', 'error', 'ID de observação ausente', entry=pos)); continue
        if oid in obs_by_id:
            findings.append(_finding('OBSERVATION_DUPLICATE', 'error', 'ID de observação duplicado', entry=oid)); continue
        obs_by_id[oid] = obs
        if not _text_ok(obs.get('statement'), 20):
            findings.append(_finding('OBSERVATION_STATEMENT_INVALID', 'error', 'Descrição factual insuficiente ou não preenchida', entry=oid))
        kind = obs.get('kind')
        if kind not in OBSERVATION_KINDS:
            findings.append(_finding('OBSERVATION_KIND_INVALID', 'error', 'Natureza da afirmação desconhecida', entry=oid))
        if not _text_ok(obs.get('limitations'), 12):
            findings.append(_finding('OBSERVATION_LIMITATIONS_MISSING', 'error', 'Limitações precisam ser documentadas', entry=oid))
        applies = obs.get('applicability')
        if not isinstance(applies, dict):
            findings.append(_finding('APPLICABILITY_MISSING', 'error', 'Aplicabilidade precisa ser objeto', entry=oid))
            applies = {}
        for key in ('material', 'classification_point', 'region', 'time_period'):
            if not _text_ok(applies.get(key)):
                findings.append(_finding('APPLICABILITY_INCOMPLETE', 'error', f'Aplicabilidade sem {key}', entry=oid))
            elif _text_ok(case.get(key)) and applies.get(key) != case.get(key):
                findings.append(_finding('APPLICABILITY_DIFFERS', 'warning',
                                         f'{key} do fato difere do caso; confirmar transferência de evidência',entry=oid))
        # Validade temporal só é avaliada quando as datas são explicitamente fornecidas.
        start, end = obs.get('valid_from'), obs.get('valid_until')
        for field, raw in (('valid_from', start), ('valid_until', end)):
            if raw is not None and not _date_ok(raw):
                findings.append(_finding('OBSERVATION_DATE_INVALID', 'error',
                                         f'{field} deve estar em YYYY-MM-DD',entry=oid))
        if start is not None and end is not None and _date_ok(start) and _date_ok(end) and start > end:
            findings.append(_finding('OBSERVATION_PERIOD_INVALID', 'error',
                                     'Início de vigência depois do término',entry=oid))
        if (start or end) and assessed_at is None:
            findings.append(_finding('ASSESSMENT_DATE_NOT_SET', 'warning',
                                     'Caso não informa data de avaliação para testar vigência',entry=oid))
        if _date_ok(assessed_at) and ((_date_ok(start) and assessed_at < start) or
                                     (_date_ok(end) and assessed_at > end)):
            temporally_invalid.add(oid)
            findings.append(_finding('OBSERVATION_OUTSIDE_PERIOD', 'warning',
                                     'Observação fora da vigência informada no caso',entry=oid))
        refs = obs.get('sources', [])
        if not isinstance(refs, list):
            findings.append(_finding('OBSERVATION_SOURCES_INVALID', 'error', 'sources deve ser lista',entry=oid))
            refs = []
        if kind == 'reported' and not refs:
            findings.append(_finding('REPORTED_OBSERVATION_WITHOUT_SOURCE', 'error',
                                     'Afirmação reportada exige fonte e localizador', entry=oid))
        if kind in ('inference', 'assumption', 'expert_judgment'):
            findings.append(_finding('NON_EMPIRICAL_OBSERVATION', 'warning',
                                     'Inferência, hipótese ou julgamento: não tratar como fato independente',entry=oid))
        seen_refs = set()
        for ref in refs:
            if not isinstance(ref, dict) or not _text_ok(ref.get('id')) or not _text_ok(ref.get('locator')):
                findings.append(_finding('OBSERVATION_SOURCE_LINK_INVALID', 'error',
                                         'Fonte de observação exige ID e localizador',entry=oid)); continue
            sid = ref['id']; key = (sid, ref['locator'])
            if key in seen_refs:
                findings.append(_finding('OBSERVATION_SOURCE_DUPLICATE', 'error',
                                         'Mesmo localizador repetido para a observação',entry=oid))
            seen_refs.add(key)
            if sid not in sources_by_id:
                findings.append(_finding('SOURCE_NOT_FOUND', 'error',
                                         'Observação cita fonte não cadastrada',entry=oid))
            else:
                used_sources.add(sid)

    # Vínculo justificável entre uma observação e a avaliação de um estado específico.
    used_obs = set()
    support = defaultdict(set)
    obs_criteria = defaultdict(set)
    same_target_roles = defaultdict(set)
    seen_links = set()
    for idx, link in enumerate(links):
        pos = f'links[{idx}]'
        if not isinstance(link, dict):
            findings.append(_finding('LINK_INVALID', 'error', 'Vínculo não é objeto',entry=pos)); continue
        oid = link.get('observation_id'); cid = link.get('criterion_id')
        sid = link.get('state_id'); role = link.get('role')
        if not all(_text_ok(x) for x in (oid, cid, sid)):
            findings.append(_finding('LINK_FIELDS_MISSING','error','Vínculo exige observação, critério e estado',entry=pos)); continue
        if oid not in obs_by_id:
            findings.append(_finding('LINK_OBSERVATION_NOT_FOUND','error','Observação não cadastrada',entry=pos))
        else:
            used_obs.add(oid)
        if cid not in leaves:
            findings.append(_finding('LINK_CRITERION_NOT_FOUND','error','Critério terminal não existe',entry=pos))
        elif sid not in leaves[cid].get('states', {}):
            findings.append(_finding('LINK_STATE_NOT_FOUND','error','Estado não cadastrado no critério',entry=pos))
        if role not in LINK_ROLES:
            findings.append(_finding('LINK_ROLE_INVALID','error','Papel do vínculo inválido',entry=pos))
        if not _text_ok(link.get('rationale'), 20):
            findings.append(_finding('LINK_RATIONALE_MISSING','error','Justificativa causal/interpretativa insuficiente',entry=pos))
        key = (oid, cid, sid, role)
        if key in seen_links:
            findings.append(_finding('LINK_DUPLICATE','error','Vínculo duplicado',entry=pos))
        seen_links.add(key)
        if oid in obs_by_id and cid in leaves and sid in leaves[cid].get('states', {}) and role in LINK_ROLES:
            obs_criteria[oid].add(cid)
            same_target_roles[(oid,cid,sid)].add(role)
            if role == 'supports' and selected.get(cid) == sid:
                support[cid].add(oid)
                if oid in temporally_invalid:
                    findings.append(_finding('OUTDATED_SUPPORT', 'error',
                                             'Estado selecionado apoiado em observação fora de vigência',
                                             entry=oid,criterion=cid))
            if role == 'supports' and selected.get(cid) != sid:
                findings.append(_finding('SUPPORTS_NON_SELECTED_STATE','warning',
                                         'Observação favorece alternativa diferente do estado escolhido',entry=oid,criterion=cid))
    for (oid,cid,sid),roles in same_target_roles.items():
        if 'supports' in roles and 'contradicts' in roles:
            findings.append(_finding('CONTRADICTORY_ROLES','error',
                                     'Mesmo fato apoia e contradiz exatamente o mesmo estado',entry=oid,criterion=cid))
    coverage={}
    for cid in leaves:
        linked = sorted(support[cid])
        if not linked:
            findings.append(_finding('STATE_UNSUPPORTED','error',
                                     'Estado escolhido não possui observação de apoio vinculada', criterion=cid))
        provisional=sorted(oid for oid in linked if obs_by_id[oid].get('kind') != 'reported')
        empirical=sorted(oid for oid in linked if obs_by_id[oid].get('kind') == 'reported')
        if linked and not empirical:
            findings.append(_finding('ONLY_PROVISIONAL_SUPPORT','warning',
                                     'Estado sustentado somente por hipótese, inferência ou julgamento', criterion=cid))
        coverage[cid]={'selected_state':selected.get(cid),
                       'supporting_observations':linked,
                       'reported_observations':empirical,
                       'provisional_observations':provisional,
                       'documented_support':bool(linked)}
    # Registros legados não podem declarar evidência empírica forte quando os
    # próprios vínculos mostram apenas hipótese/inferência.
    evidence_records = case.get('evidence_records', {})
    if isinstance(evidence_records, dict):
        for cid,rec in evidence_records.items():
            if cid not in leaves or not isinstance(rec,dict):
                continue
            if rec.get('evidence_basis') in ('primary_record','secondary_source'):
                if support[cid] and not any(obs_by_id[oid].get('kind')=='reported' for oid in support[cid]):
                    findings.append(_finding('EMPIRICAL_BASIS_WITHOUT_REPORTED_FACT', 'error',
                                             'Registro legado declara base empírica, mas só há hipótese/inferência',criterion=cid))
    for oid in sorted(set(obs_by_id)-used_obs):
        findings.append(_finding('OBSERVATION_NOT_LINKED','warning',
                                 'Observação não utilizada nos critérios',entry=oid))
    for sid in sorted(set(sources_by_id)-used_sources):
        findings.append(_finding('SOURCE_NOT_USED','warning','Fonte cadastrada sem observações',entry=sid))
    shared = [{'observation_id':oid, 'criteria':sorted(crit), 'review_required':True}
              for oid,crit in sorted(obs_criteria.items()) if len(crit)>1]
    for pair in shared:
        findings.append(_finding('SHARED_OBSERVATION','warning',
                                 'Mesmo fato ligado a múltiplos critérios: conferir dupla contagem',
                                 entry=pair['observation_id']))
    # Compatibilidade com registros legados, não elimina obrigação do novo vínculo.
    evidence_records=case.get('evidence_records', {})
    if isinstance(evidence_records, dict):
        for cid,rec in evidence_records.items():
            if not isinstance(rec,dict) or cid not in leaves:
                continue
            for oid in rec.get('fact_ids',[]):
                if oid not in obs_by_id:
                    findings.append(_finding('LEGACY_FACT_NOT_REGISTERED','warning',
                                             'fact_id legado sem entrada na nova coleção',entry=str(oid),criterion=cid))
    result=_package(findings, coverage, shared, sources_by_id, obs_by_id, empty=False)
    private_sources=sorted(sid for sid,src in sources_by_id.items()
                           if src.get('visibility') in ('internal','restricted')
                           or src.get('source_type')=='unpublished_manuscript')
    result['public_release_gate']={
        'status':('BLOCKED_PRIVATE_OR_UNPUBLISHED_SOURCES' if private_sources
                  else 'HUMAN_RIGHTS_AND_CONTENT_REVIEW_REQUIRED'),
        'flagged_sources':private_sources,
        'note':'Este diagnóstico nunca autoriza publicação: direitos, confidencialidade e licenças exigem revisão humana.'}
    return result


def _package(findings, coverage, shared, sources, observations, *, empty=False):
    errors=sum(x['level']=='error' for x in findings)
    warnings=sum(x['level']=='warning' for x in findings)
    status=('INVALID_REGISTRY' if errors else
            'DOCUMENTED_WITH_REVIEW_FLAGS' if warnings else
            'DOCUMENTED_NOT_INDEPENDENTLY_VALIDATED')
    return {'status':status, 'error_count':errors,'warning_count':warnings,
            'source_count':len(sources), 'observation_count':len(observations),
            'criteria_documented':sum(1 for x in coverage.values() if x['documented_support']),
            'coverage':coverage, 'shared_observations':shared, 'findings':findings,
            'limitations':('Cadastro e verificações formais não validam a verdade dos registros, '
                           'não mensuram dependência estatística e não autorizam conclusão ambiental ou regulatória.')}
