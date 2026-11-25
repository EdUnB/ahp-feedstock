// Production control/serialization functions exercised without a browser.
const fs=require('node:fs'),vm=require('node:vm'),assert=require('node:assert/strict'),path=require('node:path');
const data=JSON.parse(fs.readFileSync(0,'utf8'));
const elements=new Map();
const document={addEventListener(){},getElementById(id){if(!elements.has(id))elements.set(id,{replaceChildren(){},value:0,textContent:''});return elements.get(id);}};
const context=vm.createContext({document,setTimeout(){return 1;},clearTimeout(){},console});
const base=path.join(__dirname,'../app/static');
vm.runInContext(fs.readFileSync(path.join(base,'app.js'),'utf8'),context);
vm.runInContext(fs.readFileSync(path.join(base,'sensitivity.js'),'utf8'),context);
context.input=data;
vm.runInContext('sensitivityWeights=[...input.baseline_weights]',context);
for(let n=0;n<300;n++){
  const i=n%3,value=(n*137)%1001/10;
  vm.runInContext(`changeWeight(${i},${value})`,context);
  const w=vm.runInContext('sensitivityWeights',context);
  assert.ok(w.every(x=>x>=-1e-14&&x<=1+1e-14));
  assert.ok(Math.abs(w.reduce((a,b)=>a+b)-1)<1e-14);
}
vm.runInContext('changeWeight(0,100);changeWeight(0,0)',context);
assert.equal(vm.runInContext('sensitivityWeights[1]',context),.5);
assert.equal(vm.runInContext('sensitivityWeights[2]',context),.5);
vm.runInContext('sensitivityData=input;restoreReferenceWeights()',context);
assert.equal(JSON.stringify(vm.runInContext('sensitivityWeights',context)),JSON.stringify(data.baseline_weights));
const rows=vm.runInContext('sensitivityCsvRows(input)',context);
assert.equal(rows.length,537);
assert.ok(rows.every(row=>row.length===rows[0].length));
const meta=JSON.parse(rows[1][rows[0].indexOf('execution_metadata_json')]);
assert.equal(JSON.stringify(meta.user_case),JSON.stringify(data.user_case));
assert.equal(JSON.stringify(meta.reference_configuration),JSON.stringify(data.reference_configuration));
assert.equal(meta.run_id,data.run_id);
assert.equal(meta.software_version,'2.0.0');
assert.equal(vm.runInContext(`safeCsv('=2+3')`,context),'"\'=2+3"');
context.captured=[];
vm.runInContext('download=(name,content,type)=>captured.push({name,content,type});sensitivityData=input;exportSensitivity("json");exportSensitivity("csv")',context);
assert.equal(context.captured.length,2);
process.stdout.write(JSON.stringify({rows:rows.length,metadata:meta,baseline:rows[1],exploratory:rows[2],exports:context.captured}));
