const {spawn}=require('node:child_process');
const {once}=require('node:events');
const fs=require('node:fs'),path=require('node:path'),os=require('node:os'),assert=require('node:assert/strict');
const url=process.argv[2]||'http://127.0.0.1:8012/ahp-feedstock/';
const output=path.resolve('local-private/browser-audit');fs.mkdirSync(output,{recursive:true});
const profile=fs.mkdtempSync(path.join(os.tmpdir(),'ahp-chrome-'));
const browser=spawn(process.env.BROWSER_EXE||'C:/Program Files/Google/Chrome/Application/chrome.exe',['--headless','--disable-gpu','--no-first-run','--no-default-browser-check','--remote-debugging-port=0','--user-data-dir='+profile,'about:blank'],{windowsHide:true,stdio:['ignore','ignore','pipe']});
let socket;const failures=[],network=[];let sequence=0;const pending=new Map();
const timer=setTimeout(()=>{console.error('Browser audit timed out');browser.kill();process.exit(1)},210000);
async function main(){
 const endpoint=await new Promise((resolve,reject)=>{let err='';browser.stderr.on('data',chunk=>{err+=chunk;const m=err.match(/DevTools listening on (ws:\/\/[^\s]+)/);if(m)resolve(new URL(m[1]))});browser.once('error',reject);browser.once('exit',c=>reject(new Error('Chrome exit '+c+' '+err.slice(-500))))});
 const targets=await(await fetch('http://'+endpoint.host+'/json/list')).json();socket=new WebSocket(targets.find(t=>t.type==='page').webSocketDebuggerUrl);await once(socket,'open');
 socket.addEventListener('message',({data})=>{const m=JSON.parse(data);if(m.method==='Runtime.exceptionThrown')failures.push(m.params.exceptionDetails.exception?.description||m.params.exceptionDetails.text);if(m.method==='Network.requestWillBeSent')network.push(m.params.request.url);if(m.id){const task=pending.get(m.id);if(task){pending.delete(m.id);m.error?task.reject(Error(m.error.message)):task.resolve(m.result)}}});
 const cdp=(method,params={})=>new Promise((resolve,reject)=>{pending.set(++sequence,{resolve,reject});socket.send(JSON.stringify({id:sequence,method,params}))});
 async function evaluate(expression){const r=await cdp('Runtime.evaluate',{expression,returnByValue:true,awaitPromise:true});if(r.exceptionDetails)throw Error(r.exceptionDetails.exception?.description||r.exceptionDetails.text);return r.result.value}
 async function waitFor(expression,label,ms=120000){const end=Date.now()+ms;while(Date.now()<end){if(await evaluate(expression))return;await new Promise(r=>setTimeout(r,400))}throw Error('Timeout '+label+': '+await evaluate('document.body.innerText.slice(0,1600)'))}
 await cdp('Runtime.enable');await cdp('Network.enable');await cdp('Page.enable');await cdp('Page.navigate',{url});
 await waitFor("[...document.querySelectorAll('.institutional-logos img')].length===2 && [...document.querySelectorAll('.institutional-logos img')].every(i=>i.complete && i.naturalWidth>0)",'institutional logos');
 for(const width of [1440,800,390,320]){
  await cdp('Emulation.setDeviceMetricsOverride',{width,height:900,deviceScaleFactor:1,mobile:width<620});
  await evaluate('window.scrollTo(0,0)');
  const state=await evaluate("({overflow:document.documentElement.scrollWidth>innerWidth+1,logos:[...document.querySelectorAll('.institutional-logos img')].map(i=>({src:i.getAttribute('src'),width:i.getBoundingClientRect().width,height:i.getBoundingClientRect().height,right:i.getBoundingClientRect().right,alt:i.alt})),oldMark:!!document.querySelector('.brand-mark')})");
  assert.equal(state.overflow,false);assert.equal(state.oldMark,false);assert.equal(state.logos.length,2);assert.ok(state.logos.every(i=>i.width>0&&i.height>0&&i.right<=width));
  const shot=await cdp('Page.captureScreenshot',{format:'png',captureBeyondViewport:false});fs.writeFileSync(path.join(output,'header-'+width+'.png'),Buffer.from(shot.data,'base64'));console.log('HEADER_OK',width,JSON.stringify(state));
 }
 assert.deepEqual(failures,[]);
 const report={url,header_widths:[1440,800,390,320],logos:['LEA','PCMEC'],original_images:true};fs.writeFileSync(path.join(output,'header-report.json'),JSON.stringify(report,null,2));console.log('HEADER_AUDIT_PASSED');
}
main().catch(e=>{console.error(e.stack);process.exitCode=1}).finally(()=>{clearTimeout(timer);socket?.close();browser.kill()});
