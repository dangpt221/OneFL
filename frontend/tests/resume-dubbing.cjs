/* Isolated fixture only: ONEFL_E2E=1, separate backend/work directory. */
const {chromium}=require('playwright');
const assert=require('node:assert/strict'), fs=require('node:fs'), path=require('node:path');
if(process.env.ONEFL_E2E!=='1') throw new Error('Requires isolated fixture');
const BASE=process.env.ONEFL_TEST_URL||'http://127.0.0.1:3100';
const FIXTURE=process.env.ONEFL_FIXTURE_URL||'http://127.0.0.1:8100';
const OUT=path.resolve(process.env.ONEFL_TEST_ARTIFACTS||'tmp/resume-dubbing-fix');
const KEY='onefl-browser-fixture-access-2026';
const results=[],errors=[],networkErrors=[];
const write=()=>fs.writeFileSync(path.join(OUT,'browser-results.json'),JSON.stringify({results,errors,networkErrors},null,2));
async function scenario(name,fn){try{await fn();results.push({name,status:'passed'});console.log('PASS',name)}catch(e){results.push({name,status:'failed',error:e.message});throw e}finally{write()}}
(async()=>{
 const browser=await chromium.launch({headless:true,executablePath:process.env.ONEFL_BROWSER||(process.env.LOCALAPPDATA&&fs.existsSync(process.env.LOCALAPPDATA+'/ms-playwright/chromium-1248/chrome-win64/chrome.exe')?process.env.LOCALAPPDATA+'/ms-playwright/chromium-1248/chrome-win64/chrome.exe':undefined)});
 const context=await browser.newContext({viewport:{width:1366,height:950}});
 const p=await context.newPage();p.setDefaultTimeout(15000);
 p.on('pageerror',e=>errors.push(e.message));p.on('requestfailed',r=>{if(!r.failure()?.errorText.includes('ABORTED'))networkErrors.push(r.url())});
 await context.tracing.start({screenshots:true,snapshots:true});
 const api=async(route,method='GET',data)=>{const r=await p.request.fetch(BASE+'/api/v1'+route,{method,data});assert.ok(r.ok(),`${method} ${route}: ${r.status()} ${await r.text()}`);return r.json()};
 const control=async data=>{const r=await p.request.post(FIXTURE+'/__e2e/control',{headers:{'x-e2e-key':KEY},data});assert.ok(r.ok())};
 let id,posts=0;
 p.on('request',r=>{if(r.method()==='POST'&&r.url().endsWith('/resume-dubbing'))posts++});
 const project=()=>api('/projects/'+id);
 const until=async(test,label)=>{for(let i=0;i<250;i++){if(await test())return;await p.waitForTimeout(100)}throw new Error('Timeout: '+label)};
 const failed=()=>until(async()=>{const x=await project();return x.status==='FAILED'&&!x.active_job_id},'failed/idle');
 const dub=()=>api('/tts/projects/'+id+'/dub','POST',{voice:'vi-VN-HoaiMyNeural'});
 const resume=()=>p.getByRole('button',{name:'Tiếp tục chạy',exact:true});
 const upload=async pid=>{
  const r=await p.request.post(BASE+'/api/v1/projects/'+pid+'/upload',{multipart:{file:{name:'source.mp4',mimeType:'video/mp4',buffer:fs.readFileSync(path.join(OUT,'runtime/source.mp4'))},auto_start_pipeline:'false'}});
  assert.ok(r.ok(),await r.text());
 };
 try{
  const login=await p.request.post(BASE+'/api/v1/auth/login',{data:{token:KEY}});assert.ok(login.ok());
  id=(await api('/projects','POST',{title:'Resume regression '+Date.now(),source_language:'en',target_language:'vi'})).id;
  await upload(id);await api('/projects/'+id+'/subtitles','POST',{cue_index:1,start_time:.1,end_time:1.3,original_text:'Hello',translated_text:'Xin chao'});
  await scenario('active dubbing hides both resume actions',async()=>{
   await control({fail_tts:true,speech_delay:3});await dub();await p.goto(BASE+'/projects/'+id);
   await p.getByText(/Tác vụ đang chạy hoặc chờ worker/).waitFor();
   assert.equal(await resume().count(),0);assert.equal(await p.getByRole('button',{name:'Tiếp tục từ điểm dừng',exact:true}).count(),0);
   await failed();await resume().waitFor();assert.equal(await p.getByRole('button',{name:'Thử lại',exact:true}).count(),0);
  });
  await scenario('preflight detects job started in another tab without POST',async()=>{
   const before=posts;let intercepted=false;
   await p.route('**/api/v1/projects/'+id,async route=>{
    if(!intercepted&&route.request().method()==='GET'){intercepted=true;await dub()}
    await route.continue();
   });
   await resume().click();await until(()=>Promise.resolve(intercepted),'preflight intercepted');
   await resume().waitFor({state:'hidden'});assert.equal(posts,before);await p.unroute('**/api/v1/projects/'+id);
   await failed();await resume().waitFor();
  });
  await scenario('concurrent HTTP resumes return one active job',async()=>{
   const r=await Promise.all(Array.from({length:3},()=>api('/projects/'+id+'/resume-dubbing','POST')));
   assert.equal(new Set(r.map(x=>x.job_id)).size,1);assert.ok(r.some(x=>x.already_active));assert.equal((await project()).active_job_id,r[0].job_id);
   await failed();await resume().waitFor();
  });
  await scenario('double click submits once and publishes resumed dubbing',async()=>{
   await control({fail_tts:false,speech_delay:.2});const before=posts;
   await resume().evaluate(button=>{button.click();button.click()});
   await until(async()=>{const x=await project();return !x.active_job_id&&!!x.dubbed_video_url},'resumed output');
   assert.equal(posts-before,1);assert.equal(await resume().count(),0);
   await p.screenshot({path:path.join(OUT,'resumed-output.png'),fullPage:true});
  });
  await scenario('resume conflict displays inline error without losing recovery action',async()=>{
   const cue=(await api('/projects/'+id+'/subtitles')).items[0];
   await api('/projects/'+id+'/subtitles/'+cue.id,'PATCH',{translated_text:'Loi moi'});
   await control({fail_tts:true,speech_delay:.1});await dub();await failed();await resume().waitFor();
   await p.route('**/resume-dubbing',r=>r.fulfill({status:409,contentType:'application/json',body:JSON.stringify({detail:'Cancellation is pending; wait before resuming dubbing'})}));
   await resume().click();await p.getByRole('alert').filter({hasText:'Cancellation is pending'}).waitFor();
   assert.equal(await resume().isEnabled(),true);await p.screenshot({path:path.join(OUT,'resume-error.png'),fullPage:true});
   await p.unroute('**/resume-dubbing');
  });
  await scenario('translation failure does not offer dubbing resume',async()=>{
   const other=(await api('/projects','POST',{title:'Translation failure',source_language:'en',target_language:'vi'})).id;
   await upload(other);await control({fail_translation:true,delay:.1});
   await api('/projects/'+other+'/pipeline/trigger','POST',{});id=other;
   await failed();await p.goto(BASE+'/projects/'+id);await p.getByRole('button',{name:'Thử lại',exact:true}).waitFor();
   assert.equal(await resume().count(),0);assert.equal(await p.getByRole('button',{name:'Tiếp tục từ điểm dừng',exact:true}).count(),0);
  });
  assert.deepEqual(errors,[]);assert.deepEqual(networkErrors,[]);console.log('RESUME BROWSER SCENARIOS',results.length);
 }catch(e){console.error(e);await p.screenshot({path:path.join(OUT,'failure.png'),fullPage:true}).catch(()=>{});process.exitCode=1}
 finally{write();await context.tracing.stop({path:path.join(OUT,'browser-trace.zip')});await browser.close()}
})().catch(e=>{console.error(e);process.exitCode=1});
