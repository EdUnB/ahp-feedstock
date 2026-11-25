/* Transport adapter: calculation remains in the preserved Python engine. */
(()=>{
 const originalFetch=window.fetch.bind(window);let serial=0;const pending=new Map();
 const worker=new Worker(new URL('browser-worker.mjs',document.baseURI),{type:'module'});
 const notice=document.createElement('p');notice.setAttribute('role','status');notice.style.cssText='margin:0;padding:12px 24px;background:#edf3f6;font:16px/1.5 sans-serif';
 notice.textContent='Preparando o motor Python no navegador. O primeiro carregamento pode demorar; a análise é exploratória.';
 document.body.prepend(notice);
 worker.onmessage=({data})=>{const task=pending.get(data.id);if(!task)return;clearTimeout(task.timer);pending.delete(data.id);task.resolve(new Response(JSON.stringify(data.body),{status:data.status,headers:{'Content-Type':'application/json'}}));if(data.status===200)notice.textContent='Motor Python carregado. Cálculos executados neste navegador; os campos do caso não são enviados a um servidor de cálculo.';};
 worker.onerror=()=>{notice.textContent='Falha ao carregar o motor. Verifique a conexão e recarregue a página.';for(const task of pending.values()){clearTimeout(task.timer);task.reject(new Error('Falha no motor Python.'));}pending.clear();};
 window.fetch=(input,options={})=>{
  const url=new URL(typeof input==='string'?input:input.url,document.baseURI);
  if(url.origin!==location.origin||!['/api/metadata','/api/health','/api/evaluate','/api/sensitivity'].includes(url.pathname))return originalFetch(input,options);
  if(options.signal?.aborted)return Promise.reject(new DOMException('Aborted','AbortError'));
  return new Promise((resolve,reject)=>{const id=++serial;const timer=setTimeout(()=>{pending.delete(id);reject(new Error('Tempo de carregamento excedido. Recarregue a página.'));},180000);pending.set(id,{resolve,reject,timer});worker.postMessage({id,path:url.pathname,payload:options.body?JSON.parse(options.body):{}});});
 };
})();
