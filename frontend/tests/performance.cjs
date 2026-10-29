/* Production Studio network/render benchmark on the isolated fixture only. */
const {chromium}=require('playwright');
const fs=require('node:fs');const path=require('node:path');const assert=require('node:assert/strict');
if(process.env.ONEFL_E2E!=='1')throw new Error('Use the isolated fixture and ONEFL_E2E=1');
const label=process.argv[2];if(!['before','after'].includes(label))throw new Error('Pass before or after');
const BASE=process.env.ONEFL_TEST_URL||'http://127.0.0.1:3100';
const FIXTURE=process.env.ONEFL_FIXTURE_URL||'http://127.0.0.1:8000';
const OUT=path.resolve(__dirname,'../../tmp/performance');fs.mkdirSync(OUT,{recursive:true});
const KEY='onefl-browser-fixture-access-2026';
(async()=>{
 const cached=process.env.LOCALAPPDATA+'/ms-playwright/chromium-1248/chrome-win64/chrome.exe';
 const browser=await chromium.launch({headless:true,executablePath:process.env.ONEFL_BROWSER||(fs.existsSync(cached)?cached:undefined)});
 const context=await browser.newContext({viewport:{width:1440,height:1000}});let pid;
 try{
  let r=await context.request.post(BASE+'/api/v1/auth/login',{data:{token:KEY}});assert.ok(r.ok());
  r=await context.request.post(BASE+'/api/v1/projects',{data:{title:'Isolated Studio performance',source_language:'en',target_language:'vi'}});assert.ok(r.ok());pid=(await r.json()).id;
  r=await context.request.post(FIXTURE+'/__e2e/control',{headers:{'x-e2e-key':KEY},data:{seed_project_id:pid,seed_count:1000}});assert.ok(r.ok(),await r.text());
  const results=[];
  for(let i=0;i<3;i++){
   const page=await context.newPage();const requests=[];const errors=[];let bytes=0;const bodies=[];
   const matches=url=>{const u=new URL(url);return u.pathname.startsWith('/api/v1/projects/'+pid)&&!u.pathname.includes('/ws/')};
   page.on('request',r=>{if(r.method()==='GET'&&matches(r.url()))requests.push(new URL(r.url()).pathname)});
   page.on('response',r=>{if(matches(r.url()))bodies.push(r.body().then(b=>bytes+=b.length).catch(()=>{}))});
   page.on('pageerror',e=>errors.push(e.message));
   const start=performance.now();await page.goto(BASE+'/projects/'+pid);
   await page.getByTitle('Bấm để chỉnh sửa bản dịch câu này').first().waitFor();const readyMs=performance.now()-start;
   await page.waitForTimeout(1200);await Promise.all(bodies);
   assert.deepEqual(errors,[]);results.push({ready_ms:readyMs,resource_gets:requests.length,response_bytes:bytes,requests});await page.close();
  }
  fs.writeFileSync(OUT+'/browser-'+label+'.json',JSON.stringify({label,cues:1000,repeats:3,results},null,2));
  console.log(JSON.stringify({label,cues:1000,results}));
 }finally{if(pid)await context.request.delete(BASE+'/api/v1/projects/'+pid);await browser.close()}
})().catch(e=>{console.error(e);process.exit(1)});
