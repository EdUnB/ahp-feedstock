'use strict';
/* Interface apenas: nunca recalcula matrizes, pesos, classes ou CR no navegador. */
const $ = id => document.getElementById(id);
const stateLabels = {
  'descarte': 'Descarte', 'nao_descarte': 'Não descarte',
  'intencionalidade_demonstrada': 'Intencionalidade demonstrada',
  'incidental_comprovada': 'Geração incidental comprovada',
  'evidencia_insuficiente': 'Evidência insuficiente',
  'C3a-R1': 'Mercado ausente/marginal', 'C3a-R2': 'Mercado secundário', 'C3a-R3': 'Valor comercial significativo',
  'C3b-R1': 'Oferta inelástica', 'C3b-R2': 'Resposta parcial', 'C3b-R3': 'Oferta responsiva'
};
const readableFlags = {
 'PESOS_M2_APROVADOS_PROVISORIAMENTE_SEM_VALIDACAO_EXTERNA': 'Os pesos do modelo M2 foram aprovados apenas provisoriamente para simulação; não passaram por validação externa.',
 'PESOS_M2_AINDA_NAO_REELICITADOS': 'Os pesos ainda não foram reelicidados independentemente.',
 'C2_EVIDENCIA_INSUFICIENTE_NAO_EQUIVALE_A_GERACAO_INCIDENTAL': 'C2 com evidência insuficiente NÃO demonstra geração incidental.',
 'C2_INCIDENTAL_DECLARADA_SEM_COMPROVACAO': 'A geração incidental foi declarada sem comprovação formal verificada.',
 'C2_INTENCIONALIDADE_DECLARADA_SEM_COMPROVACAO': 'A intencionalidade produtiva foi declarada sem comprovação formal verificada.',
 'C4_VIABILIDADE_NAO_DETERMINADA': 'Viabilidade tecnológica ou logística não determinada.',
 'PROCESSAMENTO_NAO_CARACTERIZADO': 'Processamento ainda não caracterizado.',
 'REFERENCIAL_REGULATORIO_SEM_AVALIACAO': 'O referencial regulatório não foi avaliado nesta análise.'
};
let analysis = null, savedCase = null, metadata = null, evaluationRevision = 0;
const pct = value => `${(100 * Number(value)).toLocaleString('pt-BR',{minimumFractionDigits:2,maximumFractionDigits:2})}%`;
const number = value => Number(value).toLocaleString('pt-BR',{minimumFractionDigits:4,maximumFractionDigits:4});
function element(tag, cls, text) { const node = document.createElement(tag); if (cls) node.className = cls; if (text !== undefined) node.textContent = text; return node; }
function field(id){ return $(id).value.trim(); }
function evidence(key, textareaId){ return {status:'user_reported_unverified', claim:field(textareaId)}; }
function currentCase(){
  const context=field('contextSource');
  return {
    material: field('material'), classification_point: field('point'), region:field('region'),
    states: {C1:field('c1'),C2:field('c2'),C3a:field('c3a'),C3b:field('c3b')},
    state_evidence: {C1:evidence('C1','evC1'), C2:evidence('C2','evC2'), C3a:evidence('C3a','evC3a'), C3b:evidence('C3b','evC3b')},
    complementary_checks:{
      C4:{
        technology:{status:field('technology'), assessment:'Avaliação tecnológica relatada pelo operador; ver a fonte declarada.',source:context},
        logistics:{status:field('logistics'),assessment:'Avaliação logística relatada pelo operador; ver a fonte declarada.',source:context}
      },
      processing:{type:field('processing'),assessment:'Processamento caracterizado pelo operador; ver a fonte declarada.',source:context},
      regulatory_basis:{framework:field('basis'),status:field('regStatus')}
    }
  };
}
function clearResults(){
  evaluationRevision++;
  resetSensitivity();
  analysis=null;savedCase=null;
  $('resultsContent').hidden=true;$('emptyResult').hidden=false;
  $('runFeedback').textContent='';
}
function useDemo(){
  const values={
    material:'Fluxo hipotético X — DEMONSTRAÇÃO SINTÉTICA',region:'Região fictícia, 2026',
    point:'Saída de unidade produtiva fictícia, antes do processamento',
    c1:'nao_descarte',c2:'evidencia_insuficiente',c3a:'C3a-R2',c3b:'C3b-R1',
    evC1:'SINTÉTICO: fluxo hipotético retido para possível aproveitamento produtivo. Não corresponde a evidência observada.',
    evC2:'SINTÉTICO: não existem dados que demonstrem intenção produtiva neste caso fictício.',
    evC3a:'SINTÉTICO: mercado secundário hipotético, sem levantamentos de preços nem contratos.',
    evC3b:'SINTÉTICO: oferta supostamente inelástica, sem estimação econométrica.',
    technology:'unknown',logistics:'unknown',processing:'unknown',regStatus:'not_assessed',
    basis:'Pesquisa experimental; sem enquadramento regulatório',
    contextSource:'SINTÉTICO: condições tecnológicas, logísticas e de processamento não avaliadas.'
  };
  for(const [id,value] of Object.entries(values)) $(id).value=value;
  $('consent').checked=false;clearResults();$('sec-case').scrollIntoView({behavior:'smooth',block:'start'});
}
function resetAll(){ $('analysisForm').reset(); clearResults(); $('material').focus(); }
function download(name,content,type){
  const b=new Blob([content],{type});const url=URL.createObjectURL(b);const a=document.createElement('a');a.href=url;a.download=name;a.click();setTimeout(()=>URL.revokeObjectURL(url),1500);
}
function dateStamp(){ return new Date().toISOString().slice(0,10); }
function safeCsv(cell){
  let text=String(cell ?? ''); if (/^[\s]*[=+@\-]/.test(text)) text="'"+text;
  return '"'+text.replace(/"/g,'""')+'"';
}
function exportJson(){
  if(!analysis) return;
  const payload={
    exported_at:new Date().toISOString(), software:'AHP Feedstock HTML v2.0 · experimental',
    configuration_sha256:metadata?.config_sha256||null,
    user_case:savedCase, computational_result:analysis,
    warning:'CANDIDATO COMPUTACIONAL NÃO VALIDADO; classificação final nula; não define fronteira ou alocação de ACV.'
  };
  download(`ahp_feedstock_${dateStamp()}.json`,JSON.stringify(payload,null,2),'application/json;charset=utf-8');
}
function exportCsv(){
  if(!analysis) return;
  const rows=[['campo','valor'],
   ['data',new Date().toISOString()],['material',savedCase.material],['ponto_de_classificacao',savedCase.classification_point],
   ['modelo',analysis.model_version],['status',analysis.classification_status],['candidato',analysis.computational_candidate.winner],
   ['final_classification','NÃO ATRIBUÍDA'],['margem_pp',analysis.computational_candidate.margin*100]
  ];
  for(const [key,val] of Object.entries(savedCase.states)){ rows.push([`estado_${key}`,val],[`evidencia_${key}`,savedCase.state_evidence[key].claim]); }
  for(const [key,val] of Object.entries(analysis.computational_candidate.priorities))rows.push([`prioridade_${key}`,val]);
  for(const [key,val] of Object.entries(analysis.ahp.terminal_weights))rows.push([`peso_${key}`,val]);
  for(const [key,val] of Object.entries(analysis.ahp.consistency))rows.push([`CR_${key}`,val.CR]);
  for(const flag of analysis.flags)rows.push(['alerta',flag]);
  rows.push(['nota','Os valores AHP não são probabilidades; não definem ACV, alocação ou status jurídico.']);
  download(`ahp_feedstock_${dateStamp()}.csv`,'\ufeff'+rows.map(r=>r.map(safeCsv).join(';')).join('\r\n')+'\r\n','text/csv;charset=utf-8');
}
function renderPriorities(result){
  const holder=$('priorities');holder.replaceChildren();
  const values=result.computational_candidate.priorities;
  const ranking=result.computational_candidate.ranking;
  for(const [idx,label] of ranking.entries()){
    const item=element('div','priority-item'+(idx===0?' first':''));
    const hdr=element('div','priority-label');hdr.append(element('span',null,label.charAt(0).toUpperCase()+label.slice(1)),element('strong',null,pct(values[label])));
    const track=element('div','priority-track'); const bar=element('i');bar.style.width=`${100*Number(values[label])}%`;track.append(bar);
    item.append(hdr,track);holder.append(item);
  }
  $('margin').textContent=`Margem entre as duas primeiras categorias: ${(100*result.computational_candidate.margin).toLocaleString('pt-BR',{minimumFractionDigits:2,maximumFractionDigits:2})} pontos percentuais.`;
}
function renderConsistency(result){
  const table=element('table','consistency-table');
  const thead=element('thead');const tr=element('tr');
  for(const x of ['Matriz / estado','CR','Diagnóstico'])tr.append(element('th',null,x));
  thead.append(tr);table.append(thead);
  const tbody=element('tbody');
  for(const [node,rep] of Object.entries(result.ahp.consistency)){
    const line=element('tr');line.append(element('td',null,node),element('td',null,number(rep.CR)));
    line.append(element('td',rep.acceptable?'status-ok':'status-bad',rep.acceptable?'Aceitável':'Revisar'));
    tbody.append(line);
  }
  table.append(tbody);$('consistency').replaceChildren(table);
}
function render(result,caseData){
  analysis=result;savedCase=caseData;
  $('emptyResult').hidden=true;$('resultsContent').hidden=false;
  $('winner').textContent=result.computational_candidate.tie?'Empate técnico':result.computational_candidate.winner;
  $('winnerNote').textContent=`${caseData.material} · ${caseData.classification_point}`;
  renderPriorities(result);renderConsistency(result);
  const weights=$('appliedWeights');weights.replaceChildren();
  for(const [key,value] of Object.entries(result.ahp.terminal_weights))weights.append(element('span',null,`${key}: ${pct(value)}`));
  const flags=$('flags');flags.replaceChildren();
  if(!result.flags.length)flags.append(element('li',null,'Nenhum alerta operacional adicional. A validação científica permanece pendente.'));
  for(const flag of result.flags)flags.append(element('li',null,readableFlags[flag]||flag));
  $('sec-results').scrollIntoView({behavior:'smooth',block:'start'});
  initSensitivity();
}
async function submit(e){
  e.preventDefault();
  const form=$('analysisForm');
  if(!form.reportValidity())return;
  const payload={case:currentCase(),allow_draft:$('consent').checked};
  const btn=$('calculateBtn');btn.disabled=true;$('runFeedback').textContent='Executando motor Python…';
  clearResults();$('runFeedback').textContent='Executando motor Python…';
  const revision=evaluationRevision;
  try{
    const response=await fetch('/api/evaluate',{
      method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(payload),cache:'no-store'
    });
    const body=await response.json();
    if(revision!==evaluationRevision)return;
    if(!response.ok){
      const detail=body.detail;
      const message=Array.isArray(detail)?detail.map(x=>(x.loc||[]).join('.')+': '+x.msg).join('; '):String(detail||'Erro ao executar o motor');
      throw new Error(message);
    }
    if(body.final_classification!==null||body.separation?.acv_boundary_inferred!==false)throw new Error('Resposta inesperada: a separação entre AHP e ACV não foi preservada.');
    render(body,payload.case);
    $('runFeedback').textContent='Simulação concluída · sem validação externa.';
  }catch(error){
    $('runFeedback').textContent='Erro: '+String(error.message||error);
    console.error('AHP evaluation failed:',error);
  }finally{btn.disabled=false;}
}
async function startup(){
  $('analysisForm').addEventListener('submit',submit);
  $('loadDemo').addEventListener('click',useDemo);
  $('resetBtn').addEventListener('click',resetAll);
  $('jsonExport').addEventListener('click',exportJson);
  $('csvExport').addEventListener('click',exportCsv);
  $('printBtn').addEventListener('click',()=>window.print());
  if(location.protocol==='file:'){
    $('apiStatus').textContent='Prévia visual · motor desconectado';
    $('apiStatus').classList.add('offline');
    $('calculateBtn').disabled=true;
    $('runFeedback').textContent='Para calcular, execute INICIAR_WINDOWS.bat; ele abrirá o endereço correto no navegador.';
    return;
  }
  try{
    const [resp,healthresp]=await Promise.all([fetch('/api/metadata'),fetch('/api/health')]);
    if(!resp.ok||!healthresp.ok)throw new Error('API de pesquisa não está respondendo corretamente.');
    metadata=await resp.json();const health=await healthresp.json();
    if(!health.local_research_preview_enabled){
      $('apiStatus').textContent='Simulação desabilitada';$('apiStatus').classList.add('offline');
      $('systemError').hidden=false;$('systemError').textContent='A interface foi aberta, mas o modo experimental não está habilitado no servidor. Inicie pelo script local fornecido.';
    }else{ $('apiStatus').textContent='Motor local conectado';$('apiStatus').classList.add('online'); }
  }catch(error){
    $('apiStatus').textContent='Motor indisponível';$('apiStatus').classList.add('offline');
    $('systemError').hidden=false;$('systemError').textContent='Falha ao acessar o motor Python. Inicie o aplicativo pelo script INICIAR_WINDOWS.bat ou INICIAR_MAC_LINUX.sh. Esta interface não calcula AHP apenas abrindo o HTML.';
  }
}
document.addEventListener('DOMContentLoaded',startup);
