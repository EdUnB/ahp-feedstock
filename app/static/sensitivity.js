'use strict';
// Rendering and weight controls only. All priorities come from Python.
let sensitivityData=null, sensitivityWeights=[], sensitivityRevision=0, sensitivityTimer;
const colors=['#387a62','#d18a35','#506fc4'];
function resetSensitivity(){
  sensitivityRevision++; clearTimeout(sensitivityTimer); sensitivityData=null;
  $('sensitivityPanel').hidden=true;
}
function initSensitivity(){
  resetSensitivity(); $('sensitivityPanel').hidden=false;
  $('enableSensitivity').checked=false;
  $('sensitivityControls').disabled=true;
  $('sensitivityFeedback').textContent='Baseline de referência provisório. Ative os controles para explorar.';
  // Main weights inferred from returned terminal weights, not hard-coded.
  const t=analysis.ahp.terminal_weights;
  sensitivityWeights=[t.C1,t.C2,t.C3a+t.C3b];
  updateSliderLabels();
  $('sensitivityOutput').replaceChildren(); $('stabilityCharts').replaceChildren();
}
function updateSliderLabels(){
  sensitivityWeights.forEach((v,i)=>{$('weight'+i).value=v*100;$('weightValue'+i).textContent=pct(v);});
  $('weightSum').textContent='Soma: '+pct(sensitivityWeights.reduce((a,b)=>a+b,0));
}
function changeWeight(i,value){
  const x=Number(value)/100, others=[0,1,2].filter(j=>j!==i);
  const total=others.reduce((s,j)=>s+sensitivityWeights[j],0);
  sensitivityWeights[others[0]]=(1-x)*(total>1e-14?sensitivityWeights[others[0]]/total:.5);
  sensitivityWeights[others[1]]=1-x-sensitivityWeights[others[0]];
  sensitivityWeights[i]=x;
  updateSliderLabels(); scheduleSensitivity();
}
function scheduleSensitivity(){
  sensitivityRevision++; sensitivityData=null;
  $('sensitivityFeedback').textContent='Atualizando… exportações disponíveis após o cálculo.';
  $('sensitivityOutput').replaceChildren(); $('stabilityCharts').replaceChildren();
  clearTimeout(sensitivityTimer);
  const revision=sensitivityRevision;
  sensitivityTimer=setTimeout(()=>runSensitivity(revision),150);
}
async function runSensitivity(revision){
  try{
    const response=await fetch('/api/sensitivity',{method:'POST',headers:{'Content-Type':'application/json'},
      body:JSON.stringify({case:savedCase,allow_draft:true,weights:sensitivityWeights})});
    const data=await response.json();
    if(revision!==sensitivityRevision)return;
    if(!response.ok)throw new Error(typeof data.detail==='string'?data.detail:JSON.stringify(data.detail));
    sensitivityData=data; renderSensitivity(data);
    $('sensitivityFeedback').textContent='Atualizado pelo motor Python · exploratório, sem validação externa.';
  }catch(error){if(revision===sensitivityRevision)$('sensitivityFeedback').textContent='Falha: '+error.message;}
}
function svgNode(tag,attrs={},text){
  const n=document.createElementNS('http://www.w3.org/2000/svg',tag);
  Object.entries(attrs).forEach(([k,v])=>n.setAttribute(k,v));if(text!==undefined)n.textContent=text;return n;
}
function chartSvg(label,viewBox){return svgNode('svg',{viewBox,role:'img','aria-label':label});}
function renderSensitivity(data){
  const base=data.baseline.computational_candidate, exp=data.exploratory.computational_candidate;
  const holder=$('sensitivityOutput'); holder.replaceChildren();
  const same=base.tie===exp.tie&&base.winner===exp.winner;
  holder.append(element('h3',null,same?'Categoria candidata mantida':'Categoria candidata alterada'));
  holder.append(element('p',null,`Baseline: ${base.winner||'Empate'} · Exploratório: ${exp.winner||'Empate'}. Classificação final não atribuída.`));
  const table=element('table','consistency-table');
  const head=element('tr');['Critério','Baseline','Exploratório'].forEach(x=>head.append(element('th',null,x)));table.append(head);
  ['C1','C2','C3'].forEach((c,i)=>{const row=element('tr');[c,pct(data.baseline_weights[i]),pct(data.exploratory_weights[i])].forEach(x=>row.append(element('td',null,x)));table.append(row);});holder.append(table);
  const chart=chartSvg('Prioridades baseline e exploratórias por categoria','0 0 620 235');
  const classes=Object.keys(base.priorities);
  const weightChart=chartSvg('Pesos de referência e exploratórios','0 0 620 165');
  ['C1','C2','C3'].forEach((name,i)=>{
    const y=20+i*48;weightChart.append(svgNode('text',{x:0,y:y+15},name));
    [[data.baseline_weights,'Baseline',y,.4],[data.exploratory_weights,'Exploratório',y+19,1]].forEach(([weights,label,top,opacity])=>{
      weightChart.append(svgNode('rect',{x:45,y:top,width:370*weights[i],height:14,fill:'#387a62',opacity}));
      weightChart.append(svgNode('text',{x:50+370*weights[i],y:top+12,'font-size':11},`${label} ${pct(weights[i])}`));
    });
  });holder.append(weightChart);
  classes.forEach((name,i)=>{
    const y=25+i*65;
    chart.append(svgNode('text',{x:0,y},name));
    [[base,'Baseline',y+6],[exp,'Exploratório',y+27]].forEach(([r,label,top])=>{
      const value=r.priorities[name];chart.append(svgNode('rect',{x:140,y:top,width:360*value,height:15,fill:colors[i],opacity:label==='Baseline'?.4:1}));
      chart.append(svgNode('text',{x:145+360*value,y:top+12,'font-size':11},`${label} ${pct(value)}`));
    });
  });holder.append(chart);
  const delta=element('p',null,classes.map(c=>`${c}: Δ ${(100*(exp.priorities[c]-base.priorities[c])).toFixed(2)} p.p.`).join(' · '));holder.append(delta);
  const charts=$('stabilityCharts'); charts.replaceChildren();
  const legend=element('p',null,classes.map((c,i)=>`${c} (${['verde','laranja','azul'][i]})`).join(' · ')+' · Empate: cinza');charts.append(legend);
  const grid=chartSvg('Mapa triangular de categorias candidatas, malha de 5 pontos percentuais','0 0 440 400');
  const xy=w=>[50+340*(w[1]+w[2]/2),340-294*w[2]];
  for(const region of data.stability.regions){
    if(region.vertices.length)grid.append(svgNode('polygon',{points:region.vertices.map(w=>xy(w).join(',')).join(' '),fill:colors[classes.indexOf(region.winner)],opacity:.2}));
  }
  grid.append(svgNode('path',{d:'M50 340 L390 340 L220 46 Z',fill:'none',stroke:'#aaa'}));
  for(const point of data.grid){const [x,y]=xy(point.weights), r=point.candidate;
    const dot=svgNode('circle',{cx:x,cy:y,r:4.6,fill:r.tie?'#777':colors[classes.indexOf(r.winner)]});
    dot.append(svgNode('title',{},`C1 ${pct(point.weights[0])}; C2 ${pct(point.weights[1])}; C3 ${pct(point.weights[2])}: ${r.winner||'Empate'}`));grid.append(dot);}
  [['Baseline',data.baseline_weights,'#111',8],['Atual',data.exploratory_weights,'#d22',5]].forEach(([name,w,color,r])=>{const [x,y]=xy(w);grid.append(svgNode('circle',{cx:x,cy:y,r,fill:'none',stroke:color,'stroke-width':2}));grid.append(svgNode('text',{x:x+9,y:y-7,'font-size':12,fill:color},name));});
  [[35,363,'C1 100%'],[330,363,'C2 100%'],[190,30,'C3 100%']].forEach(([x,y,t])=>grid.append(svgNode('text',{x,y},t)));charts.append(grid);
  charts.append(element('p',null,'Regiões calculadas pela interseção das diferenças lineares de prioridades; pontos de conferência em malha de 231 combinações (5 p.p.). Empates com tolerância de 10⁻⁹ podem formar faixas menores que um pixel. As cores não representam probabilidades nem validação.'));
  Object.entries(data.sweeps).forEach(([criterion,points],i)=>{
    charts.append(element('h3',null,criterion+' — varredura a partir do baseline'));
    const svg=chartSvg('Prioridades ao variar '+criterion,'0 0 620 240');
    [0,50,100].forEach(v=>{const y=190-1.6*v;svg.append(svgNode('line',{x1:45,x2:565,y1:y,y2:y,stroke:'#ddd'}));svg.append(svgNode('text',{x:3,y:y+4,'font-size':12},v+'%'));});
    classes.forEach((name,k)=>svg.append(svgNode('polyline',{points:points.map((p,j)=>`${45+5.2*j},${190-160*p.candidate.priorities[name]}`).join(' '),fill:'none',stroke:colors[k],'stroke-width':2})));
    const x=45+520*data.baseline_weights[i];svg.append(svgNode('line',{x1:x,x2:x,y1:25,y2:190,stroke:'#111','stroke-dasharray':'4 4'}));
    [0,50,100].forEach(v=>svg.append(svgNode('text',{x:40+5.2*v,y:213,'font-size':12},v+'%')));charts.append(svg);
    const count=points.filter(p=>p.candidate.winner===base.winner&&p.candidate.tie===base.tie).length;
    charts.append(element('p',null,`${count}/101 pontos mantêm a categoria/empate do baseline. Passo de 1 p.p.; demais pesos redistribuídos proporcionalmente. Linha tracejada: peso baseline. Não mede probabilidade de acerto.`));
    const limits=element('table','consistency-table');
    const header=element('tr');['Limite inferior (%)','Limite superior (%)','Categoria no interior'].forEach(t=>header.append(element('th',null,t)));limits.append(header);
    data.stability.paths[criterion].intervals.forEach(interval=>{
      const row=element('tr');[(100*interval.lower).toFixed(8),(100*interval.upper).toFixed(8),interval.winner||'Empate'].forEach(t=>row.append(element('td',null,t)));limits.append(row);
    });charts.append(limits);
    charts.append(element('p',null,'Limites calculados, não inferidos da malha. As linhas descrevem interiores abertos; a classificação nos limites é exportada separadamente. A precisão exibida é numérica, não precisão das evidências.'));
  });
}
function sensitivityCsvRows(data){
  const rows=[['cenario','C1','C2','C3','resíduo','subproduto','coproduto','candidato','empate','margem','status','config_sha256','run_id','calculated_at_utc','engine_model_version','software_version','classification_changed','execution_metadata_json']];
  const metadata={user_case:data.user_case,method:data.method,stability:data.stability,
    baseline_weights:data.baseline_weights,exploratory_weights:data.exploratory_weights,
    configuration_sha256:data.configuration_sha256,run_id:data.run_id,calculated_at_utc:data.calculated_at_utc,
    engine_model_version:data.engine_model_version,software_version:data.software_version,
    classification_changed:data.classification_changed,priority_delta:data.priority_delta,
    reference_configuration:data.reference_configuration,engine_source_sha256:data.engine_source_sha256};
  const add=(name,w,c)=>rows.push([name,...w,...['resíduo','subproduto','coproduto'].map(k=>c.priorities[k]),c.winner,c.tie,c.margin,'EXPLORATORIO_NAO_VALIDADO',data.configuration_sha256,data.run_id,data.calculated_at_utc,data.engine_model_version,data.software_version,data.classification_changed,name==='baseline'?JSON.stringify(metadata):'']);
  add('baseline',data.baseline_weights,data.baseline.computational_candidate);
  add('exploratorio',data.exploratory_weights,data.exploratory.computational_candidate);
  Object.entries(data.sweeps).forEach(([key,ps])=>ps.forEach(p=>add('varredura_'+key,p.weights,p.candidate)));
  data.grid.forEach(p=>add('malha',p.weights,p.candidate));
  return rows;
}
function exportSensitivity(kind){
  if(!sensitivityData){$('sensitivityFeedback').textContent='Aguarde o cálculo da análise antes de exportar.';return;}
  if(kind==='json')download(`ahp_sensibilidade_${dateStamp()}.json`,JSON.stringify({exported_at:new Date().toISOString(),software:'AHP Feedstock HTML v2.0',...sensitivityData},null,2),'application/json;charset=utf-8');
  else{
    const rows=sensitivityCsvRows(sensitivityData);
    download(`ahp_sensibilidade_${dateStamp()}.csv`,'\ufeff'+rows.map(r=>r.map(safeCsv).join(';')).join('\r\n'),'text/csv;charset=utf-8');
  }
}
function restoreReferenceWeights(){
  sensitivityWeights=sensitivityData?[...sensitivityData.baseline_weights]:[analysis.ahp.terminal_weights.C1,analysis.ahp.terminal_weights.C2,analysis.ahp.terminal_weights.C3a+analysis.ahp.terminal_weights.C3b];
  updateSliderLabels();scheduleSensitivity();
}
document.addEventListener('DOMContentLoaded',()=>{
  ['C1','C2','C3'].forEach((name,i)=>$('weight'+i).addEventListener('input',e=>changeWeight(i,e.target.value)));
  $('enableSensitivity').addEventListener('change',e=>{
    $('sensitivityControls').disabled=!e.target.checked;
    if(e.target.checked)scheduleSensitivity();else initSensitivity();
  });
  $('restoreWeights').addEventListener('click',restoreReferenceWeights);
  $('sensitivityJson').addEventListener('click',()=>exportSensitivity('json'));
  $('sensitivityCsv').addEventListener('click',()=>exportSensitivity('csv'));
  $('analysisForm').addEventListener('input',()=>{clearResults();$('runFeedback').textContent='Dados alterados. Execute novamente o AHP.';});
});
