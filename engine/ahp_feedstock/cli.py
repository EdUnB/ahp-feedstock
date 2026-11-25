"""Executa o motor AHP e salva auditoria. Ex.: python run.py examples/marcela_m0_matrizes_completas.json results/run.json"""
import argparse
import hashlib
import json
from pathlib import Path
from ahp_feedstock import (evaluate, inspect_config, sensitivity_main_criteria,
                           joint_judgment_scenarios, root_weight_decision_boundaries,
                           audit_case_evidence, audit_judgment_ledger,
                           state_switch_sensitivity, joint_state_scenarios,
                           criterion_structure_scenarios, paired_state_grid,
                           audit_evidence_overlap, additive_pair_sensitivity,
                           terminal_ablation_diagnostic, audit_observation_registry,
                           evaluate_expert_panel, build_group_configuration)


def main():
    parser=argparse.ArgumentParser(description='Motor AHP, auditoria e testes de sensibilidade')
    parser.add_argument('config',help='arquivo JSON de configuração')
    parser.add_argument('output',nargs='?',help='arquivo JSON de resultados')
    parser.add_argument('--block-inconsistent',action='store_true',help='bloqueia matrizes com CR > 0.10, inclusive em estados inativos')
    parser.add_argument('--sensitivity',action='store_true',help='inclui perturbação ±10%% nos pesos principais')
    parser.add_argument('--joint-scenarios', type=int, default=0,
                        help='numero de simulacoes HIPOTETICAS de perturbacoes simultaneas')
    parser.add_argument('--joint-factor', type=float, default=.20,
                        help='amplitude multiplicativa log-uniforme, e.g. .20')
    parser.add_argument('--joint-seed', type=int, default=20261028,
                        help='semente fixa para reprodutibilidade')
    parser.add_argument('--no-consistency-filter', action='store_true',
                        help='inclui amostras com CR > 0.10 (sinalize essa escolha no relato)')
    parser.add_argument('--weight-thresholds', action='store_true',
                        help='diagnostica limiares exatos de inversao via pesos principais')
    parser.add_argument('--require-evidence', action='store_true',
                        help='recusa registros incompletos; hipóteses declaradas continuam provisórias')
    parser.add_argument('--state-switches', action='store_true',
                        help='sensibilidade de estado com alternativas registradas (se disponíveis)')
    parser.add_argument('--all-state-switches', action='store_true',
                        help='varre todos os estados catalogados como hipóteses')
    parser.add_argument('--joint-evidence-states', action='store_true',
                        help='enumera combinações de estados alternativos documentados; NÃO são probabilidades')
    parser.add_argument('--structural-criterion',
                        help='compara exclusão/renormalização e neutralização de critério principal, ex.: C4')
    parser.add_argument('--paired-state-grid', nargs=4,
                        metavar=('CRITERIO_A','ALT_A','CRITERIO_B','ALT_B'),
                        help='grade contrafactual 2x2, NÃO estima dependência estatística')
    parser.add_argument('--overlap-audit', action='store_true',
                        help='sinaliza fontes e fatos compartilhados; NÃO mede correlação')
    parser.add_argument('--pair-additivity', nargs=4,
                        metavar=('CRITERIO_A','ALT_A','CRITERIO_B','ALT_B'),
                        help='verifica decomposição aditiva para dois estados contrafactuais')
    parser.add_argument('--ablate-terminal',
                        help='exclui um critério terminal e renormaliza pesos restantes (hipotético)')
    parser.add_argument('--observation-audit', action='store_true',
                        help='audita cadastro estruturado de fontes, observações e vínculos')
    parser.add_argument('--require-observation-registry', action='store_true',
                        help='exige cadastro completo dos estados; não comprova validade científica')
    parser.add_argument('--expert-panel',
                        help='arquivo JSON com julgamentos individuais, nunca substitui o caso original')
    parser.add_argument('--expert-method',choices=['aij','aip','both'],default='both',
                        help='agrupamento dos julgamentos (AIJ) ou prioridades locais (AIP)')
    parser.add_argument('--expert-consistency',choices=['warn','block'],default='warn',
                        help='bloqueia ou alerta sobre matrizes individuais inconsistentes')
    parser.add_argument('--expert-dispersion-threshold',type=float,default=1.5,
                        help='limiar descritivo heurístico, não é critério de validade científica')
    parser.add_argument('--export-group-configs',
                        help='diretório de exportação de configurações AIJ/AIP com origem auditável')
    parser.add_argument('--require-expert-rationales',action='store_true',
                        help='rejeita avaliações sem justificativas individuais por matriz')
    args=parser.parse_args()
    if args.export_group_configs and not args.expert_panel:
        parser.error('--export-group-configs requer --expert-panel')
    src=Path(args.config).read_bytes()
    config=json.loads(src.decode('utf-8'))
    configuration_audit=inspect_config(config)
    if args.block_inconsistent and configuration_audit['consistency_warnings']:
        parser.error('Configuração contém matrizes inconsistentes: '+'; '.join(configuration_audit['consistency_warnings']))
    result=evaluate(config,config['case']['states'],consistency_policy='block' if args.block_inconsistent else 'warn')
    evidence_audit=audit_case_evidence(config)
    judgment_audit=audit_judgment_ledger(config)
    registry_audit = audit_observation_registry(config) if (args.observation_audit or args.require_observation_registry) else None
    if args.require_observation_registry and (registry_audit['status']=='NOT_PROVIDED' or registry_audit['error_count']):
        parser.error('Cadastro estruturado ausente ou inválido; consulte --observation-audit')
    if args.require_evidence and evidence_audit['error_count']:
        parser.error(f'Auditoria de evidências incompleta: {evidence_audit["error_count"]} erros')
    report={'quality_gates': {
                'mathematics': result['validation_status'],
                'state_evidence': evidence_audit['status'],
                'pairwise_justifications': judgment_audit['status'],
                'independent_scientific_validation': 'NOT_PERFORMED',
                'regulatory_verification': 'NOT_PERFORMED'},
            'evidence_audit': evidence_audit, 'judgment_audit': judgment_audit,
            'input_sha256':hashlib.sha256(src).hexdigest(),
            'case':config['case'], 'configuration_audit':configuration_audit, **result}
    if registry_audit is not None:
        report['observation_registry_audit']=registry_audit
        report['quality_gates']['observation_registry']=registry_audit['status']
    if args.sensitivity:
        report['sensitivity_main_criteria_10pct']=sensitivity_main_criteria(config,config['case']['states'],fraction=.1)
    if args.joint_scenarios:
        report['hypothetical_joint_judgment_scenarios']=joint_judgment_scenarios(
            config, config['case']['states'], iterations=args.joint_scenarios,
            max_relative_change=args.joint_factor, seed=args.joint_seed,
            consistency_filter=not args.no_consistency_filter)
    if args.weight_thresholds:
        report['root_weight_decision_boundaries']=root_weight_decision_boundaries(
            config, config['case']['states'])
    if args.state_switches or args.all_state_switches:
        report['state_switch_sensitivity']=state_switch_sensitivity(
            config, recorded_alternatives_only=not args.all_state_switches)
    if args.joint_evidence_states:
        report['joint_evidence_states']=joint_state_scenarios(config)
    if args.structural_criterion:
        report['structural_criterion_scenarios']=criterion_structure_scenarios(
            config, config['case']['states'], args.structural_criterion,
            consistency_policy='block' if args.block_inconsistent else 'warn')
    if args.paired_state_grid:
        left, alternative_left, right, alternative_right = args.paired_state_grid
        report['paired_state_grid']=paired_state_grid(
            config,config['case']['states'],left,right,alternative_left,alternative_right,
            consistency_policy='block' if args.block_inconsistent else 'warn')
    if args.overlap_audit:
        report['evidence_overlap_audit']=audit_evidence_overlap(config)
    if args.pair_additivity:
        left, alternative_left, right, alternative_right = args.pair_additivity
        report['pair_additivity']=additive_pair_sensitivity(
            config,config['case']['states'],left,right,alternative_left,alternative_right,
            consistency_policy='block' if args.block_inconsistent else 'warn')
    if args.ablate_terminal:
        report['terminal_ablation']=terminal_ablation_diagnostic(
            config,config['case']['states'],args.ablate_terminal,
            consistency_policy='block' if args.block_inconsistent else 'warn')
    if args.expert_panel:
        panel_path=Path(args.expert_panel)
        panel=json.loads(panel_path.read_text(encoding='utf-8'))
        try:
            group=evaluate_expert_panel(config,panel,method=args.expert_method,
                                        consistency_policy=args.expert_consistency,
                                        dispersion_threshold=args.expert_dispersion_threshold,
                                        require_rationales=args.require_expert_rationales)
        except ValueError as exc:
            parser.error(f'Painel de avaliadores inválido: {exc}')
        report['expert_panel_analysis']=group
        report['quality_gates']['expert_panel_consistency']=group['consistency_gate']
        report['quality_gates']['expert_panel_coverage']=group['status']
        report['quality_gates']['expert_rationales']=group['rationale_audit']['status']
        report['quality_gates']['expert_case_state_resolution']=group['case_state_status']
        report['quality_gates']['expert_group_classification_conditional']=group['group_classification_is_conditional']
        report['quality_gates']['expert_panel_empirical_validation']='NOT_PERFORMED'
        report['expert_panel_input_sha256']=hashlib.sha256(panel_path.read_bytes()).hexdigest()
        if args.export_group_configs:
            target_dir=Path(args.export_group_configs)
            target_dir.mkdir(parents=True, exist_ok=True)
            for group_method in group['methods']:
                exported=build_group_configuration(config,group,group_method)
                (target_dir / f'grupo_{group_method}.json').write_text(
                    json.dumps(exported,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    payload=json.dumps(report,indent=2,ensure_ascii=False)+'\n'
    if args.output:
        dest=Path(args.output)
        dest.parent.mkdir(parents=True,exist_ok=True)
        dest.write_text(payload,encoding='utf-8')
        print('Arquivo de resultados:',dest,'\nClassificação:',result['result']['winner'],
              '\nStatus:',configuration_audit['configuration_status'])
    else:
        print(payload)


