import {loadPyodide} from 'https://cdn.jsdelivr.net/pyodide/v314.0.8/full/pyodide.mjs';
const base=new URL('./',import.meta.url);
async function start(){
 const py=await loadPyodide({indexURL:'https://cdn.jsdelivr.net/pyodide/v314.0.8/full/'});
 await py.loadPackage('numpy');
 const response=await fetch(new URL('python-files.json',base));
 if(!response.ok)throw new Error('Não foi possível carregar o manifesto do motor.');
 const files=await response.json();
 for(const file of files){
  const resource=await fetch(new URL(file,base));if(!resource.ok)throw new Error('Arquivo indisponível: '+file);
  const bytes=new Uint8Array(await resource.arrayBuffer());
  const path='/workspace/'+file;py.FS.mkdirTree(path.slice(0,path.lastIndexOf('/')));py.FS.writeFile(path,bytes);
 }
 py.runPython("import sys; sys.path[:0]=['/workspace','/workspace/engine']; from bridge import handle; import json");
 return py;
}
const ready=start();let queue=Promise.resolve();
self.onmessage=({data})=>{queue=queue.then(async()=>{
 try{const py=await ready;py.globals.set('_request',JSON.stringify(data));
 const result=py.runPython("json.dumps(handle(json.loads(_request)['path'], json.loads(_request)['payload']), ensure_ascii=False, allow_nan=False)");
 self.postMessage({id:data.id,body:JSON.parse(result),status:200});
 }catch(error){self.postMessage({id:data.id,body:{detail:String(error.message||error)},status:422});}
});};
