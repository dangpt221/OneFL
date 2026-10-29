/* Isolated default-voice/UI/job checks. Actual network speech is verified separately. */
const {chromium} = require('playwright');
const assert=require('node:assert/strict'), fs=require('node:fs'), path=require('node:path');
if(process.env.ONEFL_E2E!=='1')throw new Error('Requires isolated fixture');
const BASE=process.env.ONEFL_TEST_URL||'http://127.0.0.1:3100', FIXTURE=process.env.ONEFL_FIXTURE_URL||'http://127.0.0.1:8100';
const OUT=path.resolve(process.env.ONEFL_TEST_ARTIFACTS||'tmp/ngoc-huyen');fs.mkdirSync(OUT,{recursive:true});
const results=[],errors=[]; let projectId,preview;
async function scenario(name,work){try{await work();results.push({name,status:'passed'});console.log('PASS',name)}
catch(e){results.push({name,status:'failed',error:e.message});throw e}
finally{fs.writeFileSync(path.join(OUT,'browser-results.json'),JSON.stringify({projectId,results,errors},null,2));}}
(async()=>{
const browser=await chromium.launch({headless:true,executablePath:process.env.ONEFL_BROWSER||path.join(process.env.LOCALAPPDATA,'ms-playwright/chromium-1248/chrome-win64/chrome.exe')});
const context=await browser.newContext({viewport:{width:1280,height:1000}});await context.tracing.start({screenshots:true,snapshots:true});
const page=await context.newPage();page.setDefaultTimeout(20000);page.on('pageerror',e=>errors.push(e.message));
const dialog=()=>page.getByRole('dialog',{name:'Lồng tiếng'});
const ngoc=()=>dialog().getByRole('radio',{name:/Ngọc Huyền/});
const nam=()=>dialog().getByRole('radio',{name:/Nam Minh/});
const listen=()=>dialog().getByRole('button',{name:/Nghe thử giọng/});
const open=()=>page.getByRole('button',{name:/Lồng Tiếng AI$/}).click();
const close=()=>dialog().getByRole('button',{name:'Đóng',exact:true}).first().click();
async function api(url,method='GET',data){const r=await context.request.fetch(BASE+'/api/v1'+url,{method,data});assert.ok(r.ok(),`${url}: ${r.status()} ${await r.text()}`);return r.json();}
async function idle(){for(let i=0;i<250;i++){const p=await api('/projects/'+projectId);if(!p.active_job_id)return p;await page.waitForTimeout(100)}throw new Error('Fixture job timed out');}
try{
await api('/auth/login','POST',{token:'onefl-browser-fixture-access-2026'});
const p=await api('/projects/from-url','POST',{url:'https://www.bilibili.com/video/BV1MHh66uEFH/',auto_start_pipeline:false});projectId=p.id;await idle();
const seed=await context.request.post(FIXTURE+'/__e2e/control',{headers:{'x-e2e-key':'onefl-browser-fixture-access-2026'},data:{seed_project_id:projectId,seed_count:1}});assert.ok(seed.ok());
await page.goto(BASE+'/projects/'+projectId);await open();
await scenario('new project selects configured Ngoc Huyen; preview payload and audio playback match',async()=>{
assert.equal((await api('/projects/'+projectId)).default_voice,'vieneu-ngoc-huyen');await ngoc().waitFor();assert.ok(await ngoc().isChecked());
const catalog=await api('/tts/voices');assert.deepEqual(catalog.filter(v=>v.is_default).map(v=>v.id),['vieneu-ngoc-huyen']);
await dialog().locator('audio').evaluate(a=>{window.previewPlays=0;a.addEventListener('play',()=>window.previewPlays++);});
const [res]=await Promise.all([page.waitForResponse(r=>r.url().endsWith('/tts/preview')),listen().click()]);
assert.equal(res.status(),200);assert.equal(res.request().postDataJSON().voice,'vieneu-ngoc-huyen');preview=await res.json();
await page.waitForFunction(()=>window.previewPlays>0);assert.ok((await context.request.get(BASE+preview.preview_url)).ok());
await page.screenshot({path:path.join(OUT,'ngoc-huyen-selected.png'),fullPage:true});
});
await scenario('HTTP 502 shows actionable provider detail and keeps selected voice',async()=>{
await page.waitForFunction(()=>document.querySelector('[role="dialog"] audio').paused);
await page.route('**/tts/preview',r=>r.fulfill({status:502,contentType:'application/json',body:JSON.stringify({detail:'Microsoft Edge từ chối kết nối (HTTP 403). Kiểm tra kết nối mạng rồi thử lại.'})}));
await listen().click();await dialog().getByRole('alert').filter({hasText:'HTTP 403'}).waitFor();assert.ok(await ngoc().isChecked());assert.ok(await listen().isEnabled());await page.unroute('**/tts/preview');
});
await scenario('late preview failure after close cannot overwrite a reopened dialog',async()=>{
let release;const gate=new Promise(r=>release=r);
await page.route('**/tts/preview',async r=>{await gate;await r.fulfill({status:502,contentType:'application/json',body:JSON.stringify({detail:'Stale provider error'})});});
const pending=page.waitForRequest(r=>r.url().endsWith('/tts/preview'));await listen().click();await pending;await close();await open();await ngoc().waitFor();
release();await page.waitForTimeout(400);assert.equal(await dialog().getByRole('alert').count(),0);assert.ok(await ngoc().isChecked());assert.ok(await listen().isEnabled());await page.unroute('**/tts/preview');
});
await scenario('late preview success cannot play the previous voice after selection changes',async()=>{
let release;const gate=new Promise(r=>release=r);
await page.route('**/tts/preview',async r=>{await gate;await r.fulfill({status:200,contentType:'application/json',body:JSON.stringify(preview)});});
const pending=page.waitForRequest(r=>r.url().endsWith('/tts/preview'));await listen().click();await pending;await nam().check();release();
await page.waitForTimeout(400);assert.ok(await nam().isChecked());assert.ok(await dialog().locator('audio').evaluate(a=>a.paused));assert.ok(await listen().isEnabled());await page.unroute('**/tts/preview');
});
await scenario('an older pending play promise cannot pause a newer voice preview',async()=>{
await ngoc().check();
await dialog().locator('audio').evaluate(a=>{
const play=a.play.bind(a);let first=true;
a.play=()=>first?(first=false,new Promise(resolve=>window.releaseOldPlay=resolve)):play();
});
await listen().click();await page.waitForFunction(()=>typeof window.releaseOldPlay==='function');
await nam().check();await listen().click();
await page.waitForFunction(()=>!document.querySelector('[role="dialog"] audio').paused);
assert.ok(await page.evaluate(async()=>{window.releaseOldPlay();await new Promise(r=>setTimeout(r,0));return !document.querySelector('[role="dialog"] audio').paused;}));
await dialog().locator('audio').evaluate(a=>{a.pause();delete a.play;});
});
await scenario('real durable dubbing stores Ngoc Huyen and reopens its saved configuration',async()=>{
await ngoc().check();const [r]=await Promise.all([page.waitForResponse(r=>r.url().endsWith('/dub')&&r.request().method()==='POST'),dialog().getByRole('button',{name:/Bắt Đầu Lồng Tiếng Ngay/}).click()]);
assert.equal(r.status(),200);assert.equal(r.request().postDataJSON().voice,'vieneu-ngoc-huyen');
await dialog().waitFor({state:'hidden'});const p=await idle();assert.equal(p.status,'WAITING_REVIEW',p.error_message);assert.ok(p.dubbed_audio_url&&p.dubbed_video_url);assert.equal(p.default_voice,'vieneu-ngoc-huyen');assert.equal(p.last_dub_config.voice,'vieneu-ngoc-huyen');
await open();await ngoc().waitFor();assert.ok(await ngoc().isChecked());
fs.writeFileSync(path.join(OUT,'browser-dub-output.json'),JSON.stringify(p,null,2));
});
await scenario('explicit saved voice wins over the global default; mobile dialog stays within viewport',async()=>{
await nam().check();await dialog().getByRole('button',{name:/Bắt Đầu Lồng Tiếng Ngay/}).click();await dialog().waitFor({state:'hidden'});await idle();
await api('/projects/'+projectId,'PATCH',{default_voice:'vieneu-ngoc-huyen'});await page.reload();await open();await nam().waitFor();assert.ok(await nam().isChecked());
await page.setViewportSize({width:390,height:844});assert.ok(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth));
const box=await dialog().boundingBox();assert.ok(box.width<=390);await page.screenshot({path:path.join(OUT,'ngoc-huyen-mobile.png'),fullPage:true});
});
assert.deepEqual(errors,[]);
}finally{await context.tracing.stop({path:path.join(OUT,'tts-default-trace.zip')});await browser.close();}
})().catch(e=>{console.error(e);process.exitCode=1;});
