const fs=require('node:fs');const path=require('node:path');const assert=require('node:assert/strict');
const ts=require('../node_modules/typescript');const mod={};
const source=fs.readFileSync(path.join(__dirname,'../src/lib/refreshCoordinator.ts'),'utf8');
new Function('exports',ts.transpileModule(source,{compilerOptions:{module:ts.ModuleKind.CommonJS,target:ts.ScriptTarget.ES2020}}).outputText)(mod);
const sleep=ms=>new Promise(r=>setTimeout(r,ms));
(async()=>{
 let calls=0;const burst=mod.createRefreshCoordinator(async()=>{calls++},5);
 await Promise.all(Array.from({length:12},()=>burst.request()));assert.equal(calls,1);burst.cancel();
 let release,entered;const started=new Promise(r=>entered=r);const blocked=new Promise(r=>release=r);calls=0;
 const trailing=mod.createRefreshCoordinator(async()=>{calls++;if(calls===1){entered();await blocked}},5);
 const first=trailing.request();await started;const second=trailing.request();const third=trailing.request();release();
 await Promise.all([first,second,third]);assert.equal(calls,2);trailing.cancel();
 calls=0;const cancelled=mod.createRefreshCoordinator(async()=>{calls++},5);
 const pending=cancelled.request();cancelled.cancel();await pending;await sleep(15);assert.equal(calls,0);
 const failed=mod.createRefreshCoordinator(async()=>{throw new Error('fetch failed')},1);
 const results=await Promise.allSettled([failed.request(),failed.request()]);assert.ok(results.every(r=>r.status==='rejected'));failed.cancel();
 console.log('Refresh burst, trailing invalidation, teardown and errors: passed');
})().catch(e=>{console.error(e);process.exitCode=1});
